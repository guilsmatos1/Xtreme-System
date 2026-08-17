"""HTMX routes for integração RSD (puxar dados + consulta unitária)."""

import json
import time
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BeforeValidator, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xtreme_system.api.deps import (
    SessionDep,
    UIAdmin,
    found,
    require_operacao,
    templates,
)
from xtreme_system.api.routes.ui_routes.filters import (
    IdFiltro,
    PeriodoFiltro,
    TextoFiltro,
    vazio_para_none,
)
from xtreme_system.database.core import SessionLocal, detach_request_session
from xtreme_system.rsd import core as rsd
from xtreme_system.usuario import core as usuario
from xtreme_system.veiculo import core as veiculo

logger = structlog.get_logger(__name__)

router = APIRouter()
_RSD_STATUS_IDS = {
    "rsd-status",
    "rsd-status-compra",
    "rsd-status-consignacao",
    "rsd-status-veiculo",
}

# Contador de falhas transitórias consecutivas por dossiê, para o poll do
# lado do cliente tolerar blips de rede sem parar de pollar nem sobrescrever
# o estado do dossiê a cada erro (ver atualizar_consulta_dossie).
_POLL_TRANSIENT_MAX = 3
_poll_falhas: dict[int, int] = {}


def _normalize_status_id(value: str) -> str:
    return value if value in _RSD_STATUS_IDS else "rsd-status"


def _normalize_prefix(value: str) -> str:
    return value if value in {"", "vei_", "veic_troca_"} else ""


# Só estes erros dizem algo sobre a credencial. Indisponibilidade do portal,
# timeout ou erro de consulta não: rebaixar o status nesses casos manda o
# operador reconfigurar um e-mail/senha que estão corretos.
_ERROS_DE_CREDENCIAL = (
    rsd.RsdAuthError,
    rsd.RsdCapabilityError,
    rsd.RsdEncryptionError,
)


def _marcar_falha_credencial(config: rsd.RsdConfig, erro: rsd.RsdError) -> None:
    if not isinstance(erro, _ERROS_DE_CREDENCIAL) or not rsd.configurado(config):
        return
    rsd.registrar_teste_config_persistente(
        email=config.email,
        senha=rsd.senha_config(config),
        base_url=config.base_url,
        sucesso=False,
        erro=erro,
    )


def _status_partial(
    request: Request,
    *,
    erro: str | None = None,
    sucesso: str | None = None,
    unitaria: rsd.UnitariaResult | None = None,
    status_id: str = "rsd-status",
    status_code: int = 200,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "erro": erro,
            "sucesso": sucesso,
            "unitaria": unitaria,
            "status_id": _normalize_status_id(status_id),
        },
        status_code=status_code,
    )
    # Este endpoint atualiza só o status parcial do RSD dentro do modal, que
    # deve continuar aberto. Sem isto, o middleware global
    # (_htmx_write_feedback) adiciona HX-Trigger: close-modal a qualquer POST
    # 2xx sem HX-Trigger próprio, e o cliente fecha #modal.
    response.headers["HX-Trigger"] = "{}"
    return response


def _placa_para_puxar_dados(placa: str) -> str:
    """Normaliza a placa do form; levanta ValueError com mensagem de UI."""
    raw = (placa or "").strip()
    if not raw:
        raise ValueError("Informe a placa para puxar dados.")
    try:
        return veiculo.normalizar_placa(raw)
    except veiculo.PlacaInvalidaError as exc:
        raise ValueError(str(exc)) from exc


