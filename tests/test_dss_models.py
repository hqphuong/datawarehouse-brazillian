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


# Tỷ lệ trễ của giai đoạn kiểm tra cũ (~5,98%). Không được dùng làm
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


def test_route_priority_overall_override_uses_full_period_rate():
    """``overall`` cố định ngưỡng đỏ/vàng, không phụ thuộc tỷ lệ của tập con."""
    frame = _orders_from_counts(
        [
            ("A->B", 1000, 200),  # 20% trễ
            ("C->D", 1000, 100),  # 10% trễ
        ]
    )
    # Tỷ lệ của chính frame = 15% → ngưỡng đỏ 30%, vàng 22,5%: không gắn cờ.
    assert len(M.route_priority(frame)) == 0

    # Mốc toàn giai đoạn 6% → ngưỡng đỏ 12%, vàng 9%: A->B đỏ, C->D vàng.
    out = M.route_priority(frame, overall=0.06).set_index("route")
    assert out.loc["A->B", "level"] == "red"
    assert out.loc["C->D", "level"] == "amber"


def test_low_sample_targets_overall_override():
    frame = _orders_from_counts([("A->B", 10, 1)])  # 10% trễ
    overridden = M.low_sample_targets(frame, min_orders=200, overall=0.04)
    assert overridden.loc[0, "level"] == "red"
    default = M.low_sample_targets(
        frame, min_orders=200, include_unflagged=True
    )
    assert default.loc[0, "level"] == "ok"


def test_route_flag_check_passes_overall_override():
    frame = _orders_from_counts(
        [
            ("A->B", 1000, 200),  # 20% trễ
            ("C->D", 1000, 100),  # 10% trễ
        ]
    )
    check = M.route_flag_check(
        frame, ["A->B", "C->D"], overall=0.06
    ).set_index("route")
    assert check.loc["A->B", "level"] == "red"
    assert check.loc["C->D", "level"] == "amber"


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
    """Ngưỡng trên kho thật là red/amber × tỷ lệ trễ chung ≈ 8,16%, không phải 5,98%."""
    overall = float(o["is_late"].mean())
    assert round(overall * 100, 2) == 8.16
    assert round(TEST_PREVALENCE * 100, 2) == 5.98
    assert abs(overall - TEST_PREVALENCE) > 0.02

    flagged = M.route_priority(o, top=len(o)).reset_index(drop=True)
    red_thr = overall * 2.0
    amber_thr = overall * 1.5
    # Khóa cứng các mốc đã xác nhận (dung sai 4 chữ số thập phân).
    assert overall == pytest.approx(0.0816, abs=1e-4)
    assert red_thr == pytest.approx(0.1631, abs=1e-4)
    assert amber_thr == pytest.approx(0.1223, abs=1e-4)
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


def test_d2_fields_and_weight_band(o):
    assert o.gmv.notna().all() and (o.gmv >= 0).all()
    assert o.promise_days.notna().all()
    assert o.seller_id.notna().all()
    assert o.attrs["promise_gap_max"] < 1e-9
    assert set(o.weight_band.unique()) == {"Q1", "Q2", "Q3", "Q4"}
    assert o.distance_km.notna().mean() > 0.99


def test_stage_invalid_excluded_from_stats():
    raw = M.load_orders(include_invalid=True)
    clean = M.load_orders()
    assert (clean[["approval", "prep", "transit"]] >= 0).all().all()
    assert not clean[["approval", "prep", "transit"]].isna().any().any()
    assert len(clean) + raw.attrs["excluded_stage_invalid_rows"] == len(raw)
    assert raw.attrs["excluded_stage_invalid_rows"] > 0
    assert raw.attrs["late_rate_order"] != raw.attrs["late_rate_order_route"]


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


def _seller_orders(seller, n_orders, n_late, late_review=5, ok_review=5):
    return pd.DataFrame(
        {
            "order_id": [f"{seller}-{i}" for i in range(n_orders)],
            "seller_id": seller,
            "route": "A->B",
            "is_late": [i < n_late for i in range(n_orders)],
            "gmv": 10.0,
            "review_score": [
                late_review if i < n_late else ok_review for i in range(n_orders)
            ],
        }
    )


