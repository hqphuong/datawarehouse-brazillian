import numpy as np
import pandas as pd
import pytest

from etl import dss_eval as E
from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


def test_backtest_contract(o):
    frame, summary = E.backtest(o, min_orders=30)

    assert list(frame.columns) == [
        "period",
        "next_period",
        "flagged_routes",
        "flagged_orders",
        "other_orders",
        "total_orders",
        "flagged_late_rate",
        "other_late_rate",
        "diff",
    ]
    assert len(frame) == 19
    assert summary["periods_considered"] == len(frame)
    assert summary["periods_evaluated"] == len(frame.dropna(subset=["diff"]))
    comparable = frame.dropna(subset=["diff"])
    assert summary["higher_periods"] == int((comparable["diff"] > 0).sum())
    assert 0 <= summary["higher_periods"] <= summary["periods_evaluated"]
    expected = np.average(
        comparable["diff"], weights=comparable["total_orders"]
    )
    assert summary["weighted_diff"] == pytest.approx(float(expected))
    assert summary["weighted_diff_basis"] == "total_orders"
    expected_flagged = np.average(
        comparable["diff"], weights=comparable["flagged_orders"]
    )
    assert summary["weighted_diff_flagged"] == pytest.approx(float(expected_flagged))


def test_backtest_historical_baseline_contract(o):
    frame, summary = E.backtest(o, min_orders=30, baseline=True)

    assert "baseline_diff" in frame.columns
    assert len(frame) == 19
    assert summary["baseline_periods_evaluated"] == len(
        frame.dropna(subset=["baseline_diff"])
    )
    assert (
        summary["baseline_better_periods"]
        + summary["dss_better_periods"]
        + summary["tied_periods"]
        == summary["paired_periods"]
    )
    assert summary["paired_periods"] <= summary["periods_evaluated"]
    # DSS phải tốt hơn baseline lịch sử trên trung bình có trọng số.
    assert summary["weighted_diff"] > summary["baseline_weighted_diff"]


def test_backtest_historical_baseline_through_contract(o):
    frame, summary = E.backtest(o, min_orders=30, baseline_through=True)

    assert "baseline_through_diff" in frame.columns
    assert summary["baseline_through_periods_evaluated"] == len(
        frame.dropna(subset=["baseline_through_diff"])
    )
    assert (
        summary["baseline_through_better_periods"]
        + summary["dss_better_vs_through_periods"]
        + summary["tied_vs_through_periods"]
        == summary["paired_through_periods"]
    )
    # Biến thể "through" dùng nhiều thông tin hơn nên sát DSS hơn baseline "prior",
    # nhưng DSS vẫn cao hơn về trung bình có trọng số.
    assert (
        summary["baseline_weighted_diff"]
        < summary["baseline_through_weighted_diff"]
        < summary["weighted_diff"]
    )
    # Số kỳ đã kiểm chứng độc lập với dữ liệu hiện tại.
    assert summary["baseline_through_higher_periods"] == 14
    assert summary["baseline_through_better_periods"] == 4
    assert summary["tied_vs_through_periods"] == 3


def test_backtest_handles_period_without_flagged_routes(o):
    two_months = o[o["period"].isin([201701, 201702])]
    frame, summary = E.backtest(two_months, min_orders=10**9)

    assert len(frame) == 1
    assert frame.iloc[0]["flagged_routes"] == 0
    assert np.isnan(frame.iloc[0]["flagged_late_rate"])
    assert np.isnan(frame.iloc[0]["diff"])
    assert summary["periods_without_flags"] == 1
    assert summary["periods_evaluated"] == 0
    assert summary["weighted_diff"] is None


def test_threshold_sensitivity_contract(o):
    table = E.threshold_sensitivity(o)

    assert len(table) == 24  # 4 mức min_orders × 6 cặp ngưỡng
    assert list(table.columns) == [
        "min_orders",
        "red",
        "amber",
        "flagged_routes",
        "red_routes",
        "amber_routes",
        "is_default",
    ]
    assert set(table["min_orders"]) == {50, 100, 150, 200}
    assert table.groupby("min_orders").size().eq(6).all()
    assert len(table[["red", "amber"]].drop_duplicates()) == 6
    assert table["is_default"].sum() == 4  # một dòng mặc định mỗi min_orders
    assert (table["flagged_routes"] == table["red_routes"] + table["amber_routes"]).all()

    # Mặc định 100 / 2,0 / 1,5 phải khớp con số đã công bố.
    default = table[(table["min_orders"] == 100) & table["is_default"]].iloc[0]
    assert default["flagged_routes"] == 14
    assert default["red_routes"] == 6
    assert default["amber_routes"] == 8

    # H8: tại min_orders=50, số tuyến gắn cờ chạy 7–30 trên 6 cặp ngưỡng.
    at50 = table[table["min_orders"] == 50]
    assert at50["flagged_routes"].min() == 7
    assert at50["flagged_routes"].max() == 30

    # Tại min_orders=100: 5 cặp quanh mặc định chạy 10–21; cặp siết cả hai
    # (2,5; 2,0) chỉ còn lõi 6 tuyến.
    at100 = table[table["min_orders"] == 100]
    strict = at100[(at100["red"] == 2.5) & (at100["amber"] == 2.0)]
    assert strict["flagged_routes"].iloc[0] == 6
    around = at100[~((at100["red"] == 2.5) & (at100["amber"] == 2.0))]
    assert around["flagged_routes"].min() == 10
    assert around["flagged_routes"].max() == 21


def test_top_routes_include_sp_rj(o):
    table = E.top_routes_report(o, n=3)

    assert len(table) == 3
    assert "SP->RJ" in set(table["route"])
    assert set(table["stage"]) == {"transit"}
    assert (table["has_bottleneck"]).all()
    for column in ("approval_cut_1", "prep_cut_5", "transit_cut_5"):
        assert column in table.columns


def test_negative_time_comparison_contract(o):
    table = E.negative_time_comparison(o, n=3)

    assert len(table) == 3
    assert set(table["route"]) == set(
        M.route_priority(o, top=3, ensure_red=False)["route"]
    )
    assert (table["stage_keep"] == table["stage_drop"]).all()
    assert (table["has_bottleneck_keep"] == table["has_bottleneck_drop"]).all()


def test_exact_sign_test_hand_example():
    result = E._exact_sign_test(pd.Series([1, 2, -1, -2, 0]))

    assert result["positive"] == 2
    assert result["negative"] == 2
    assert result["n_non_tie"] == 4
    assert result["p_one_sided"] == pytest.approx(0.6875)
    assert result["p_two_sided"] == pytest.approx(1.0)


def test_route_level_bootstrap_is_deterministic(o):
    first = E.route_level_bootstrap(o, reps=12, seed=42)
    second = E.route_level_bootstrap(o, reps=12, seed=42)

    assert first == second
    assert first["reps"] == 12
    assert first["routes_resampled"] > 0
    assert set(first["shares"]) == {
        "share_approval",
        "share_prep",
        "share_transit",
        "share_promise",
    }
