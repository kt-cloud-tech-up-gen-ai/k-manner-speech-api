import json
import logging
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def _raise_test_error() -> None:
    raise RuntimeError("secret-password-must-not-leak")


if not any(getattr(route, "path", None) == "/_test/boom" for route in app.routes):
    app.add_api_route("/_test/boom", _raise_test_error, include_in_schema=False)


def test_500_uses_error_envelope_and_structured_log(caplog) -> None:
    caplog.set_level(logging.ERROR)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/_test/boom",
            headers={"Origin": "http://localhost:5173", "Cookie": "access_token=secret"},
        )

    assert response.status_code == 500, "AC-T1-ERROR-ENVELOPE"
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            "status": 500,
        }
    }, "AC-T1-ERROR-ENVELOPE"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    records = [json.loads(record.message) for record in caplog.records if record.name == "app.http"]
    assert len(records) == 1, "AC-T1-ERROR-ENVELOPE"
    assert records[0]["status"] == 500
    assert records[0]["path"] == "/_test/boom"
    assert records[0]["request_id"]
    assert "secret" not in caplog.text, "AC-LOG-NO-SECRETS"


def test_cors_allows_credentials_for_local_front() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200, "AC-E2E-LIVE-COOKIE-FLOW"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_known_http_error_uses_same_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/definitely-missing")

    assert response.status_code == 404
    assert response.json()["error"]["status"] == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_cors_rejects_unlisted_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_unexpected_error_handler_uses_configured_allowlist_directly() -> None:
    origin = "https://dev.example.test"
    with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": origin}):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/boom", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") == origin, (
        "AC-ERROR-CORS-CONFIG-SINGLE-SOURCE"
    )
