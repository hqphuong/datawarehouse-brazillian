"""Tests for ``/api/auth/*`` and the credential service."""

from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from dss import auth_service as A
from dss.app import create_app


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Credential service
# ---------------------------------------------------------------------------
def test_login_unknown_user(monkeypatch):
    monkeypatch.setattr(A.repo, "get_account", lambda username: None)
    assert A.login("nobody", "secret") is None


def test_login_accepts_werkzeug_hash(monkeypatch):
    stored = generate_password_hash("secret")
    monkeypatch.setattr(
        A.repo, "get_account", lambda username: {"username": "admin", "password": stored}
    )
    assert A.login("admin", "secret") == "admin"
    assert A.login("admin", "wrong") is None


def test_login_upgrades_legacy_plaintext(monkeypatch):
    updates = {}
    monkeypatch.setattr(
        A.repo,
        "get_account",
        lambda username: {"username": "admin", "password": "legacy-pass"},
    )
    monkeypatch.setattr(
        A.repo,
        "update_account_password",
        lambda username, value: updates.update({"username": username, "value": value}),
    )

    assert A.login("admin", "legacy-pass") == "admin"
    assert updates["username"] == "admin"
    assert updates["value"].startswith(("scrypt:", "pbkdf2:"))
    assert updates["value"] != "legacy-pass"


def test_login_rejects_wrong_legacy_plaintext(monkeypatch):
    called = {"upgraded": False}
    monkeypatch.setattr(
        A.repo,
        "get_account",
        lambda username: {"username": "admin", "password": "legacy-pass"},
    )
    monkeypatch.setattr(
        A.repo,
        "update_account_password",
        lambda username, value: called.update({"upgraded": True}),
    )

    assert A.login("admin", "nope") is None
    assert called["upgraded"] is False


def test_login_upgrade_failure_still_logs_in(monkeypatch):
    def boom(username, value):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        A.repo,
        "get_account",
        lambda username: {"username": "admin", "password": "legacy-pass"},
    )
    monkeypatch.setattr(A.repo, "update_account_password", boom)

    assert A.login("admin", "legacy-pass") == "admin"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_login_success_sets_session_cookie(client, monkeypatch):
    monkeypatch.setattr(A, "login", lambda username, password: "admin")
    res = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret"}
    )
    assert res.status_code == 200
    assert res.get_json() == {"message": "Login successful", "username": "admin"}
    cookie = res.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_login_invalid_credentials(client, monkeypatch):
    monkeypatch.setattr(A, "login", lambda username, password: None)
    res = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert res.status_code == 401
    assert res.get_json() == {"message": "Invalid username or password"}


def test_login_validation_errors(client):
    cases = [
        None,
        {},
        {"username": "", "password": "x"},
        {"username": "admin", "password": ""},
        {"username": 1, "password": "x"},
        {"username": "admin"},
    ]
    for payload in cases:
        res = client.post("/api/auth/login", json=payload)
        assert res.status_code == 400
        body = res.get_json()
        assert set(body) == {"message"}
        assert isinstance(body["message"], str)


def test_unknown_json_keys_ignored(client, monkeypatch):
    monkeypatch.setattr(A, "login", lambda username, password: username)
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret", "remember": True},
    )
    assert res.status_code == 200
    assert res.get_json()["username"] == "admin"


def test_me_before_and_after_login(client, monkeypatch):
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.get_json() == {"authenticated": False, "username": None}

    monkeypatch.setattr(A, "login", lambda username, password: "admin")
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.get_json() == {"authenticated": True, "username": "admin"}


def test_logout_clears_session(client, monkeypatch):
    monkeypatch.setattr(A, "login", lambda username, password: "admin")
    client.post("/api/auth/login", json={"username": "admin", "password": "secret"})

    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.get_json() == {"message": "Logged out"}

    res = client.get("/api/auth/me")
    assert res.get_json() == {"authenticated": False, "username": None}


def test_auth_method_not_allowed_is_json(client):
    res = client.get("/api/auth/login")
    assert res.status_code == 405
    assert res.get_json() == {"message": "Method not allowed"}
