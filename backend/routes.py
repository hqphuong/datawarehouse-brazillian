from flask import jsonify, session
from flask_smorest import Blueprint, abort
from schema import (
    StdErrorSchema,
    req_FilterSchema,
    req_LateTrendSchema,
    req_OrdersQuerySchema,
    req_SellerQuerySchema,
    req_AlertsQuerySchema,
    req_OlapQuerySchema,
    req_OverviewSchema,
    req_LoginSchema,
    res_HealthSchema,
    res_KpiSchema,
    res_StatesSchema,
    res_LateTrendSchema,
    res_SlaBreakdownSchema,
    res_OrdersSchema,
    res_RegionSchema,
    res_SellerSchema,
    res_AlertSchema,
    res_OlapMetadataSchema,
    res_OlapQuerySchema,
    res_OverviewSchema,
    res_LoginSchema,
    res_LogoutSchema,
    res_MeSchema,
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


# ---------------------------------------------------------------------------
# OLAP Query Builder: filter metadata
# ---------------------------------------------------------------------------
@blp.route('/api/olap/metadata', methods=['GET'])
@blp.response(200, res_OlapMetadataSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_olap_metadata():
    logger.info('Fetching OLAP metadata')
    return service.get_olap_metadata()


# ---------------------------------------------------------------------------
# OLAP Query Builder: dynamic pivot / aggregation
# ---------------------------------------------------------------------------
@blp.route('/api/olap/query', methods=['POST'])
@blp.arguments(req_OlapQuerySchema)
@blp.response(200, res_OlapQuerySchema)
@blp.alt_response(422, schema=StdErrorSchema, description="Invalid OLAP payload")
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def run_olap_query(payload):
    logger.info('Running OLAP query: %s', payload)
    return service.get_olap_query(payload)


# ---------------------------------------------------------------------------
# BI Dashboard overview: KPI cards + late-rate trend
# ---------------------------------------------------------------------------
@blp.route('/api/dashboard/overview', methods=['GET'])
@blp.arguments(req_OverviewSchema, location='query')
@blp.response(200, res_OverviewSchema)
@blp.alt_response(422, schema=StdErrorSchema, description="Invalid query parameters")
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def get_dashboard_overview(query_args):
    logger.info('Fetching dashboard overview with query: %s', query_args)
    return service.get_overview(query_args)


# ---------------------------------------------------------------------------
# Authentication (minimal, not secure by design)
# ---------------------------------------------------------------------------
@blp.route('/api/auth/login', methods=['POST'])
@blp.arguments(req_LoginSchema)
@blp.response(200, res_LoginSchema)
@blp.alt_response(401, schema=StdErrorSchema, description="Invalid credentials")
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def login(payload):
    logger.info('Login attempt for username: %s', payload.get('username'))
    username = service.login(payload['username'], payload['password'])
    if not username:
        abort(401, message='Invalid username or password')
    session['username'] = username
    return {'message': 'Login successful', 'username': username}


@blp.route('/api/auth/logout', methods=['POST'])
@blp.response(200, res_LogoutSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def logout():
    session.pop('username', None)
    return {'message': 'Logged out'}


@blp.route('/api/auth/me', methods=['GET'])
@blp.response(200, res_MeSchema)
@blp.alt_response(500, schema=StdErrorSchema, description="Unexpected error")
def current_user():
    username = session.get('username')
    return {'authenticated': username is not None, 'username': username}
