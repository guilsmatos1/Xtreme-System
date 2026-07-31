from fastapi import FastAPI

from xtreme_system.api.route_factories import register_crud_routes
from xtreme_system.investidor import core as investidor


def test_json_crud_with_pagina_publishes_response_schemas() -> None:
    app = FastAPI()

    register_crud_routes(
        app,
        investidor,
        "/investidores",
        "Investidor",
        read_schema=investidor.InvestidorRead,
        create_schema=investidor.InvestidorCreate,
        update_schema=investidor.InvestidorUpdate,
        pagina="investidores",
    )

    paths = app.openapi()["paths"]
    list_schema = paths["/investidores"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    read_ref = "#/components/schemas/InvestidorRead"

    assert list_schema["type"] == "array"
    assert list_schema["items"] == {"$ref": read_ref}
    assert (
        paths["/investidores/{item_id}"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == read_ref
    )
    assert (
        paths["/investidores"]["post"]["responses"]["201"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == read_ref
    )
    assert (
        paths["/investidores/{item_id}"]["patch"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == read_ref
    )