@router.post("/ui/rsd/puxar-dados")
async def ui_rsd_puxar_dados(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    rsd_prefix: Annotated[str, Form()] = "",
    rsd_status_id: Annotated[str, Form()] = "rsd-status",
) -> HTMLResponse:
    form = await request.form()
    placa = str(form.get(f"{rsd_prefix}placa") or "")
    try:
        placa = _placa_para_puxar_dados(placa)
    except ValueError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    inicio = time.monotonic()
    try:
        dados = client.puxar_dados(placa)
    except rsd.RsdError as exc:
        _marcar_falha_credencial(config, exc)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logger.warning(
            "rsd_puxar_dados_falhou",
            placa=placa,
            duracao_ms=duracao_ms,
            **rsd.contexto_log(exc),
        )
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.puxar_dados,
            placa=placa,
            usuario_id=user.id,
            sucesso=False,
            erro=rsd.erro_para_historico(exc),
            duracao_ms=duracao_ms,
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    duracao_ms = int((time.monotonic() - inicio) * 1000)
    campos = rsd.mapear_para_veiculo(dados, prefix=_normalize_prefix(rsd_prefix))
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.puxar_dados,
        placa=placa,
        usuario_id=user.id,
        payload=dados.model_dump(),
        campos_aplicados=campos,
        sucesso=True,
        duracao_ms=duracao_ms,
    )
    response = templates.TemplateResponse(
        request,
        "_rsd_status.html",
        {
            "sucesso": "Dados carregados do RSD.",
            "campos": campos,
            "erro": None,
            "unitaria": None,
            "status_id": _normalize_status_id(rsd_status_id),
        },
    )
    # Ver comentário em _status_partial: este POST atualiza o status parcial
    # dentro do modal, que deve continuar aberto.
    response.headers["HX-Trigger"] = "{}"
    return response


def _rotacionar_proprietario(
    obj: veiculo.Veiculo, campos: dict[str, Any]
) -> dict[str, Any]:
    """Move o proprietário atual para "anterior" quando o RSD traz um novo.

    O portal só devolve o proprietário corrente; "anterior" é conhecimento
    nosso — é o nome que estava gravado antes desta consulta. Só rotaciona
    quando o nome de fato mudou, para que reconsultas seguidas do mesmo
    veículo não apaguem o histórico duplicando o nome nos dois campos.
    Se o próprio portal devolveu um anterior, ele tem prioridade.
    """
    novo = str(campos.get("proprietario_atual") or "").strip()
    atual = (obj.proprietario_atual or "").strip()
    if not novo or not atual or campos.get("proprietario_anterior"):
        return campos
    if novo.casefold() == atual.casefold():
        return campos
    return {**campos, "proprietario_anterior": atual}


