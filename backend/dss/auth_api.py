"""Minimal session-based authentication (``/api/auth/*``).

Same contract as the team's API: ``accounts`` table, server-side session cookie,
``SECRET_KEY`` required.  Credentials may be stored as a werkzeug hash; legacy
plain-text rows are upgraded on first successful login.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from . import auth_service as A
from .api_errors import ApiError, register_error_handlers

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
register_error_handlers(bp)


def _credentials(payload):
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object")
    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not username:
        raise ApiError("username must be a non-empty string")
    if not isinstance(password, str) or not password:
        raise ApiError("password must be a non-empty string")
    return username, password


@bp.post("/login")
def login():
    username, password = _credentials(request.get_json(silent=True))
    current_app.logger.info("Login attempt for username: %s", username)

    authenticated = A.login(username, password)
    if not authenticated:
        raise ApiError("Invalid username or password", 401)

    session["username"] = authenticated
    return jsonify({"message": "Login successful", "username": authenticated})


@bp.post("/logout")
def logout():
    session.pop("username", None)
    return jsonify({"message": "Logged out"})


@bp.get("/me")
def current_user():
    username = session.get("username")
    return jsonify({"authenticated": username is not None, "username": username})
