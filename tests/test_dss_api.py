"""Flask API parity tests ported from backend/dss/tests.py (25 Django tests).

Adds the mocked empty-route-list case and an autouse fixture that isolates
action-log tests in memory (không xoá dữ liệu log thật).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import pandas as pd
import psycopg2
import pytest

from dss import db
from dss import service as S
from dss.app import create_app


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True})


@pytest.fixture()
def client(app):
    return app.test_client()


def _db_available() -> bool:
    try:
        db.count_actions()
        return True
    except psycopg2.Error:
        return False


DB_AVAILABLE = _db_available()


@pytest.fixture(autouse=True)
def clean_action_log(monkeypatch):
    """Dùng log giả để test không ghi/sửa/xoá bản ghi thật trong PostgreSQL."""
    rows = []

    def _now():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def insert(body, config=None):
        rows.append(
            {
                "id": len(rows) + 1,
                "created_at": _now(),
                "action": str(body.get("action", ""))[:40],
                "route": str(body.get("route", ""))[:20],
                "level": str(body.get("level", ""))[:10],
                "detail": json.dumps(body, ensure_ascii=False),
                "status": "recorded",
                "updated_at": _now(),
            }
        )

    def listing(config=None):
        return [dict(row) for row in reversed(rows)]

    def count(config=None):
        return len(rows)

    def update(action_id, status, config=None):
        for row in rows:
            if row["id"] == action_id:
                row["status"] = status
                row["updated_at"] = _now()
                return dict(row)
        return None

    monkeypatch.setattr(db, "insert_action", insert)
    monkeypatch.setattr(db, "list_actions", listing)
    monkeypatch.setattr(db, "count_actions", count)
    monkeypatch.setattr(db, "update_action_status", update)
    yield


@pytest.fixture()
def requires_db():
    if not DB_AVAILABLE:
        pytest.skip("PostgreSQL không sẵn sàng")


def _json(res):
    return res.get_json()


def test_routes_default_top_10(client):
    res = client.get("/api/dss/routes")
    assert res.status_code == 200
    rows = _json(res)
    assert len(rows) == 10
    assert set(rows[0]) == {
        "route",
        "orders",
        "late_orders",
        "late_rate",
        "level",
        "root_cause",
        "ci_low",
        "ci_high",
        "low_sample",
        "uncertain",
    }
    assert rows[0]["level"] in {"red", "amber"}
    assert "has_bottleneck" in rows[0]["root_cause"]


def test_routes_default_top_contains_all_red(client):
    rows = _json(client.get("/api/dss/routes"))
    all_rows = _json(client.get("/api/dss/routes?top=100"))

    red = {r["route"] for r in all_rows if r["level"] == "red"}
    assert red
    assert red <= {r["route"] for r in rows}
    assert rows[0]["level"] == "red"


def test_routes_wilson_fields_and_low_sample(client):
    params = S.brief_parameters()
    rows = _json(client.get("/api/dss/routes"))
    for row in rows:
        assert "ci_low" in row
        assert "ci_high" in row
        assert "low_sample" in row
        assert 0.0 <= row["ci_low"]
        assert row["ci_low"] <= row["late_rate"]
        assert row["late_rate"] <= row["ci_high"]
        assert row["ci_high"] <= 1.0
        assert isinstance(row["low_sample"], bool)
        assert row["low_sample"] == (
            row["orders"] < params["low_sample_threshold"]
        )


def test_routes_uncertain_uses_overall_rate_not_test_prevalence(client):
    """Cờ uncertain dùng tỷ lệ trễ chung ≈ 8,16%, không dùng 5,98% tập kiểm tra."""
    test_prevalence = 0.05979368707146828
    orders = S.O
    overall = float(orders["is_late"].mean())
    assert round(overall * 100, 2) == 8.16
    assert round(test_prevalence * 100, 2) == 5.98
    assert abs(overall - test_prevalence) > 0.02

    rows = _json(client.get("/api/dss/routes?top=100"))
    assert len(rows) == 14
    red_thr = overall * 2.0
    amber_thr = overall * 1.5
    disagree = 0
    for row in rows:
        assert isinstance(row["uncertain"], bool)
        if row["late_rate"] >= red_thr:
            assert row["level"] == "red"
            threshold = red_thr
            wrong = test_prevalence * 2.0
        else:
            assert row["level"] == "amber"
            assert row["late_rate"] >= amber_thr
            threshold = amber_thr
            wrong = test_prevalence * 1.5
        expected = row["ci_low"] < threshold
        assert row["uncertain"] is expected
        if (row["ci_low"] < wrong) is not expected:
            disagree += 1

        cause = S.M.root_cause(orders, row["route"])
        subset = orders[orders["route"] == row["route"]]
        excess = {
            stage: float(subset[stage].mean() - orders[stage].mean())
            for stage in S.M.STAGES
        }
        assert row["root_cause"]["stage"] == max(excess, key=excess.get)
        assert row["root_cause"]["has_bottleneck"] is (
            max(excess.values()) > 0
        )
        assert row["root_cause"]["stage"] == cause["stage"]
        assert row["root_cause"]["has_bottleneck"] is cause["has_bottleneck"]
        assert "uncertain" not in row["root_cause"]

    assert disagree > 0

    pairs = {(row["low_sample"], row["uncertain"]) for row in rows}
    assert (False, True) in pairs
    assert (True, False) in pairs

    levels = [row["level"] for row in rows]
    n_red = levels.count("red")
    assert levels == ["red"] * n_red + ["amber"] * (len(levels) - n_red)
    for level in ("red", "amber"):
        late_orders = [
            row["late_orders"] for row in rows if row["level"] == level
        ]
        assert len(late_orders) == len(set(late_orders))
        assert late_orders == sorted(late_orders, reverse=True)

    uncertain_first = sorted(
        rows,
        key=lambda row: (
            0 if row["level"] == "red" else 1,
            0 if row["uncertain"] else 1,
            -row["late_orders"],
        ),
    )
    assert [row["route"] for row in rows] != [
        row["route"] for row in uncertain_first
    ]


def test_routes_top_100_returns_all_flagged(client):
    res = client.get("/api/dss/routes?top=100")
    assert res.status_code == 200
    assert len(_json(res)) == 14


def test_routes_year_filter(client):
    res = client.get("/api/dss/routes?year=2018")
    assert res.status_code == 200
    rows = _json(res)
    assert all(r["orders"] > 0 for r in rows)


def test_routes_year_uses_full_period_base_rate(client):
    """?year= chỉ lọc tuyến; ngưỡng đỏ/vàng vẫn theo L toàn giai đoạn."""
    rows = _json(client.get("/api/dss/routes?year=2018&top=100"))
    assert rows
    for row in rows:
        if row["late_rate"] >= S.BASE_RATE * 2.0:
            assert row["level"] == "red"
        elif row["late_rate"] >= S.BASE_RATE * 1.5:
            assert row["level"] == "amber"
        else:
            pytest.fail(f"tuyến {row['route']} bị gắn cờ dưới ngưỡng toàn kỳ")


def test_brief_config_exposes_full_period_base_rate(client):
    body = _json(client.get("/api/dss/brief"))
    assert body["config"]["base_rate"] == pytest.approx(S.BASE_RATE, abs=1e-12)
    assert body["config"]["base_rate_label"] == "overall rate of the full period"


def test_routes_bad_year(client):
    res = client.get("/api/dss/routes?year=abc")
    assert res.status_code == 400
    assert "error" in _json(res)


def test_routes_empty_list_is_json_array(client, monkeypatch):
    """Mocked empty route list: endpoint must return [] and no error."""
    monkeypatch.setattr(
        S.M,
        "route_priority",
        lambda *args, **kwargs: pd.DataFrame(columns=["route"]),
    )
    res = client.get("/api/dss/routes")
    assert res.status_code == 200
    assert _json(res) == []


def test_scenario_sp_rj(client):
    res = client.get("/api/dss/scenario?" + urlencode({"route": "SP->RJ"}))
    assert res.status_code == 200
    body = _json(res)
    assert body["orders"] == 8016
    assert body["baseline"] == pytest.approx(0.157061, abs=1e-5)
    assert body["projected"] == pytest.approx(body["baseline"], abs=1e-12)
    assert body["bottleneck"] == "transit"
    assert body["has_bottleneck"] is True
    assert len(body["series"]) == 6
    assert "NaN" not in res.data.decode()


def test_scenario_with_cut(client):
    res = client.get(
        "/api/dss/scenario?" + urlencode({"route": "SP->RJ", "prep": 5})
    )
    assert res.status_code == 200
    body = _json(res)
    assert body["projected"] < body["baseline"]
    assert body["avoided"] > 0


def test_scenario_missing_route(client):
    res = client.get("/api/dss/scenario")
    assert res.status_code == 400


def test_scenario_unknown_route(client):
    res = client.get("/api/dss/scenario?" + urlencode({"route": "XX->YY"}))
    assert res.status_code == 400
    assert "error" in _json(res)


def test_promise_sp_rj(client):
    res = client.get(
        "/api/dss/promise?" + urlencode({"route": "SP->RJ", "target": 0.05})
    )
    assert res.status_code == 200
    body = _json(res)
    assert body["extra_days"] == 15
    assert body["late_after"] <= 0.05


def test_promise_missing_route(client):
    res = client.get("/api/dss/promise")
    assert res.status_code == 400


def test_actions_post_and_get(client, requires_db):
    payload = {
        "action": "extend_promise",
        "route": "SP->RJ",
        "level": "amber",
        "extra_days": 15,
    }
    res = client.post(
        "/api/dss/actions",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert _json(res) == {"ok": True}
    assert db.count_actions() == 1
    row = db.list_actions()[0]
    assert row["action"] == "extend_promise"
    assert row["route"] == "SP->RJ"
    assert row["level"] == "amber"
    assert json.loads(row["detail"])["extra_days"] == 15

    listing = client.get("/api/dss/actions")
    assert listing.status_code == 200
    assert len(_json(listing)) == 1


def test_actions_reject_invalid_json(client, requires_db):
    res = client.post(
        "/api/dss/actions",
        data="{not-json",
        content_type="application/json",
    )
    assert res.status_code == 400
    assert db.count_actions() == 0


def test_actions_patch_status_and_listing(client, requires_db):
    client.post(
        "/api/dss/actions",
        json={
            "action": "recommendation",
            "route": "SP->RJ",
            "level": "amber",
            "detail": "Rà soát tuyến SP->RJ.",
        },
    )
    created = _json(client.get("/api/dss/actions"))[0]
    assert isinstance(created["id"], int)
    assert created["status"] == "recorded"
    assert created["updated_at"]

    res = client.patch(f"/api/dss/actions/{created['id']}", json={"status": "done"})
    assert res.status_code == 200
    assert _json(res)["status"] == "done"

    listing = _json(client.get("/api/dss/actions"))
    assert listing[0]["id"] == created["id"]
    assert listing[0]["status"] == "done"
    assert listing[0]["updated_at"]

    undo = client.patch(
        f"/api/dss/actions/{created['id']}", json={"status": "recorded"}
    )
    assert undo.status_code == 200
    assert _json(undo)["status"] == "recorded"


def test_actions_patch_rejects_invalid_input(client, requires_db):
    res = client.patch("/api/dss/actions/1", json={"status": "unknown"})
    assert res.status_code == 400
    assert _json(res)["error"]

    missing = client.patch("/api/dss/actions/999", json={"status": "done"})
    assert missing.status_code == 404
    assert db.count_actions() == 0


def test_scenario_series_matches_projected_with_base_cut(client):
    """series[transit_cut].projected phải bằng projected khi cut kết hợp."""
    params = urlencode({"route": "SP->RJ", "prep": 2, "transit": 1})
    res = client.get(f"/api/dss/scenario?{params}")
    assert res.status_code == 200
    body = _json(res)
    assert body["bottleneck"] == "transit"
    series = body["series"]
    assert series[1]["cut"] == 1
    assert series[1]["projected"] == pytest.approx(
        body["projected"], abs=1e-12
    )


def test_brief_endpoint_includes_action_groups_and_notes(client):
    res = client.get("/api/dss/brief")
    assert res.status_code == 200
    body = _json(res)
    assert "route_actions" in body
    assert "seller_actions" in body
    assert "city" in body["seller_actions"][0]
    assert "state" in body["seller_actions"][0]
    assert "low_sample_actions" in body
    assert any(
        "đổi định nghĩa trễ, không rút ngắn thời gian giao" in note
        for note in body["notes"]
    )


def test_attribution_endpoint_accepts_supported_quantiles(client):
    for q in ("0.25", "0.5"):
        res = client.get(f"/api/dss/attribution?q={q}")
        assert res.status_code == 200
        body = _json(res)
        assert body["q"] == float(q)
        assert "rows" in body
        assert "shares_in_late_orders" in body["systemwide"]


def test_attribution_endpoint_ranked_routes_peer_fields(client):
    res = client.get("/api/dss/attribution?q=0.5")
    assert res.status_code == 200
    body = _json(res)
    assert body["grain"] == "order-route"
    assert "ranked_routes" in body
    rows = body["ranked_routes"]
    assert rows
    required = {
        "route",
        "order_routes",
        "orders",
        "late_rate",
        "expected_late_rate",
        "excess_pp",
        "excess_order_routes",
        "share_promise",
        "top_stage",
        "benchmark_peer_share",
    }
    assert required <= set(rows[0])
    excess = [row["excess_pp"] for row in rows]
    assert excess == sorted(excess, reverse=True)
    for row in rows[:10]:
        assert row["late_rate"] == pytest.approx(
            row["expected_late_rate"] + row["phi_total"], abs=1e-10
        )
        assert row["excess_pp"] == pytest.approx(
            row["phi_total"] * 100, abs=1e-8
        )
        assert row["order_routes"] >= row["orders"]
        assert row["top_stage"] in {"approval", "prep", "transit"}
        assert row["orders"] >= S.brief_parameters()["seller_min_orders"]


def test_attribution_endpoint_rejects_q75_with_reason(client):
    res = client.get("/api/dss/attribution?q=0.75")
    assert res.status_code == 400
    assert "q=0.75 bị loại" in _json(res)["error"]


def test_promise_policy_endpoint_labels_service_levels(client):
    res = client.get("/api/dss/promise-policy")
    assert res.status_code == 200
    body = _json(res)
    assert body["label"] == "mức phục vụ, không phải khuyến nghị đặt promise"
    assert {row["service_level"] for row in body["rows"]} == {
        0.85,
        0.9,
        0.95,
    }
    assert "không rút ngắn thời gian giao" in body["note"]


def test_sellers_endpoint_returns_single_seller_scorecard(client):
    res = client.get("/api/dss/sellers")
    assert res.status_code == 200
    body = _json(res)
    assert body["rows"]
    assert "segment" in body["rows"][0]
    assert "city" in body["rows"][0]
    assert "state" in body["rows"][0]
    assert body["summary"]["n_orders_single_seller"] > 0


def test_portfolio_endpoint_reports_half_late_order_coverage(client):
    res = client.get("/api/dss/portfolio")
    assert res.status_code == 200
    coverage = _json(res)["coverage_50_percent"]
    assert coverage["k"] == 102
    assert coverage["covered_share"] == pytest.approx(0.5010, abs=1e-4)
