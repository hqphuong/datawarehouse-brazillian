"""OLAP metadata and dynamic query endpoints (``/api/olap/*``)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from . import bi_service as S
from . import bi_validation as V
from .api_errors import register_error_handlers

bp = Blueprint("olap", __name__, url_prefix="/api/olap")
register_error_handlers(bp)


@bp.get("/metadata")
def get_olap_metadata():
    current_app.logger.info("Fetching OLAP metadata")
    return jsonify(S.get_olap_metadata())


@bp.post("/query")
def run_olap_query():
    payload = V.olap_payload(request.get_json(silent=True))
    current_app.logger.info("Running OLAP query: %s", payload)
    return jsonify(S.get_olap_query(payload))
