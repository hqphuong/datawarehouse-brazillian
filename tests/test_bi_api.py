"""Tests for the BI endpoints ported from the team's Flask backend.

Replaces ``tests__test_flask_backend.py`` (marshmallow schemas, ``/openapi.json``,
Django model rows) with tests for the unified app: hand-written validation,
plain-dict rows and the ``{"message": ...}`` error contract.
"""

from __future__ import annotations

import datetime

import pytest

from dss import bi_service as S
from dss import bi_validation as V
from dss.api_errors import ApiError
from dss.app import create_app


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Period helpers and service logic
# ---------------------------------------------------------------------------
def test_generate_month_periods():
    periods = list(S.generate_month_periods(2017, 11, 2018, 2))
    assert periods == [(2017, 11), (2017, 12), (2018, 1), (2018, 2)]


def test_generate_quarter_periods():
    periods = list(S.generate_quarter_periods(2017, 3, 2018, 2))
    assert periods == [(2017, 3), (2017, 4), (2018, 1), (2018, 2)]


def test_get_kpi_zero_division(monkeypatch):
    monkeypatch.setattr(
        S.repo,
        "get_kpi",
        lambda filters=None: {
            "order_count": 0,
            "delay_count": 0,
            "complaint_count": 0,
            "avg_delivery_time": 0.0,
            "avg_freight": 0.0,
            "avg_score": 0.0,
        },
    )
    kpi = S.get_kpi()
    assert kpi["order_count"] == 0
    assert kpi["delay_rate"] == 0.0
    assert kpi["complaint_rate"] == 0.0


def test_get_kpi_calculation(monkeypatch):
    monkeypatch.setattr(
        S.repo,
        "get_kpi",
        lambda filters=None: {
            "order_count": 100,
            "delay_count": 8,
            "complaint_count": 4,
            "avg_delivery_time": 12.345,
            "avg_freight": 20.556,
            "avg_score": 4.123,
        },
    )
    kpi = S.get_kpi()
    assert kpi["order_count"] == 100
    assert kpi["delay_rate"] == 0.08
    assert kpi["complaint_rate"] == 0.04
    assert kpi["avg_delivery_time"] == 12.35
    assert kpi["avg_freight_cost"] == 20.56
    assert kpi["avg_score"] == 4.12


# ---------------------------------------------------------------------------
# Validation (previously marshmallow schemas)
# ---------------------------------------------------------------------------
def test_filter_args_valid():
    filters = V.filter_args(
        {"start_date": "2017-01-01", "end_date": "2017-12-31"}
    )
    assert filters["start_date"] == datetime.date(2017, 1, 1)
    assert filters["end_date"] == datetime.date(2017, 12, 31)


def test_filter_args_inverted_range_raises():
    with pytest.raises(ApiError) as exc:
        V.filter_args({"start_date": "2018-01-01", "end_date": "2017-01-01"})
    assert exc.value.status == 400
    assert "start_date must be before or equal to end_date" == exc.value.message


def test_filter_args_bad_date_raises():
    with pytest.raises(ApiError) as exc:
        V.filter_args({"start_date": "01/01/2017"})
    assert exc.value.status == 400
    assert "YYYY-MM-DD" in exc.value.message


def test_filter_args_ignores_unknown_keys():
    filters = V.filter_args({"bogus": "1", "customer_state": "SP"})
    assert filters["customer_state"] == "SP"
    assert "bogus" not in filters


def test_late_trend_query_defaults_and_choices():
    assert V.late_trend_query({})["granularity"] == "month"
    assert V.late_trend_query({"granularity": "quarter"})["granularity"] == "quarter"
    with pytest.raises(ApiError):
        V.late_trend_query({"granularity": "daily"})


def test_orders_query_bounds():
    loaded = V.orders_query({"page": "2", "page_size": "50"})
    assert loaded["page"] == 2
    assert loaded["page_size"] == 50

    with pytest.raises(ApiError):
        V.orders_query({"page": "0"})
    with pytest.raises(ApiError):
        V.orders_query({"page_size": "500"})
    with pytest.raises(ApiError):
        V.orders_query({"page": "abc"})


def test_seller_query_sort_validation():
    assert V.seller_query({"sort_by": "avg_prep_time"})["sort_by"] == "avg_prep_time"
    with pytest.raises(ApiError):
        V.seller_query({"sort_by": "invalid_metric"})


def test_alerts_query_severity_validation():
    assert V.alerts_query({"severity": "CRITICAL"})["severity"] == "CRITICAL"
    assert V.alerts_query({})["severity"] is None
    with pytest.raises(ApiError):
        V.alerts_query({"severity": "UNKNOWN"})


def test_overview_query_defaults_and_period_range():
    query = V.overview_query({})
    assert query["time_mode"] == "month"
    assert query["from_time"] is None
    assert query["to_time"] is None

    assert V.overview_query({"time_mode": "quarter"})["time_mode"] == "quarter"
    with pytest.raises(ApiError):
        V.overview_query({"time_mode": "day"})
    with pytest.raises(ApiError):
        V.overview_query({"from": "2018-01", "to": "2017-01"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "Kasane Teto" in res.get_json()["message"]


def test_customer_states_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        S, "get_customer_states", lambda: {"states": ["MG", "RJ", "SP"]}
    )
    res = client.get("/api/customer-states")
    assert res.status_code == 200
    assert res.get_json() == {"states": ["MG", "RJ", "SP"]}


def test_seller_states_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        S, "get_seller_states", lambda: {"states": ["PR", "SC", "SP"]}
    )
    res = client.get("/api/seller-states")
    assert res.status_code == 200
    assert res.get_json() == {"states": ["PR", "SC", "SP"]}


def test_orders_endpoint_pagination(client, monkeypatch):
    captured = {}

    def fake_get_orders(args):
        captured.update(args)
        return {
            "total": 1,
            "page": 1,
            "page_size": 10,
            "total_pages": 1,
            "orders": [{"order_id": "abc12345", "sla_status": "on_time"}],
        }

    monkeypatch.setattr(S, "get_orders", fake_get_orders)
    res = client.get("/api/orders?page=1&page_size=10")
    assert res.status_code == 200
    assert captured["page"] == 1
    assert captured["page_size"] == 10
    body = res.get_json()
    assert body["total"] == 1
    assert body["orders"][0]["order_id"] == "abc12345"


def test_orders_endpoint_validation_error_shape(client):
    res = client.get("/api/orders?page=0")
    assert res.status_code == 400
    body = res.get_json()
    assert set(body) == {"message"}
    assert isinstance(body["message"], str)


def test_unknown_query_params_ignored(client, monkeypatch):
    captured = {}

    def fake_sla(filters):
        captured.update(filters)
        return {
            "avg_approval_time": 0.0,
            "avg_prep_time": 0.0,
            "avg_transit_time": 0.0,
            "avg_delivery_time": 0.0,
        }

    monkeypatch.setattr(S, "get_sla_breakdown", fake_sla)
    res = client.get("/api/analytics/sla-breakdown?bogus=1&customer_state=SP")
    assert res.status_code == 200
    assert captured["customer_state"] == "SP"
    assert "bogus" not in captured


def test_method_not_allowed_is_json(client):
    res = client.post("/api/health")
    assert res.status_code == 405
    assert res.get_json() == {"message": "Method not allowed"}