def _aplicar_campos_no_veiculo(
    veiculo_id: int, campos: dict[str, Any], actor_id: int
) -> None:
    """Grava os campos vindos do RSD no veículo, em sessão própria.

    A rota chama `detach_request_session` antes da chamada ao portal (ver
    docs/agents/transactions-rollbacks.md), então quando o resultado chega não
    há mais sessão do request para gravar — mesmo motivo pelo qual
    `rsd.registrar_consulta` abre a sua. Diferente dela, aqui a exceção sobe:
    uma falha de gravação precisa virar alerta para o usuário, não log silencioso.
    """
    session = SessionLocal()
    try:
        obj = found(veiculo.get(session, veiculo_id), "Veículo")
        campos = _rotacionar_proprietario(obj, campos)
        veiculo.update(session, obj, veiculo.VeiculoUpdate(**campos), actor_id=actor_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/ui/rsd/veiculos/{veiculo_id}/atualizar")
def ui_rsd_atualizar_veiculo(
    veiculo_id: int,
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
) -> Response:
    """Puxa os dados do RSD pela placa do veículo e grava no próprio registro.

    Diferente de `ui_rsd_puxar_dados`, que devolve os campos para o JS preencher
    um formulário aberto, aqui a escrita é server-side: é a ação de um clique na
    página de detalhes, onde não há formulário para submeter depois.
    """
    obj = found(veiculo.get(session, veiculo_id), "Veículo")
    try:
        placa = _placa_para_puxar_dados(obj.placa or "")
    except ValueError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id="rsd-status-veiculo",
            status_code=400,
        )

    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id="rsd-status-veiculo",
            status_code=400,
        )

    # A sessão de teste pode ser compartilhada entre requests e ainda conter
    # a gravação da configuração RSD. Fecha esse limite antes de abrir a
    # sessão própria usada após a chamada externa, evitando lock no SQLite.
    session.commit()
    detach_request_session(request, keep=(user, config, obj))
    inicio = time.monotonic()
    modo = config.modo_atualizacao
    tipo_consulta = (
        rsd.TipoConsultaRsd.unitaria
        if modo == rsd.ModoAtualizacaoRsd.crlv
        else rsd.TipoConsultaRsd.puxar_dados
    )
    dossie_id: int | None = None
    try:
        if modo == rsd.ModoAtualizacaoRsd.crlv:
            dados, dossie_id = client.puxar_dados_crlv(placa)
        else:
            dados = client.puxar_dados(placa)
    except rsd.RsdError as exc:
        _marcar_falha_credencial(config, exc)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logger.warning(
            "rsd_atualizar_veiculo_falhou",
            veiculo_id=obj.id,
            placa=placa,
            modo=modo,
            duracao_ms=duracao_ms,
            **rsd.contexto_log(exc),
        )
        rsd.registrar_consulta(
            tipo=tipo_consulta,
            placa=placa,
            veiculo_id=obj.id,
            usuario_id=user.id,
            sucesso=False,
            erro=rsd.erro_para_historico(exc),
            duracao_ms=duracao_ms,
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id="rsd-status-veiculo",
            status_code=400,
        )

    duracao_ms = int((time.monotonic() - inicio) * 1000)
    campos = rsd.mapear_para_veiculo(dados)
    try:
        _aplicar_campos_no_veiculo(obj.id, campos, user.id)
    except IntegrityError:
        logger.warning("rsd_atualizar_veiculo_conflito", veiculo_id=obj.id, placa=placa)
        rsd.registrar_consulta(
            tipo=tipo_consulta,
            placa=placa,
            veiculo_id=obj.id,
            usuario_id=user.id,
            payload=dados.model_dump(),
            campos_aplicados=campos,
            sucesso=False,
            erro="conflito ao gravar dados do RSD",
            dossie_id=dossie_id,
            duracao_ms=duracao_ms,
        )
        return _status_partial(
            request,
            erro="Os dados retornados pelo RSD conflitam com outro veículo já "
            "cadastrado. Nada foi alterado.",
            status_id="rsd-status-veiculo",
            status_code=400,
        )

    rsd.registrar_consulta(
        tipo=tipo_consulta,
        placa=placa,
        veiculo_id=obj.id,
        usuario_id=user.id,
        payload=dados.model_dump(),
        campos_aplicados=campos,
        sucesso=True,
        dossie_id=dossie_id,
        duracao_ms=duracao_ms,
    )
    response = Response(status_code=204)
    response.headers["HX-Refresh"] = "true"
    # Ver comentário em _status_partial: sem HX-Trigger próprio o middleware
    # global (_htmx_write_feedback) injeta toast + close-modal neste POST.
    response.headers["HX-Trigger"] = "{}"
    return response