def test_single_seller_filter_and_exclusion_shares():
    single = pd.concat(
        [
            _seller_orders("S1", 4, 1),
            _seller_orders("S2", 3, 2),
        ],
        ignore_index=True,
    )
    multi = pd.DataFrame(
        {
            "order_id": ["M1", "M1", "M2", "M2"],
            "seller_id": ["S1", "S2", "S1", "S2"],
            "route": "A->B",
            "is_late": [True, True, False, False],
            "gmv": 10.0,
            "review_score": 5,
        }
    )
    missing = pd.DataFrame(
        {
            "order_id": ["X1"],
            "seller_id": [float("nan")],
            "route": "A->B",
            "is_late": [True],
            "gmv": 10.0,
            "review_score": 5,
        }
    )
    frame = pd.concat([single, multi, missing], ignore_index=True)

    order, stats = M._single_seller_orders(frame)
    assert len(order) == 7
    assert set(order["order_id"]) == set(single["order_id"])
    assert stats["n_orders_total"] == 10
    assert stats["n_orders_single_seller"] == 7
    assert stats["n_orders_multi_seller"] == 2
    assert stats["n_orders_missing_seller"] == 1
    assert stats["excluded_order_share"] == pytest.approx(3 / 10)
    assert stats["n_order_routes_total"] == 12
    assert stats["n_order_routes_single_seller"] == 7
    assert stats["excluded_order_route_share"] == pytest.approx(5 / 12)
    assert stats["system_late_rate"] == pytest.approx(3 / 7)


def test_seller_scorecard_metrics_ci_level_segment():
    # Hệ thống (single-seller) = 103/420 = 24,52%.
    frame = pd.concat(
        [
            _seller_orders("A", 100, 50, late_review=1),
            _seller_orders("B", 100, 5),
            _seller_orders("C", 100, 0),
            _seller_orders("D", 20, 20),
            _seller_orders("E", 100, 28),
        ],
        ignore_index=True,
    )
    card = M.seller_scorecard(frame, min_orders=30)
    assert len(card) == 5
    assert card.attrs["n_orders_total"] == 420
    assert card.attrs["system_late_rate"] == pytest.approx(103 / 420)
    assert card.attrs["n_sellers_scored"] == 4

    row = card.set_index("seller_id")
    a = row.loc["A"]
    assert a["orders"] == 100
    assert a["late_orders"] == 50
    assert a["late_rate"] == pytest.approx(0.5)
    lo, hi = M.wilson_interval(50, 100)
    assert a["wilson_low"] == pytest.approx(lo)
    assert a["wilson_high"] == pytest.approx(hi)
    assert a["level"] == "red"
    assert a["segment"] == "ưu tiên"
    assert a["bad_review_rate"] == pytest.approx(0.5)

    # B thấp hơn hệ thống rõ rệt.
    assert row.loc["B", "level"] == "ok"
    assert row.loc["B", "segment"] == "ổn định"
    assert row.loc["B", "ci_status"] == "thấp hơn hệ thống"
    assert row.loc["B", "bad_review_rate"] == pytest.approx(0.0)

    # E trên hệ thống nhưng CI còn chứa hệ thống -> amber, vẫn ưu tiên.
    assert row.loc["E", "late_rate"] == pytest.approx(0.28)
    assert row.loc["E", "wilson_low"] < card.attrs["system_late_rate"]
    assert row.loc["E", "level"] == "amber"
    assert row.loc["E", "segment"] == "ưu tiên"

    # D mẫu nhỏ: vẫn có level theo luật nhưng bị tách khỏi nhóm ưu tiên.
    assert row.loc["D", "orders"] == 20
    assert bool(row.loc["D", "low_sample"]) is True
    assert row.loc["D", "level"] == "red"
    assert row.loc["D", "segment"] == "cần thêm dữ liệu"

    assert card["late_orders"].is_monotonic_decreasing
    assert card["late_orders_share"].sum() == pytest.approx(1.0)
    assert card["gmv_share"].sum() == pytest.approx(1.0)
    assert card.attrs["level_counts"]["red"] == 2
    assert card.attrs["segment_counts"]["cần thêm dữ liệu"] == 1


