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


# Tỷ lệ trễ của giai đoạn kiểm tra mô hình ML (~5,98%). Không được dùng làm
# ngưỡng đỏ/vàng: route_priority nhân red/amber với tỷ lệ trễ chung (~8,07%).
TEST_PREVALENCE = 0.05979368707146828


def _orders_from_counts(specs, stages=None):
    """Tạo bảng đơn tối thiểu: mỗi spec là (route, số đơn, số đơn trễ)."""
    rows = []
    for route, n_orders, n_late in specs:
        for i in range(n_orders):
            rows.append(
                {
                    "route": route,
                    "order_id": f"{route}-{i}",
                    "is_late": i < n_late,
                    "approval": 1.0,
                    "prep": 1.0,
                    "transit": 1.0,
                }
            )
    frame = pd.DataFrame(rows)
    for route, values in (stages or {}).items():
        mask = frame["route"] == route
        for column, value in values.items():
            frame.loc[mask, column] = value
    return frame


def test_uncertain_threshold_and_independence_from_low_sample():
    """uncertain = ci_low dưới ngưỡng của chính level; không đi theo low_sample.

    Bốn tuyến cố ý tách bốn tổ hợp (low_sample, uncertain). Tuyến đỏ có CI
    cắt ngưỡng vẫn giữ level red.
    """
    frame = _orders_from_counts(
        [
            ("ZZ->ZZ", 20000, 1500),  # nền, dưới ngưỡng vàng
            ("SU->RE", 600, 280),  # đỏ, mẫu lớn, CI nằm trên ngưỡng
            ("CR->OS", 250, 50),  # đỏ, mẫu lớn, CI cắt ngưỡng đỏ
            ("SM->AL", 150, 70),  # đỏ, mẫu < 200, CI nằm trên ngưỡng
            ("AM->BG", 2000, 300),  # vàng, mẫu lớn, CI cắt ngưỡng vàng
            ("BO->TH", 130, 22),  # vàng, mẫu < 200, CI cắt ngưỡng vàng
        ]
    )
    overall = float(frame["is_late"].mean())
    red_thr = overall * 2.0
    amber_thr = overall * 1.5

    out = M.route_priority(frame).set_index("route")
    assert "ZZ->ZZ" not in out.index
    assert set(out.index) == {"SU->RE", "CR->OS", "SM->AL", "AM->BG", "BO->TH"}

    for route, row in out.iterrows():
        if row["late_rate"] >= red_thr:
            assert row["level"] == "red"
            threshold = red_thr
        else:
            assert row["level"] == "amber"
            assert row["late_rate"] >= amber_thr
            threshold = amber_thr
        lower, _ = M.wilson_interval(int(row["late_orders"]), int(row["orders"]))
        assert row["ci_low"] == pytest.approx(lower)
        assert bool(row["uncertain"]) is bool(lower < threshold)
        assert bool(row["low_sample"]) is bool(row["orders"] < 200)

    # CI cắt ngưỡng không kéo level xuống.
    assert out.loc["CR->OS", "level"] == "red"
    assert float(out.loc["CR->OS", "ci_low"]) < red_thr
    assert out.loc["AM->BG", "level"] == "amber"
    assert float(out.loc["AM->BG", "ci_low"]) < amber_thr

    assert bool(out.loc["SU->RE", "low_sample"]) is False
    assert bool(out.loc["SU->RE", "uncertain"]) is False
    assert bool(out.loc["CR->OS", "low_sample"]) is False
    assert bool(out.loc["CR->OS", "uncertain"]) is True
    assert bool(out.loc["SM->AL", "low_sample"]) is True
    assert bool(out.loc["SM->AL", "uncertain"]) is False
    assert bool(out.loc["BO->TH", "low_sample"]) is True
    assert bool(out.loc["BO->TH", "uncertain"]) is True


