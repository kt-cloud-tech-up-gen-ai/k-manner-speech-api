from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

SESSION = {
    "access_token": "access-secret",
    "refresh_token": "refresh-secret",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {"id": "user-1", "email": "learner@example.com", "role": "authenticated"},
}


def _assert_private_session(response) -> None:
    body = response.json()
    assert "access_token" not in body, "AC-T2-HTTPONLY-LIFECYCLE"
    assert "refresh_token" not in body, "AC-T2-HTTPONLY-LIFECYCLE"
    cookies = response.headers.get_list("set-cookie")
    assert any("access_token=" in value and "HttpOnly" in value for value in cookies)
    assert any("refresh_token=" in value and "HttpOnly" in value for value in cookies)
    assert any("csrf_token=" in value and "HttpOnly" not in value for value in cookies)


def test_cookie_session_full_lifecycle() -> None:
    with (
        patch("app.routers.auth.sign_in_with_password", return_value=SESSION),
        patch("app.routers.auth.refresh_session", return_value=SESSION, create=True),
        TestClient(app) as client,
    ):
        login = client.post(
            "/auth/login",
            data={"username": "learner@example.com", "password": "correct-password"},
        )
        assert login.status_code == 200, "AC-T2-HTTPONLY-LIFECYCLE"
        _assert_private_session(login)

        csrf = client.cookies.get("csrf_token")
        refreshed = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert refreshed.status_code == 200, "AC-T2-HTTPONLY-LIFECYCLE"
        _assert_private_session(refreshed)

        rotated_csrf = client.cookies.get("csrf_token")
        logged_out = client.post("/auth/logout", headers={"X-CSRF-Token": rotated_csrf})
        assert logged_out.status_code == 204, "AC-T2-HTTPONLY-LIFECYCLE"
        assert client.cookies.get("access_token") is None
        assert client.cookies.get("refresh_token") is None


def test_signup_sets_private_cookie_without_token_body() -> None:
    with (
        patch("app.routers.auth.sign_up_with_password", return_value=SESSION),
        TestClient(app) as client,
    ):
        response = client.post(
            "/auth/signup",
            json={"email": "learner@example.com", "password": "correct-password"},
        )

    assert response.status_code == 201
    _assert_private_session(response)


def test_csrf_rejects_missing_and_mismatched_header() -> None:
    with TestClient(app) as client:
        client.cookies.set("access_token", "session")
        client.cookies.set("csrf_token", "expected")
        missing = client.post("/auth/logout")
        mismatch = client.post("/auth/logout", headers={"X-CSRF-Token": "wrong"})

    assert missing.status_code == 403
    assert mismatch.status_code == 403
    assert missing.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
