from fastapi.testclient import TestClient

from xtreme_system.api.core import app


def test_cors_allows_configured_origin_for_allowed_methods() -> None:
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert response.headers["access-control-allow-methods"] == (
        "GET, POST, PATCH, DELETE"
    )


def test_cors_denies_unconfigured_origins() -> None:
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_denies_unlisted_methods_and_headers() -> None:
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "X-Admin-Override",
        },
    )

    assert response.status_code == 400
    assert "PUT" not in response.headers["access-control-allow-methods"]
    assert "X-Admin-Override" not in response.headers["access-control-allow-headers"]