def test_uncertain_does_not_change_order_stage_or_bottleneck():
    """Cờ không đổi thứ tự đỏ-trước / late_orders, cũng không đổi root_cause."""
    frame = _orders_from_counts(
        [
            ("ZZ->ZZ", 20000, 1500),
            ("SU->RE", 600, 280),
            ("CR->OS", 250, 50),
            ("SM->AL", 150, 70),
            ("AM->BG", 2000, 300),
            ("BO->TH", 130, 22),
        ],
        stages={
            "CR->OS": {"transit": 8.0},
            "BO->TH": {"approval": 0.0, "prep": 0.0, "transit": 0.0},
        },
    )
    out = M.route_priority(frame).reset_index(drop=True)

    # AM->BG có nhiều đơn trễ hơn mọi tuyến đỏ trừ cách xếp theo level.
    # CR->OS là đỏ không chắc; nếu xếp uncertain lên trước thì nó đứng trên SU->RE.
    assert out["route"].tolist() == ["SU->RE", "SM->AL", "CR->OS", "AM->BG", "BO->TH"]
    assert int(out.loc[out["route"] == "AM->BG", "late_orders"].iloc[0]) > int(
        out.loc[out["route"] == "SU->RE", "late_orders"].iloc[0]
    )
    assert bool(out.loc[out["route"] == "CR->OS", "uncertain"].iloc[0]) is True
    assert out.loc[out["route"] == "CR->OS", "level"].iloc[0] == "red"

    cross = M.root_cause(frame, "CR->OS")
    assert cross["stage"] == "transit"
    assert cross["has_bottleneck"] is True
    assert "uncertain" not in cross

    both = M.root_cause(frame, "BO->TH")
    excess = {
        stage: float(frame.loc[frame["route"] == "BO->TH", stage].mean() - frame[stage].mean())
        for stage in M.STAGES
    }
    assert both["stage"] == max(excess, key=excess.get)
    assert both["has_bottleneck"] is False
    assert max(excess.values()) < 0


def test_uncertain_on_warehouse_uses_overall_rate_not_test_prevalence(o):
    """Ngưỡng trên kho thật là red/amber × tỷ lệ trễ chung ≈ 8,07%, không phải 5,98%."""
    overall = float(o["is_late"].mean())
    assert round(overall * 100, 2) == 8.07
    assert round(TEST_PREVALENCE * 100, 2) == 5.98
    assert abs(overall - TEST_PREVALENCE) > 0.02

    flagged = M.route_priority(o, top=len(o)).reset_index(drop=True)
    red_thr = overall * 2.0
    amber_thr = overall * 1.5
    # Khóa cứng các mốc đã xác nhận (dung sai 4 chữ số thập phân).
    assert overall == pytest.approx(0.0807, abs=1e-4)
    assert red_thr == pytest.approx(0.1615, abs=1e-4)
    assert amber_thr == pytest.approx(0.1211, abs=1e-4)
    wrong_red = TEST_PREVALENCE * 2.0
    wrong_amber = TEST_PREVALENCE * 1.5

    disagree = 0
    for row in flagged.itertuples(index=False):
        if row.late_rate >= red_thr:
            assert row.level == "red"
            threshold = red_thr
            wrong = wrong_red
        else:
            assert row.level == "amber"
            assert row.late_rate >= amber_thr
            threshold = amber_thr
            wrong = wrong_amber
        expected = bool(row.ci_low < threshold)
        assert bool(row.uncertain) is expected
        if bool(row.ci_low < wrong) != expected:
            disagree += 1
        assert bool(row.low_sample) is (row.orders < 200)

    assert disagree > 0

    pairs = {
        (bool(low), bool(unc))
        for low, unc in zip(flagged["low_sample"], flagged["uncertain"])
    }
    assert (False, True) in pairs
    assert (True, False) in pairs

    levels = flagged["level"].tolist()
    n_red = levels.count("red")
    assert levels == ["red"] * n_red + ["amber"] * (len(levels) - n_red)
    for level in ("red", "amber"):
        part = flagged.loc[flagged["level"] == level, "late_orders"]
        assert part.is_unique
        assert part.tolist() == sorted(part.tolist(), reverse=True)

    rank = flagged["level"].map({"red": 0, "amber": 1})
    by_flag = flagged.assign(_rank=rank).sort_values(
        ["_rank", "uncertain", "late_orders"],
        ascending=[True, False, False],
    )
    assert flagged["route"].tolist() != by_flag["route"].tolist()

    for row in flagged.itertuples(index=False):
        cause = M.root_cause(o, row.route)
        subset = o[o["route"] == row.route]
        excess = {
            stage: float(subset[stage].mean() - o[stage].mean()) for stage in M.STAGES
        }
        assert cause["stage"] == max(excess, key=excess.get)
        assert cause["has_bottleneck"] is (max(excess.values()) > 0)
        assert "uncertain" not in cause


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
