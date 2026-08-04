"""Factory for attachment modal, upload, and delete routes."""

from collections.abc import Callable
from dataclasses import dataclass
from inspect import Parameter, Signature
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from xtreme_system.api.deps import SessionDep, found, templates
from xtreme_system.api.routes.ui_routes.uploads import (
    excluir_anexo_entidade,
    pending_upload_paths,
    salvar_anexos_entidade,
)
from xtreme_system.usuario import core as usuario

ParentLoader = Callable[[Session, int], Any]
AttachmentCallback = Callable[[Session, Any, int], Any]
AttachmentContext = Callable[[Session, Any, usuario.Usuario], dict[str, Any]]
UploadDirectory = Callable[[int], Path]
UploadUrl = Callable[[int], str]


def _empty_context(
    _session: Session, _parent: Any, _user: usuario.Usuario
) -> dict[str, Any]:
    return {}


def callback_from(namespace: dict[str, Any], path: str) -> Callable[..., Any]:
    """Resolve a module callback when the route handles a request.

    Keeping resolution lazy preserves the module-level seams used by tests and
    by deployments that replace upload storage callbacks at runtime.
    """

    def callback(*args: Any, **kwargs: Any) -> Any:
        value: Any = namespace
        for part in path.split("."):
            value = value[part] if isinstance(value, dict) else getattr(value, part)
        return value(*args, **kwargs)

    return callback


@dataclass(frozen=True)
class AttachmentRouteConfig:  # pylint: disable=too-many-instance-attributes
    name: str
    path: str
    parent_param: str
    attachment_param: str
    parent_loader: ParentLoader
    attachment_loader: ParentLoader
    parent_label: str
    parent_context_key: str
    template: str
    upload_dir: UploadDirectory
    url_prefix: UploadUrl
    create_fn: AttachmentCallback
    schema: type[BaseModel]
    fk_field: str
    delete_fn: AttachmentCallback
    upload_field: str
    attachment_label: str
    get_dependency: Any
    upload_dependency: Any
    delete_dependency: Any
    refresh_parent: bool = True
    extra_context: AttachmentContext = _empty_context


def _parameter(
    name: str,
    annotation: Any,
    *,
    kind: Any = Parameter.POSITIONAL_OR_KEYWORD,
) -> Parameter:
    return Parameter(name, kind, annotation=annotation)


def _route_signature(
    config: AttachmentRouteConfig, *, upload: bool = False, delete: bool = False
) -> Signature:
    parameters = [
        _parameter("request", Request),
        _parameter("session", SessionDep),
        _parameter(
            "user",
            config.delete_dependency
            if delete
            else config.upload_dependency
            if upload
            else config.get_dependency,
        ),
        _parameter(config.parent_param, int),
    ]
    if upload:
        parameters.append(
            _parameter(
                "arquivos",
                Annotated[
                    list[UploadFile],
                    File(default_factory=list, alias=config.upload_field),
                ],
            )
        )
    elif delete:
        parameters.append(_parameter(config.attachment_param, int))
    return Signature(parameters=parameters, return_annotation=HTMLResponse)


def register_attachment_routes(
    app: FastAPI | APIRouter, config: AttachmentRouteConfig
) -> None:
    """Register the standard GET/upload/delete attachment route trio."""

    def render(
        request: Request,
        session: Session,
        user: usuario.Usuario,
        parent_id: int,
        *,
        error: str | None = None,
        action_oob: bool = False,
    ) -> HTMLResponse:
        parent = found(config.parent_loader(session, parent_id), config.parent_label)
        if config.refresh_parent:
            session.refresh(parent)
        context: dict[str, Any] = {
            config.parent_context_key: parent,
            "user": user,
            "action_oob": action_oob,
            "pending_upload_paths": pending_upload_paths(session),
        }
        if error is not None:
            context["erro"] = error
        context.update(config.extra_context(session, parent, user))
        return templates.TemplateResponse(
            request,
            config.template,
            context,
            status_code=400 if error else 200,
        )

    def get_endpoint(**kwargs: Any) -> HTMLResponse:
        return render(
            kwargs["request"],
            kwargs["session"],
            kwargs["user"],
            kwargs[config.parent_param],
        )

    def upload_endpoint(**kwargs: Any) -> HTMLResponse:
        parent_id = kwargs[config.parent_param]
        user = kwargs["user"]
        session = kwargs["session"]
        found(config.parent_loader(session, parent_id), config.parent_label)
        error = salvar_anexos_entidade(
            session,
            upload_dir=config.upload_dir(parent_id),
            url_prefix=config.url_prefix(parent_id),
            create_fn=config.create_fn,
            schema=config.schema,
            fk_field=config.fk_field,
            fk_id=parent_id,
            arquivos=kwargs["arquivos"],
            actor_id=user.id,
        )
        if error:
            return render(
                kwargs["request"],
                session,
                user,
                parent_id,
                error=error,
            )
        return render(
            kwargs["request"],
            session,
            user,
            parent_id,
            action_oob=True,
        )

    def delete_endpoint(**kwargs: Any) -> HTMLResponse:
        parent_id = kwargs[config.parent_param]
        session = kwargs["session"]
        user = kwargs["user"]
        attachment = found(
            config.attachment_loader(session, kwargs[config.attachment_param]),
            config.attachment_label,
        )
        excluir_anexo_entidade(
            session,
            anexo=attachment,
            parent_field=config.fk_field,
            parent_id=parent_id,
            delete_fn=config.delete_fn,
            actor_id=user.id,
            not_found_detail=f"{config.attachment_label} não encontrado",
        )
        return render(
            kwargs["request"],
            session,
            user,
            parent_id,
            action_oob=True,
        )

    get_endpoint.__signature__ = _route_signature(config)  # type: ignore[attr-defined]
    upload_endpoint.__signature__ = _route_signature(config, upload=True)  # type: ignore[attr-defined]
    delete_endpoint.__signature__ = _route_signature(config, delete=True)  # type: ignore[attr-defined]

    app.add_api_route(
        config.path,
        get_endpoint,
        methods=["GET"],
        response_class=HTMLResponse,
        name=f"{config.name}_modal",
    )
    app.add_api_route(
        config.path,
        upload_endpoint,
        methods=["POST"],
        response_class=HTMLResponse,
        name=f"{config.name}_upload",
    )
    app.add_api_route(
        f"{config.path}/{{{config.attachment_param}}}/excluir",
        delete_endpoint,
        methods=["POST"],
        response_class=HTMLResponse,
        name=f"{config.name}_delete",
    )
