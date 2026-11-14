"""BI/analytics endpoints ported from the team's Flask API.

Paths are unchanged (``/api/health``, ``/api/dashboard/*``, ``/api/analytics/*``,
``/api/orders``, ``/api/alerts``).  JSON values keep the original conventions:
dashboard ``delay_rate`` is a ratio, ``late_rate`` in analytics is a ratio too.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from . import bi_service as S
from . import bi_validation as V
from .api_errors import register_error_handlers

bp = Blueprint("bi", __name__, url_prefix="/api")
register_error_handlers(bp)


@bp.get("/health")
def health_check():
    current_app.logger.info("--- HEALTH CHECK")
    return jsonify({"message": S.health_check()})


# ---------------------------------------------------------------------------
# Global filter lookup
# ---------------------------------------------------------------------------
@bp.get("/customer-states")
def get_customer_states():
    current_app.logger.info("Fetching customer states list")
    return jsonify(S.get_customer_states())


@bp.get("/seller-states")
def get_seller_states():
    current_app.logger.info("Fetching seller states list")
    return jsonify(S.get_seller_states())


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------
@bp.get("/dashboard/kpis")
def get_kpi():
    filters = V.filter_args(request.args)
    current_app.logger.info("Fetching dashboard KPIs with filters: %s", filters)
    return jsonify(S.get_kpi(filters))


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@bp.get("/analytics/late-trend")
def get_late_trend():
    query_args = V.late_trend_query(request.args)
    current_app.logger.info("Fetching late delivery trend with query: %s", query_args)
    return jsonify(S.get_late_trend(query_args))


@bp.get("/analytics/sla-breakdown")
def get_sla_breakdown():
    filters = V.filter_args(request.args)
    current_app.logger.info("Fetching SLA breakdown with filters: %s", filters)
    return jsonify(S.get_sla_breakdown(filters))


@bp.get("/analytics/regions")
def get_regions():
    filters = V.filter_args(request.args)
    current_app.logger.info("Fetching regional analytics with filters: %s", filters)
    return jsonify(S.get_regions(filters))


@bp.get("/analytics/sellers")
def get_sellers():
    query_args = V.seller_query(request.args)
    current_app.logger.info("Fetching seller analytics with query: %s", query_args)
    return jsonify(S.get_sellers(query_args))


# ---------------------------------------------------------------------------
# Drill-through and alerts
# ---------------------------------------------------------------------------
@bp.get("/orders")
def get_orders():
    query_args = V.orders_query(request.args)
    current_app.logger.info("Fetching orders with query: %s", query_args)
    return jsonify(S.get_orders(query_args))


@bp.get("/alerts")
def get_alerts():
    query_args = V.alerts_query(request.args)
    current_app.logger.info("Fetching alerts with query: %s", query_args)
    return jsonify(S.get_alerts(query_args))


# ---------------------------------------------------------------------------
# BI Dashboard overview
# ---------------------------------------------------------------------------
@bp.get("/dashboard/overview")
def get_dashboard_overview():
    query_args = V.overview_query(request.args)
    current_app.logger.info("Fetching dashboard overview with query: %s", query_args)
    return jsonify(S.get_overview(query_args))