def test_seller_portfolio_segments_and_top_shares():
    frame = pd.concat(
        [
            _seller_orders("A", 100, 50),
            _seller_orders("B", 100, 5),
            _seller_orders("C", 100, 0),
            _seller_orders("D", 20, 20),
            _seller_orders("E", 100, 28),
        ],
        ignore_index=True,
    )
    card = M.seller_scorecard(frame, min_orders=30)
    port = M.seller_portfolio(frame, min_orders=30, top=2, scorecard=card)
    summary = port["summary"]
    assert summary["n_sellers"] == 5
    assert summary["orders"] == 420
    assert summary["late_orders"] == 103
    assert summary["late_rate"] == pytest.approx(103 / 420)
    assert summary["top_n"] == 2
    assert summary["top_seller_share_late_orders"] == pytest.approx(78 / 103)
    assert summary["top_seller_share_gmv"] == pytest.approx(2000 / 4200)
    assert summary["k_sellers_cover_50pct_late"] == 2
    assert summary["late_orders_covered_50pct"] == 78
    assert summary["late_orders_covered_50pct_share"] == pytest.approx(78 / 103)

    segments = port["segments"].set_index("segment")
    assert set(segments.index) == {"ưu tiên", "ổn định", "cần thêm dữ liệu"}
    assert segments.loc["ưu tiên", "n_sellers"] == 2
    assert segments.loc["ưu tiên", "late_orders"] == 78
    assert segments.loc["cần thêm dữ liệu", "orders"] == 20
    assert segments["orders"].sum() == 420
    assert segments["late_orders"].sum() == 103
    assert segments["late_orders_share"].sum() == pytest.approx(1.0)

    top = port["top_sellers"]
    assert list(top["seller_id"]) == ["A", "E"]
    assert list(top["late_orders"]) == [50, 28]


def test_sellers_covering_late_share_contract():
    """k nhỏ nhất phủ 50% đơn trễ; hòa phá bằng orders."""
    frame = pd.concat(
        [
            _seller_orders("A", 100, 50),
            _seller_orders("B", 100, 5),
            _seller_orders("C", 100, 0),
            _seller_orders("D", 20, 20),
            _seller_orders("E", 100, 28),
        ],
        ignore_index=True,
    )
    card = M.seller_scorecard(frame, min_orders=30)
    cover = M.sellers_covering_late_share(card, target=0.5)
    # late_orders: A=50, E=28, D=20, B=5, C=0; total=103; 50% = 51,5.
    assert cover["k"] == 2
    assert cover["covered_late_orders"] == 78
    assert cover["total_late_orders"] == 103
    assert cover["covered_share"] == pytest.approx(78 / 103)
    assert cover["remaining_late_orders"] == 25
    assert cover["seller_ids"] == ["A", "E"]

    assert M.sellers_covering_late_share(card, target=0.4)["k"] == 1
    # Seller C có 0 đơn trễ nên không cần cho target=1,0.
    assert M.sellers_covering_late_share(card, target=1.0)["k"] == 4
    with pytest.raises(ValueError):
        M.sellers_covering_late_share(card, target=0)
    with pytest.raises(ValueError):
        M.sellers_covering_late_share(card.drop(columns=["late_orders"]))


