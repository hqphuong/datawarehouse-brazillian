import pandas as pd
import pytest

from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


def test_unique_order_route(o):
    assert not o.duplicated(["order_id", "route"]).any()


def test_wilson_interval_known_values():
    """Kiểm tra công thức Wilson 95% với vài giá trị tính trước."""
    lo, hi = M.wilson_interval(50, 100)
    assert lo == pytest.approx(0.403830, abs=1e-6)
    assert hi == pytest.approx(0.596170, abs=1e-6)

    lo, hi = M.wilson_interval(31, 124)
    assert lo == pytest.approx(0.1821, abs=5e-4)
    assert hi == pytest.approx(0.3329, abs=5e-4)


def test_low_sample_threshold_is_200_orders():
    """Cờ low_sample bật đúng khi orders < 200, tắt khi orders = 200."""
    routes = ["A->A"] * 199 + ["B->B"] * 200 + ["C->C"] * 1000
    late = [True] * 100 + [False] * 99 + [True] * 100 + [False] * 100 + [False] * 1000
    orders = pd.DataFrame(
        {
            "route": routes,
            "order_id": [f"o{i}" for i in range(len(routes))],
            "is_late": late,
        }
    )

    out = M.route_priority(orders, top=10).set_index("route")
    assert bool(out.loc["A->A", "low_sample"]) is True
    assert bool(out.loc["B->B", "low_sample"]) is False
    assert "C->C" not in out.index  # tuyến nền không bị gắn cờ


def test_default_top_contains_all_red_routes(o):
    """Top mặc định phải chứa mọi tuyến đỏ, và đỏ phải đứng trước vàng."""
    all_flagged = M.route_priority(o, top=len(o))
    default = M.route_priority(o)

    red_routes = set(all_flagged.loc[all_flagged.level == "red", "route"])
    assert red_routes
    assert red_routes <= set(default["route"])

    levels = default["level"].tolist()
    n_red = levels.count("red")
    assert levels == ["red"] * n_red + ["amber"] * (len(levels) - n_red)

    reds = default[default.level == "red"]
    assert reds["late_orders"].tolist() == sorted(
        reds["late_orders"].tolist(), reverse=True
    )


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


def test_sensitivity_base_cut_series_matches_projected(o):
    """series[cut_transit].projected phải bằng projected của scenario với cùng bộ cut."""
    route = "SP->RJ"
    cut = {"prep": 2, "transit": 1}
    # bottleneck của SP->RJ là transit
    cause = M.root_cause(o, route)
    assert cause["stage"] == "transit", "test giả định bottleneck là transit"

    projected_scenario = M.scenario(o, route, cut)["projected"]
    base_cut = {k: v for k, v in cut.items() if k != "transit"}
    series = M.sensitivity(o, route, "transit", base_cut=base_cut)

    # series[1] ứng với transit_cut=1 — phải khớp projected của scenario(cut)
    assert series[1]["cut"] == 1
    assert series[1]["projected"] == pytest.approx(projected_scenario)


def test_sensitivity_base_cut_none_unchanged(o):
    """Gọi sensitivity không truyền base_cut (mặc định None) phải cho kết quả như cũ."""
    route = M.route_priority(o).route.iloc[0]
    old = [
        {"cut": x, "projected": M.scenario(o, route, {"prep": x})["projected"]}
        for x in range(6)
    ]
    new = M.sensitivity(o, route, "prep")  # base_cut=None
    for a, b in zip(old, new):
        assert a["cut"] == b["cut"]
        assert a["projected"] == pytest.approx(b["projected"])