@router.post("/ui/rsd/consulta-unitaria")
def ui_rsd_consulta_unitaria(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    placa: Annotated[str, Form()] = "",
    vei_placa: Annotated[str, Form()] = "",
    rsd_status_id: Annotated[str, Form()] = "rsd-status",
) -> HTMLResponse:
    placa = placa or vei_placa
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    inicio = time.monotonic()
    try:
        dossie_id = client.iniciar_unitaria(placa)
    except rsd.RsdError as exc:
        _marcar_falha_credencial(config, exc)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logger.warning(
            "rsd_iniciar_unitaria_falhou",
            placa=placa,
            duracao_ms=duracao_ms,
            **rsd.contexto_log(exc),
        )
        rsd.registrar_consulta(
            tipo=rsd.TipoConsultaRsd.unitaria,
            placa=placa,
            usuario_id=user.id,
            sucesso=False,
            erro=rsd.erro_para_historico(exc),
            duracao_ms=duracao_ms,
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    duracao_ms = int((time.monotonic() - inicio) * 1000)
    rsd.registrar_consulta(
        tipo=rsd.TipoConsultaRsd.unitaria,
        placa=placa,
        usuario_id=user.id,
        sucesso=True,
        dossie_id=dossie_id,
        status_dossie="processing",
        duracao_ms=duracao_ms,
    )
    return _status_partial(
        request,
        sucesso="Consulta iniciada — aguardando o portal…",
        unitaria=rsd.UnitariaResult(
            dossie_id=dossie_id, status="processing", is_terminal=False
        ),
        status_id=rsd_status_id,
    )


@router.get("/ui/rsd/dossie/{dossie_id}/status")
def ui_rsd_dossie_status(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    dossie_id: int,
    rsd_status_id: str = "rsd-status",
) -> HTMLResponse:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdError as exc:
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    detach_request_session(request, keep=(user, config))
    inicio = time.monotonic()
    try:
        resultado = client.status_unitaria(dossie_id)
    except rsd.RsdError as exc:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        falhas = _poll_falhas.get(dossie_id, 0) + 1
        _poll_falhas[dossie_id] = falhas
        logger.warning(
            "rsd_poll_status_falhou",
            dossie_id=dossie_id,
            tentativa=falhas,
            duracao_ms=duracao_ms,
            **rsd.contexto_log(exc),
        )
        if falhas < _POLL_TRANSIENT_MAX:
            # Erro transitório: não sobrescreve o estado já gravado do
            # dossiê (ficaria marcado como fracassado mesmo processando
            # normalmente no portal) e mantém o poll do cliente ativo.
            return _status_partial(
                request,
                sucesso="Consulta em andamento…",
                unitaria=rsd.UnitariaResult(
                    dossie_id=dossie_id, status="processing", is_terminal=False
                ),
                status_id=rsd_status_id,
            )
        _poll_falhas.pop(dossie_id, None)
        _marcar_falha_credencial(config, exc)
        rsd.atualizar_consulta_dossie(
            dossie_id=dossie_id,
            payload=None,
            status_dossie=None,
            sucesso=False,
            erro=rsd.erro_para_historico(exc),
        )
        return _status_partial(
            request,
            erro=str(exc),
            status_id=rsd_status_id,
            status_code=400,
        )

    _poll_falhas.pop(dossie_id, None)
    if resultado.is_terminal:
        rsd.atualizar_consulta_dossie(
            dossie_id=dossie_id,
            payload=resultado.model_dump(),
            status_dossie=resultado.status,
            sucesso=not bool(resultado.error),
            erro=resultado.error,
        )
    return _status_partial(
        request,
        sucesso=resultado.status_display or "Consulta em andamento…",
        unitaria=resultado,
        status_id=rsd_status_id,
    )


@router.get("/ui/rsd/dossie/{dossie_id}/pdf")
def ui_rsd_dossie_pdf(
    request: Request,
    session: SessionDep,
    user: Annotated[usuario.Usuario, Depends(require_operacao("veiculos", "editar"))],
    dossie_id: int,
) -> Response:
    config = rsd.get_config(session)
    try:
        client = rsd.client_from_config(config)
    except rsd.RsdError as exc:
        return HTMLResponse(str(exc), status_code=400)

    detach_request_session(request, keep=(user, config))
    try:
        pdf = client.baixar_pdf(dossie_id)
    except rsd.RsdError as exc:
        _marcar_falha_credencial(config, exc)
        logger.warning(
            "rsd_baixar_pdf_falhou", dossie_id=dossie_id, **rsd.contexto_log(exc)
        )
        return HTMLResponse(str(exc), status_code=400)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="dossie-{dossie_id}.pdf"'
        },
    )


# ---- Histórico de consultas (admin-only, read-only) ----

LIMIT_MAX = 200


