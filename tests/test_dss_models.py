import pytest

from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


def test_unique_order_route(o):
    assert not o.duplicated(["order_id", "route"]).any()


def test_delay_days_valid(o):
    assert o.delay_days.notna().all()
    assert ((o.delay_days > 0) == o.is_late).all()


def test_zero_cut_is_baseline(o):
    r = M.route_priority(o).route.iloc[0]
    s = M.scenario(o, r)
    assert abs(s["projected"] - s["baseline"]) < 1e-9


def test_sensitivity_monotone(o):
    r = M.route_priority(o).route.iloc[0]
    ser = [x["projected"] for x in M.sensitivity(o, r, "prep")]
    assert all(a >= b for a, b in zip(ser, ser[1:]))


def test_more_cut_does_not_increase_late_rate(o):
    r = M.route_priority(o).route.iloc[0]
    for stage in M.STAGES:
        rates = [M.scenario(o, r, {stage: x})["projected"] for x in (0, 1, 2, 5)]
        assert all(a >= b for a, b in zip(rates, rates[1:]))


def test_cut_is_clipped_by_actual_stage_time(o):
    r = M.route_priority(o).route.iloc[0]
    s = M.scenario(o, r, {"prep": 10_000})
    assert 0.0 <= s["projected"] <= s["baseline"]


def test_goal_seek_promise(o):
    r = M.route_priority(o).route.iloc[0]
    assert M.goal_seek_promise(o, r, 0.05)["late_after"] <= 0.05 + 1e-9


def test_goal_seek_cut_zero_when_target_already_met(o):
    r = M.route_priority(o).route.iloc[0]
    baseline = M.scenario(o, r)["baseline"]
    assert M.goal_seek_cut(o, r, "prep", target=baseline) == 0.0


def test_root_cause_contract(o):
    r = M.route_priority(o).route.iloc[0]
    rc = M.root_cause(o, r)
    assert rc["stage"] in M.STAGES
    assert rc["owner"] == M.OWNER[rc["stage"]]
    assert isinstance(rc["has_bottleneck"], bool)
    assert set(rc["excess"]) == set(M.STAGES)
    if rc["has_bottleneck"]:
        assert rc["recommendation"] == M.RULES[rc["stage"]]
    else:
        assert rc["recommendation"] == "Không có giai đoạn nào vượt mức trung bình hệ thống."


def test_root_cause_sp_sp_has_no_bottleneck(o):
    rc = M.root_cause(o, "SP->SP")
    assert rc["has_bottleneck"] is False
    assert rc["recommendation"] == "Không có giai đoạn nào vượt mức trung bình hệ thống."


def test_root_cause_sp_rj_bottleneck_is_transit(o):
    rc = M.root_cause(o, "SP->RJ")
    assert rc["has_bottleneck"] is True
    assert rc["stage"] == "transit"
    assert rc["recommendation"] == M.RULES["transit"]
