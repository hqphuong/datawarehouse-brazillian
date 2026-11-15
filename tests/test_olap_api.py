"""Tests for ``/api/olap/*`` (ported from the team's Flask backend)."""

from __future__ import annotations

import pytest

from dss import bi_service as S
from dss import bi_validation as V
from dss.api_errors import ApiError
from dss.app import create_app

VALID_DIMENSION = "Dim_Location.state"
VALID_MEASURE = "total_orders"


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------
def test_payload_requires_dimensions_and_measures():
    with pytest.raises(ApiError):
        V.olap_payload({"measures": [VALID_MEASURE]})
    with pytest.raises(ApiError):
        V.olap_payload({"dimensions": [VALID_DIMENSION]})
    with pytest.raises(ApiError):
        V.olap_payload({"dimensions": [], "measures": [VALID_MEASURE]})


def test_payload_requires_list_of_strings():
    with pytest.raises(ApiError):
        V.olap_payload(
            {"dimensions": VALID_DIMENSION, "measures": [VALID_MEASURE]}
        )
    with pytest.raises(ApiError):
        V.olap_payload({"dimensions": [1], "measures": [VALID_MEASURE]})


def test_payload_rejects_unknown_dimension():
    with pytest.raises(ApiError) as exc:
        V.olap_payload(
            {"dimensions": ["Dim_Unknown.state"], "measures": [VALID_MEASURE]}
        )
    assert exc.value.status == 400
    assert "Unsupported dimension" in exc.value.message


def test_payload_rejects_unknown_measure():
    with pytest.raises(ApiError) as exc:
        V.olap_payload(
            {"dimensions": [VALID_DIMENSION], "measures": ["unknown_measure"]}
        )
    assert exc.value.status == 400
    assert "Unsupported measure" in exc.value.message


def test_payload_rejects_bad_filters():
    with pytest.raises(ApiError):
        V.olap_payload(
            {
                "dimensions": [VALID_DIMENSION],
                "measures": [VALID_MEASURE],
                "filters": ["SP"],
            }
        )


def test_payload_defaults_and_ignores_unknown_keys():
    payload = V.olap_payload(
        {
            "dimensions": [VALID_DIMENSION],
            "measures": [VALID_MEASURE],
            "unknown": "ignored",
            "filters": {"customer_states": ["SP"], "unknown": ["x"]},
        }
    )
    assert payload["time_mode"] == "month"
    assert payload["filters"] == {
        "customer_states": ["SP"],
        "seller_states": [],
        "categories": [],
    }
    assert "unknown" not in payload


def test_payload_period_range():
    with pytest.raises(ApiError):
        V.olap_payload(
            {
                "dimensions": [VALID_DIMENSION],
                "measures": [VALID_MEASURE],
                "from_time": "2017/01",
            }
        )
    with pytest.raises(ApiError):
        V.olap_payload(
            {
                "dimensions": [VALID_DIMENSION],
                "measures": [VALID_MEASURE],
                "from_time": "2018-01",
                "to_time": "2017-01",
            }
        )


# ---------------------------------------------------------------------------
# Service formatting
# ---------------------------------------------------------------------------
def test_get_olap_query_formats_rows(monkeypatch):
    captured = {}

    def fake_query(dimensions, measures, filters, date_from, date_to):
        captured["dimensions"] = dimensions
        captured["measures"] = measures
        return [
            {
                "customer_state": "SP",
                "month": None,
                "total_orders": 10,
                "late_rate": 12.3456,
            }
        ]

    monkeypatch.setattr(S.repo, "run_olap_query", fake_query)
    result = S.get_olap_query(
        {
            "dimensions": [VALID_DIMENSION, "Dim_Time.month"],
            "measures": [VALID_MEASURE, "late_rate"],
            "time_mode": "month",
            "filters": {"customer_states": ["SP"]},
        }
    )

    assert result["columns"] == ["customer_state", "month", "total_orders", "late_rate"]
    assert result["data"] == [
        {
            "customer_state": "SP",
            "month": None,
            "total_orders": 10,
            "late_rate": 12.35,
        }
    ]
    assert len(captured["dimensions"]) == 2
    assert len(captured["measures"]) == 2


def test_get_olap_query_null_values_become_zero(monkeypatch):
    monkeypatch.setattr(
        S.repo,
        "run_olap_query",
        lambda **kwargs: [{"customer_state": "SP", "total_orders": None}],
    )
    result = S.get_olap_query(
        {"dimensions": [VALID_DIMENSION], "measures": [VALID_MEASURE]}
    )
    assert result["data"][0]["total_orders"] == 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_metadata_endpoint(client, monkeypatch):
    payload = {
        "states": ["SP"],
        "categories": ["bed_bath_table"],
        "seller_states": ["RJ"],
        "time_range": {"min": "2016-09", "max": "2018-10"},
    }
    monkeypatch.setattr(S, "get_olap_metadata", lambda: payload)
    res = client.get("/api/olap/metadata")
    assert res.status_code == 200
    assert res.get_json() == payload


def test_query_endpoint(client, monkeypatch):
    captured = {}

    def fake_query(payload):
        captured.update(payload)
        return {"columns": ["customer_state", "total_orders"], "data": []}

    monkeypatch.setattr(S, "get_olap_query", fake_query)
    res = client.post(
        "/api/olap/query",
        json={
            "dimensions": [VALID_DIMENSION],
            "measures": [VALID_MEASURE],
            "from_time": "2017-01",
            "unknown": "ignored",
        },
    )
    assert res.status_code == 200
    assert res.get_json()["columns"] == ["customer_state", "total_orders"]
    assert captured["from_time"] == "2017-01"
    assert "unknown" not in captured


def test_query_endpoint_requires_json_object(client):
    res = client.post("/api/olap/query")
    assert res.status_code == 400
    assert set(res.get_json()) == {"message"}

    res = client.post("/api/olap/query", json=["not", "an", "object"])
    assert res.status_code == 400
    assert set(res.get_json()) == {"message"}


def test_query_endpoint_rejects_unknown_dimension(client):
    res = client.post(
        "/api/olap/query",
        json={"dimensions": ["nope"], "measures": [VALID_MEASURE]},
    )
    assert res.status_code == 400
    assert "Unsupported dimension" in res.get_json()["message"]


def test_query_endpoint_method_not_allowed(client):
    res = client.get("/api/olap/query")
    assert res.status_code == 405
    assert res.get_json() == {"message": "Method not allowed"}