def test_seller_scorecard_rejects_bad_input():
    with pytest.raises(ValueError):
        M.seller_scorecard(pd.DataFrame())
    with pytest.raises(ValueError):
        M.seller_scorecard(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        M.seller_scorecard(_seller_orders("A", 3, 1), min_orders=0)
    with pytest.raises(ValueError):
        M.seller_portfolio(_seller_orders("A", 3, 1), top=0)
    card = M.seller_scorecard(_seller_orders("A", 3, 1), min_orders=1)
    with pytest.raises(ValueError):
        M.seller_portfolio(
            _seller_orders("A", 3, 1), scorecard=card.drop(columns=["level"])
        )


def test_low_sample_targets_split_without_changing_route_priority():
    frame = _orders_from_counts(
        [
            ("ZZ->ZZ", 2000, 100),  # nền, tỷ lệ chung ~7,06%
            ("BIG->OK", 200, 0),  # đúng ngưỡng, không thuộc nhóm mẫu nhỏ
            ("MA->SP", 118, 30),  # đỏ tạm, thiếu 82 đơn
            ("PR->BA", 144, 40),  # đỏ tạm, thiếu 56 đơn
            ("SP->TO", 195, 22),  # vàng tạm, thiếu 5 đơn
            ("OK->SM", 50, 1),  # mẫu nhỏ nhưng không có tín hiệu
        ]
    )
    low = M.low_sample_targets(frame)
    assert list(low["route"]) == ["PR->BA", "MA->SP", "SP->TO"]
    assert list(low["level"]) == ["red", "red", "amber"]
    assert (low["status"] == "cần thêm dữ liệu").all()
    assert (low["orders"] < 200).all()
    assert list(low["needed_orders"]) == [56, 82, 5]
    assert low.attrs["min_orders"] == 200
    assert low.attrs["n_routes_total"] == 6
    assert low.attrs["n_low_sample"] == 4
    assert low.attrs["n_low_sample_candidates"] == 3
    assert low.attrs["n_low_sample_late_orders"] == 30 + 40 + 22 + 1
    assert low.attrs["n_candidate_late_orders"] == 30 + 40 + 22

    # Không đổi route_priority: các tuyến mẫu nhỏ vẫn được gắn cờ như trước,
    # không bị trộn thêm cột/nhóm "cần thêm dữ liệu".
    priority = M.route_priority(frame)
    assert set(priority["route"]) == {"PR->BA", "MA->SP", "SP->TO"}
    assert "status" not in priority.columns
    assert priority["low_sample"].all()

    all_low = M.low_sample_targets(frame, include_unflagged=True)
    assert set(all_low["route"]) == {"MA->SP", "PR->BA", "SP->TO", "OK->SM"}
    assert len(M.low_sample_targets(frame, top=2)) == 2
    assert len(M.low_sample_targets(frame, top=0)) == 3


def test_route_flag_check_named_routes():
    frame = _orders_from_counts(
        [
            ("ZZ->ZZ", 2000, 100),
            ("BIG->OK", 200, 0),
            ("MA->SP", 118, 30),
            ("PR->BA", 144, 40),
            ("SP->TO", 195, 22),
            ("OK->SM", 50, 1),
        ]
    )
    check = M.route_flag_check(
        frame,
        ["MA->SP", "PR->BA", "SP->TO", "OK->SM"],
        min_orders=100,
        low_sample_threshold=200,
    )
    by_route = check.set_index("route")
    for route in ("MA->SP", "PR->BA", "SP->TO"):
        assert bool(by_route.loc[route, "in_flagged"]) is True
        assert bool(by_route.loc[route, "low_sample"]) is True
        assert by_route.loc[route, "status"] == "cần thêm dữ liệu"
    assert by_route.loc["MA->SP", "needed_orders"] == 82
    assert by_route.loc["PR->BA", "needed_orders"] == 56
    assert by_route.loc["SP->TO", "needed_orders"] == 5
    # red xếp trước theo late_orders: PR->BA (40), MA->SP (30), rồi amber SP->TO (22).
    assert by_route.loc["PR->BA", "flagged_rank"] == 1
    assert by_route.loc["MA->SP", "flagged_rank"] == 2
    assert by_route.loc["SP->TO", "flagged_rank"] == 3

    assert bool(by_route.loc["OK->SM", "in_flagged"]) is False
    assert by_route.loc["OK->SM", "level"] == "ok"
    assert by_route.loc["OK->SM", "status"] == "cần thêm dữ liệu"
    assert check.attrs["n_flagged_total"] == 3
    assert set(check.attrs["flagged_routes"]) == {"MA->SP", "PR->BA", "SP->TO"}

    with pytest.raises(ValueError):
        M.route_flag_check(pd.DataFrame(), ["MA->SP"])
    with pytest.raises(ValueError):
        M.route_flag_check(frame, ["MA->SP"], min_orders=0)
    with pytest.raises(ValueError):
        M.route_flag_check(frame, ["MA->SP"], low_sample_threshold=0)


def test_low_sample_targets_rejects_bad_input():
    with pytest.raises(ValueError):
        M.low_sample_targets(pd.DataFrame())
    with pytest.raises(ValueError):
        M.low_sample_targets(_orders_from_counts([("A->B", 10, 1)]), min_orders=0)
    with pytest.raises(ValueError):
        M.low_sample_targets(_orders_from_counts([("A->B", 10, 1)]), top=-1)
