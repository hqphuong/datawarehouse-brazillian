"""
Unit tests for Flask Backend: Schemas, Service logic, and API Routes.
Ensures migrated Flask endpoints maintain functionality without live DB dependency.
"""

import datetime
from unittest.mock import patch, MagicMock
import pytest
from marshmallow import ValidationError

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema import (
    SafeDateField,
    req_FilterSchema,
    req_LateTrendSchema,
    req_OrdersQuerySchema,
    req_SellerQuerySchema,
    req_AlertsQuerySchema,
    res_KpiSchema,
    res_OrdersSchema,
)
import service
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ============================================================================
# 1. Schema Validation Tests
# ============================================================================

def test_safe_date_field_serialization():
    field = SafeDateField()
    assert field._serialize(None, "d", {}) is None
    assert field._serialize("2026-11-10", "d", {}) == "2026-11-10"
    d = datetime.date(2026, 11, 10)
    assert field._serialize(d, "d", {}) == "2026-11-10"


def test_filter_schema_valid_and_invalid():
    schema = req_FilterSchema()
    # Valid
    valid = schema.load({"start_date": "2017-01-01", "end_date": "2017-12-31"})
    assert valid["start_date"] == datetime.date(2017, 1, 1)

    # Inverted date range
    with pytest.raises(ValidationError):
        schema.load({"start_date": "2018-01-01", "end_date": "2017-01-01"})


def test_late_trend_schema():
    schema = req_LateTrendSchema()
    assert schema.load({})["granularity"] == "month"
    assert schema.load({"granularity": "quarter"})["granularity"] == "quarter"
    with pytest.raises(ValidationError):
        schema.load({"granularity": "daily"})


def test_orders_query_schema():
    schema = req_OrdersQuerySchema()
    loaded = schema.load({"page": 2, "page_size": 50})
    assert loaded["page"] == 2
    assert loaded["page_size"] == 50
    with pytest.raises(ValidationError):
        schema.load({"page": 0})
    with pytest.raises(ValidationError):
        schema.load({"page_size": 500})


def test_seller_query_schema():
    schema = req_SellerQuerySchema()
    loaded = schema.load({"sort_by": "avg_prep_time"})
    assert loaded["sort_by"] == "avg_prep_time"
    with pytest.raises(ValidationError):
        schema.load({"sort_by": "invalid_metric"})


def test_alerts_query_schema():
    schema = req_AlertsQuerySchema()
    loaded = schema.load({"severity": "CRITICAL"})
    assert loaded["severity"] == "CRITICAL"
    with pytest.raises(ValidationError):
        schema.load({"severity": "UNKNOWN"})


# ============================================================================
# 2. Service Logic Tests
# ============================================================================

def test_generate_month_periods():
    periods = list(service.generate_month_periods(2017, 11, 2018, 2))
    assert periods == [(2017, 11), (2017, 12), (2018, 1), (2018, 2)]


def test_generate_quarter_periods():
    periods = list(service.generate_quarter_periods(2017, 3, 2018, 2))
    assert periods == [(2017, 3), (2017, 4), (2018, 1), (2018, 2)]


@patch("service.repo.get_kpi")
def test_service_get_kpi_zero_division(mock_repo_kpi):
    mock_repo_kpi.return_value = {
        "order_count": 0,
        "delay_count": 0,
        "complaint_count": 0,
        "avg_delivery_time": 0.0,
        "avg_freight": 0.0,
        "avg_score": 0.0,
    }
    kpi = service.get_kpi()
    assert kpi["order_count"] == 0
    assert kpi["delay_rate"] == 0.0
    assert kpi["complaint_rate"] == 0.0


@patch("service.repo.get_kpi")
def test_service_get_kpi_calculation(mock_repo_kpi):
    mock_repo_kpi.return_value = {
        "order_count": 100,
        "delay_count": 8,
        "complaint_count": 4,
        "avg_delivery_time": 12.345,
        "avg_freight": 20.556,
        "avg_score": 4.123,
    }
    kpi = service.get_kpi()
    assert kpi["order_count"] == 100
    assert kpi["delay_rate"] == 0.08
    assert kpi["complaint_rate"] == 0.04
    assert kpi["avg_delivery_time"] == 12.35
    assert kpi["avg_freight_cost"] == 20.56
    assert kpi["avg_score"] == 4.12


# ============================================================================
# 3. Flask Route Integration Tests
# ============================================================================

def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "Kasane Teto" in res.get_json()["message"]


def test_openapi_spec(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    doc = res.get_json()
    assert doc["info"]["title"] == "Olist Logistics DSS API"
    assert "/api/dashboard/kpis" in doc["paths"]
    assert "/api/orders" in doc["paths"]
    assert "/api/analytics/sellers" in doc["paths"]


@patch("service.repo.get_customer_states")
def test_api_customer_states(mock_get_states, client):
    mock_get_states.return_value = ["MG", "RJ", "SP"]
    res = client.get("/api/customer-states")
    assert res.status_code == 200
    assert res.get_json() == {"states": ["MG", "RJ", "SP"]}


@patch("service.repo.get_seller_states")
def test_api_seller_states(mock_get_states, client):
    mock_get_states.return_value = ["PR", "SC", "SP"]
    res = client.get("/api/seller-states")
    assert res.status_code == 200
    assert res.get_json() == {"states": ["PR", "SC", "SP"]}


@patch("service.repo.get_orders")
def test_api_orders_pagination(mock_get_orders, client):
    dummy_order = MagicMock()
    dummy_order.order_id = "abc12345"
    dummy_order.order_date = datetime.date(2017, 5, 1)
    dummy_order.customer_state = "SP"
    dummy_order.seller_state = "RJ"
    dummy_order.approval_time_days = 0.5
    dummy_order.seller_prep_time_days = 1.2
    dummy_order.carrier_transit_time_days = 4.3
    dummy_order.total_delivery_time_days = 6.0
    dummy_order.review_score = 5
    dummy_order.is_late = False

    mock_get_orders.return_value = (1, [dummy_order])
    res = client.get("/api/orders?page=1&page_size=10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["orders"]) == 1
    assert data["orders"][0]["order_id"] == "abc12345"
    assert data["orders"][0]["sla_status"] == "on_time"
