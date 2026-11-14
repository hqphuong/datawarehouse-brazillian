"""Shared JSON error contract for the BI/OLAP/auth blueprints.

The ``/api/dss/*`` endpoints keep their original Django-compatible contract
(``{"error": ...}`` and HTML framework responses); this module is only used by
the blueprints ported from the team's Flask API, where every error is
``{"message": "<string>"}``.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from werkzeug.exceptions import MethodNotAllowed


class ApiError(Exception):
    """Validation / domain error rendered as ``{"message": ...}``."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(bp: Blueprint) -> None:
    @bp.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return jsonify({"message": exc.message}), exc.status

    @bp.errorhandler(MethodNotAllowed)
    def _method_not_allowed(exc: MethodNotAllowed):
        response = jsonify({"message": "Method not allowed"})
        response.status_code = 405
        allowed = [m for m in (exc.valid_methods or [])]
        if allowed:
            response.headers["Allow"] = ", ".join(allowed)
        return response

    @bp.errorhandler(Exception)
    def _unexpected(exc: Exception):  # pragma: no cover - defensive
        current_app.logger.exception("Unhandled BI API error")
        return jsonify({"message": "Internal server error"}), 500
