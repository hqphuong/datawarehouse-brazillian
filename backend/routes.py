from flask import jsonify
from flask_smorest import Blueprint, abort
from schema import (
    StdErrorSchema,
    req_FilterSchema,
    req_LateTrendSchema,
    req_OrdersQuerySchema,
    req_SellerQuerySchema,
    req_AlertsQuerySchema,
    res_HealthSchema,
    res_KpiSchema,
    res_StatesSchema,
    res_LateTrendSchema,
    res_SlaBreakdownSchema,
    res_OrdersSchema,
    res_RegionSchema,
    res_SellerSchema,
    res_AlertSchema,
)
import service
from app import logger

blp = Blueprint(
    "api", __name__,
    description="OLIST Logistics DSS Analytics & Operations API"
)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@blp.route('/api/health', methods=['GET'])
@blp.response(200, res_HealthSchema)
def health_check():
    logger.info('--- HEALTH CHECK')
    return {"message": service.health_check()}


# ---------------------------------------------------------------------------
# Global Filter Lookup Endpoints
# ---------------------------------------------------------------------------
@blp.route('/api/customer-states', methods=['GET'])
@blp.response(200, res_StatesSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_customer_states():
    logger.info('Fetching customer states list')
    return service.get_customer_states()


@blp.route('/api/seller-states', methods=['GET'])
@blp.response(200, res_StatesSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_seller_states():
    logger.info('Fetching seller states list')
    return service.get_seller_states()


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------
@blp.route('/api/dashboard/kpis', methods=['GET'])
@blp.arguments(req_FilterSchema, location='query')
@blp.response(200, res_KpiSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_kpi(filters):
    logger.info('Fetching dashboard KPIs with filters: %s', filters)
    return service.get_kpi(filters)


# ---------------------------------------------------------------------------
# Analytics: Late Delivery Trend
# ---------------------------------------------------------------------------
@blp.route('/api/analytics/late-trend', methods=['GET'])
@blp.arguments(req_LateTrendSchema, location='query')
@blp.response(200, res_LateTrendSchema(many=True))
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_late_trend(query_args):
    logger.info('Fetching late delivery trend with query: %s', query_args)
    return service.get_late_trend(query_args)


# ---------------------------------------------------------------------------
# Analytics: SLA Breakdown
# ---------------------------------------------------------------------------
@blp.route('/api/analytics/sla-breakdown', methods=['GET'])
@blp.arguments(req_FilterSchema, location='query')
@blp.response(200, res_SlaBreakdownSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_sla_breakdown(filters):
    logger.info('Fetching SLA breakdown with filters: %s', filters)
    return service.get_sla_breakdown(filters)


# ---------------------------------------------------------------------------
# Orders Drill-through
# ---------------------------------------------------------------------------
@blp.route('/api/orders', methods=['GET'])
@blp.arguments(req_OrdersQuerySchema, location='query')
@blp.response(200, res_OrdersSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_orders(query_args):
    logger.info('Fetching orders with query: %s', query_args)
    return service.get_orders(query_args)


# ---------------------------------------------------------------------------
# Analytics: Regional Analysis
# ---------------------------------------------------------------------------
@blp.route('/api/analytics/regions', methods=['GET'])
@blp.arguments(req_FilterSchema, location='query')
@blp.response(200, res_RegionSchema(many=True))
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_regions(filters):
    logger.info('Fetching regional analytics with filters: %s', filters)
    return service.get_regions(filters)


# ---------------------------------------------------------------------------
# Analytics: Seller Performance
# ---------------------------------------------------------------------------
@blp.route('/api/analytics/sellers', methods=['GET'])
@blp.arguments(req_SellerQuerySchema, location='query')
@blp.response(200, res_SellerSchema(many=True))
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_sellers(query_args):
    logger.info('Fetching seller analytics with query: %s', query_args)
    return service.get_sellers(query_args)


# ---------------------------------------------------------------------------
# Operational Alerts
# ---------------------------------------------------------------------------
@blp.route('/api/alerts', methods=['GET'])
@blp.arguments(req_AlertsQuerySchema, location='query')
@blp.response(200, res_AlertSchema(many=True))
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_alerts(query_args):
    logger.info('Fetching alerts with query: %s', query_args)
    return service.get_alerts(query_args)