class FiltroRsdConsulta(PeriodoFiltro):
    placa: TextoFiltro = None
    usuario_id: IdFiltro = None
    sucesso: Annotated[bool | None, BeforeValidator(vazio_para_none)] = None

    @staticmethod
    def _periodo_padrao() -> tuple[date, date]:
        hoje = datetime.now(UTC).date()
        return hoje - timedelta(days=7), hoje


class FiltroRsdConsultaPagina(FiltroRsdConsulta):
    limit: int = Field(50, ge=1, le=LIMIT_MAX)
    offset: int = Field(0, ge=0)


FiltroRsdConsultaPaginaDep = Annotated[FiltroRsdConsultaPagina, Query()]


def _nomes_usuarios(
    session: Session, registros: list[rsd.RsdConsulta]
) -> dict[int, str]:
    ids = {r.usuario_id for r in registros if r.usuario_id is not None}
    if not ids:
        return {}
    rows = (
        session.query(usuario.Usuario.id, usuario.Usuario.username)
        .filter(usuario.Usuario.id.in_(ids))
        .all()
    )
    return dict(cast("list[tuple[int, str]]", rows))


def _filtros_qs(f: FiltroRsdConsultaPagina) -> dict[str, Any]:
    data_de, data_ate = f.periodo
    filtros: dict[str, Any] = {
        "data_de": data_de.isoformat(),
        "data_ate": data_ate.isoformat(),
    }
    if f.placa:
        filtros["placa"] = f.placa
    if f.usuario_id is not None:
        filtros["usuario_id"] = f.usuario_id
    if f.sucesso is not None:
        filtros["sucesso"] = str(f.sucesso).lower()
    return filtros


def _ctx_consultas(
    session: Session, user: usuario.Usuario, f: FiltroRsdConsultaPagina
) -> dict[str, Any]:
    registros = rsd.listar_consultas(
        session,
        placa=f.placa,
        usuario_id=f.usuario_id,
        sucesso=f.sucesso,
        data_de=f.data_de,
        data_ate=f.data_ate,
        limit=f.limit,
        offset=f.offset,
    )
    total = rsd.count_consultas(
        session,
        placa=f.placa,
        usuario_id=f.usuario_id,
        sucesso=f.sucesso,
        data_de=f.data_de,
        data_ate=f.data_ate,
    )
    return {
        "user": user,
        "registros": registros,
        "nomes_usuarios": _nomes_usuarios(session, registros),
        "usuarios": usuario.list_all(session),
        "f_placa": f.placa,
        "f_usuario_id": f.usuario_id,
        "f_sucesso": f.sucesso,
        "f_data_de": f.data_de,
        "f_data_ate": f.data_ate,
        "filtros_qs": urlencode(_filtros_qs(f)),
        "total": total,
        "limit": f.limit,
        "offset": f.offset,
    }


@router.get("/consultas")
def ui_rsd_consultas(
    request: Request,
    session: SessionDep,
    user: UIAdmin,
    filtros: FiltroRsdConsultaPaginaDep,
) -> HTMLResponse:
    ctx = _ctx_consultas(session, user, filtros)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "_rsd_consultas_resultado.html", ctx)
    return templates.TemplateResponse(request, "rsd_consultas.html", ctx)


def _pretty(dados: dict[str, Any] | None) -> str | None:
    if dados is None:
        return None
    return json.dumps(dados, indent=2, ensure_ascii=False, default=str)


@router.get("/consultas/{consulta_id}/detalhe")
def ui_rsd_consulta_detalhe(
    consulta_id: int, request: Request, session: SessionDep, _: UIAdmin
) -> HTMLResponse:
    reg = found(rsd.get_consulta(session, consulta_id), "Consulta RSD")
    nome: str | None = None
    if reg.usuario_id is not None:
        u = usuario.get(session, reg.usuario_id)
        nome = u.username if u else None
    return templates.TemplateResponse(
        request,
        "_detalhe_rsd_consulta.html",
        {
            "reg": reg,
            "usuario_username": nome,
            "payload_json": _pretty(reg.payload),
            "campos_aplicados_json": _pretty(reg.campos_aplicados),
        },
    )
