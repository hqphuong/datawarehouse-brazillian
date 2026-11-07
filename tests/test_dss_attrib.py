import math

import numpy as np
import pandas as pd
import pytest

from etl import dss_attrib as A
from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


@pytest.fixture(scope="module")
def attributed(o):
    return A.attribute(o, A.fit_benchmarks(o))


def _orders(
    n,
    route="A->B",
    start_km=1.0,
    step_km=1.0,
    approval=1.0,
    prep=2.0,
    transit=3.0,
    promise=7.0,
    payment_type="credit_card",
    weight_band="Q1",
):
    rows = []
    for i in range(n):
        rows.append(
            {
                "order_id": f"{route}-{i}",
                "route": route,
                "distance_km": start_km + i * step_km,
                "approval": approval,
                "prep": prep,
                "transit": transit,
                "promise_days": promise,
                "total_lead_days": approval + prep + transit,
                "delay_days": approval + prep + transit - promise,
                "is_late": approval + prep + transit > promise,
                "review_score": 1 if i % 3 == 0 else 5,
                "gmv": 100.0,
                "payment_type": payment_type,
                "weight_band": weight_band,
            }
        )
    return pd.DataFrame(rows)


def _benchmark(
    route="A->B",
    band="D1",
    weight_band="Q1",
    payment_type="credit_card",
    b=(0.5, 0.5, 1.0),
):
    return pd.DataFrame(
        [
            {
                "route": route,
                "distance_band": band,
                "weight_band": weight_band,
                "payment_type": payment_type,
                "n_orders": 100,
                "b_approval": b[0],
                "b_prep": b[1],
                "b_transit": b[2],
                "benchmark_level_approval": "peer",
                "benchmark_level_prep": "peer",
                "benchmark_level_transit": "peer",
                "benchmark_level": "peer",
            }
        ]
    )


def test_shapley_hand_example():
    o = pd.DataFrame(
        [
            {
                "order_id": "o1",
                "route": "A->B",
                "distance_km": 10.0,
                "weight_band": "Q1",
                "payment_type": "credit_card",
                "approval": 2.0,
                "prep": 1.0,
                "transit": 1.0,
                "promise_days": 2.0,
                "total_lead_days": 4.0,
                "delay_days": 2.0,
                "is_late": True,
                "review_score": 1,
                "gmv": 100.0,
            }
        ]
    )
    a = A.attribute(o, _benchmark(b=(0.5, 0.5, 1.0)))
    row = a.iloc[0]
    assert row.phi_approval == pytest.approx(0.5)
    assert row.phi_prep == pytest.approx(0.5)
    assert row.phi_transit == pytest.approx(0.0)
    assert row.late_actual == 1
    assert row.late_benchmark == 0
    assert row.residual_promise_days == pytest.approx(0.0)
    assert A.check_attrib(a)["passed"]


def test_shapley_symmetry_and_null_player():
    # approval và prep vượt benchmark giống nhau -> phi bằng nhau; transit đạt benchmark -> phi = 0.
    actual = pd.DataFrame({"approval": [2.2], "prep": [2.2], "transit": [1.0]})
    bench = pd.DataFrame({"approval": [1.0], "prep": [1.0], "transit": [1.0]})
    phi, late_actual, late_bench = A._shapley_orders(actual, bench, pd.Series([3.0]))
    assert late_actual[0] == 1
    assert late_bench[0] == 0
    assert phi["approval"][0] == pytest.approx(phi["prep"][0])
    assert phi["transit"][0] == pytest.approx(0.0)
    assert sum(phi[s][0] for s in A.STAGES) == pytest.approx(1.0)


def test_transit_benchmark_is_cross_route_peer():
    # Hai tuyến cùng dải khoảng cách: benchmark transit phải là median gộp
    # xuyên tuyến (15), không phải median nội bộ từng tuyến (10 và 20).
    o = pd.concat(
        [
            _orders(40, "A->X", 1.0, transit=10.0),
            _orders(40, "B->X", 1.0, transit=20.0),
        ]
    )
    b = A.fit_benchmarks(o, min_orders=30, distance_bands=2)
    a = A.attribute(o, b)
    for route in ("A->X", "B->X"):
        values = a.loc[a["route"] == route, "b_transit"]
        assert values.nunique() == 1
        assert values.iloc[0] == pytest.approx(15.0)


def test_fit_benchmarks_fallback_per_stage():
    o = pd.concat(
        [
            _orders(100, "R1->X", 1.0, payment_type="credit_card", weight_band="Q1"),
            _orders(5, "R2->X", 1.0, payment_type="boleto", weight_band="Q9"),
        ]
    )
    b = A.fit_benchmarks(o, min_orders=30, distance_bands=10)
    approval = b.attrs["stage_benchmarks"]["approval"].set_index("payment_type")
    assert approval.loc["credit_card", "benchmark_level_approval"] == "peer"
    assert approval.loc["boleto", "benchmark_level_approval"] == "global"

    prep = b.attrs["stage_benchmarks"]["prep"].set_index("weight_band")
    assert prep.loc["Q1", "benchmark_level_prep"] == "peer"
    assert prep.loc["Q9", "benchmark_level_prep"] == "global"

    # 10 decile trên 105 đơn -> mỗi decile ~10 đơn < 30: transit fallback global.
    assert set(b["benchmark_level_transit"]) == {"global"}


def test_fit_benchmarks_rejects_bad_input():
    with pytest.raises(ValueError):
        A.fit_benchmarks(pd.DataFrame({"route": []}))
    with pytest.raises(ValueError):
        A.fit_benchmarks(_orders(3).drop(columns=["distance_km"]))
    with pytest.raises(ValueError):
        A.fit_benchmarks(_orders(3), quantile=1.0)


def test_attribute_preserves_benchmark_fallback_level():
    o = _orders(40, "R1->X")
    b = A.fit_benchmarks(o, min_orders=1000)  # mọi nhóm đều < 1000
    assert set(b["benchmark_level_approval"]) == {"global"}
    assert set(b["benchmark_level_prep"]) == {"global"}
    assert set(b["benchmark_level_transit"]) == {"global"}
    a = A.attribute(o, b)
    assert set(a["benchmark_level_approval"]) == {"global"}
    assert set(a["benchmark_level_prep"]) == {"global"}
    assert set(a["benchmark_level_transit"]) == {"global"}


def test_benchmarks_cover_every_order(attributed):
    assert not attributed[A.BENCH_COLS].isna().any().any()
    assert set(attributed["benchmark_level"]).issubset({"peer", "global", "mixed"})
    assert (attributed["late_actual"] == attributed["is_late"].astype(int)).all()


def test_attribution_invariants_on_real_data(attributed):
    checks = A.check_attrib(attributed)
    assert checks["l1_row_efficiency"], checks
    assert checks["l2_aggregate_efficiency"], checks
    assert checks["l3_validity"], checks
    assert checks["passed"]


def test_check_attrib_detects_tampering(attributed):
    bad = attributed.copy()
    bad.loc[bad.index[0], "phi_approval"] += 0.1
    checks = A.check_attrib(bad)
    assert not checks["l1_row_efficiency"]
    assert not checks["l2_aggregate_efficiency"]


def test_attribution_summary_reconstructs_late_rate(attributed):
    s = A.attribution_summary(attributed, min_orders=30)
    assert len(s) > 0
    assert s["efficiency_error"].abs().max() < 1e-12
    assert s["phi_total"].notna().all()
    assert set(s["top_stage"]).issubset(set(A.STAGES))
    positive = s[s["phi_total"] > 0]
    stage_share_sum = positive[[f"share_{x}" for x in A.STAGES]].sum(axis=1)
    assert np.allclose(stage_share_sum, 1.0, atol=1e-12)
    caused = s[s["late_rate"] > 0]
    cause_cols = [f"cause_share_{x}" for x in A.STAGES] + ["share_promise"]
    assert np.allclose(caused[cause_cols].sum(axis=1), 1.0, atol=1e-12)


def test_bad_review_uplift_contract():
    o = pd.DataFrame(
        {
            "late_actual": [1, 1, 1, 0, 0],
            "review_score": [1, 1, 5, 1, 5],
        }
    )
    r = A.bad_review_uplift(o)
    assert r["n_late"] == 3 and r["n_ontime"] == 2
    assert r["bad_review_rate_late"] == pytest.approx(2 / 3)
    assert r["bad_review_rate_ontime"] == pytest.approx(1 / 2)
    assert r["absolute_uplift_pp"] == pytest.approx((2 / 3 - 1 / 2) * 100)

    o.loc[len(o)] = [1, np.nan]
    r = A.bad_review_uplift(o)
    assert r["n_missing_review"] == 1


def _calibration_cell(route, weight_band, leads, promise):
    return pd.DataFrame(
        {
            "order_id": [f"{route}-{weight_band}-{i}" for i in range(len(leads))],
            "route": route,
            "weight_band": weight_band,
            "promise_days": promise,
            "total_lead_days": leads,
            "is_late": [lead > promise for lead in leads],
        }
    )


def test_promise_calibration_labels_and_avoidable():
    # 95 đơn lead=3, 5 đơn lead=10 -> Q95=3.35, needed=ceil=4.
    # tight: promise=2 -> gap=-2 < -0.5; 95 đơn trễ 3 ngày tránh được.
    tight = _calibration_cell("T->X", "Q1", [3] * 95 + [10] * 5, promise=2)
    # loose: promise=5 -> gap=+3 > +0.5; các đơn trễ đều lead=10 > needed.
    loose = _calibration_cell("L->X", "Q1", [1] * 95 + [10] * 5, promise=5)
    # ok: promise=4 = needed -> gap=0.
    ok = _calibration_cell("O->X", "Q1", [3] * 95 + [10] * 5, promise=4)
    small = _calibration_cell("S->X", "Q1", [1] * 50, promise=1)
    o = pd.concat([tight, loose, ok, small], ignore_index=True)

    c = A.promise_calibration(o, min_orders=100, tolerance_days=0.5)
    labels = c.set_index("route")["label"].to_dict()
    assert labels == {"T->X": "tight", "L->X": "loose", "O->X": "ok"}
    assert c.set_index("route").loc["T->X", "needed_days"] == 4
    assert c.set_index("route").loc["T->X", "gap_days"] == pytest.approx(-2)
    assert c.set_index("route").loc["T->X", "avoidable_orders"] == 95
    assert c.set_index("route").loc["L->X", "avoidable_orders"] == 0
    assert c.set_index("route").loc["O->X", "avoidable_orders"] == 0

    assert c.attrs["n_cells_total"] == 4
    assert c.attrs["n_cells_kept"] == 3
    assert c.attrs["n_cells_small"] == 1
    assert c.attrs["n_orders_small_cells"] == 50
    assert c.attrs["avoidable_orders"] == 95
    assert c.attrs["label_counts"] == {"tight": 1, "ok": 1, "loose": 1}


def test_promise_calibration_real_data(o):
    c = A.promise_calibration(o)
    assert len(c) > 0
    assert (c["n_orders"] >= 100).all()
    assert set(c["label"]).issubset(set(A.PROMISE_LABELS))
    assert (c["avoidable_orders"] <= c["late_orders"]).all()
    assert c["avoidable_orders"].sum() == c.attrs["avoidable_orders"]
    assert c.attrs["n_orders_kept"] == c["n_orders"].sum()
    assert sum(c.attrs["label_counts"].values()) == len(c)
    assert (c.loc[c["label"] == "tight", "gap_days"] < -c.attrs["tolerance_days"]).all()
    assert (c.loc[c["label"] == "loose", "gap_days"] > c.attrs["tolerance_days"]).all()
    assert (
        c.loc[c["label"] == "ok", "gap_days"].abs() <= c.attrs["tolerance_days"]
    ).all()
    row = c.iloc[0]
    sub = o[
        (o["route"] == row["route"])
        & (o["weight_band"].astype(str) == row["weight_band"])
    ]
    assert row["needed_days"] == math.ceil(sub["total_lead_days"].quantile(0.95))


def test_promise_calibration_rejects_bad_input():
    with pytest.raises(ValueError):
        A.promise_calibration(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        A.promise_calibration(pd.DataFrame())
    with pytest.raises(ValueError):
        A.promise_calibration(_calibration_cell("A->B", "Q1", [1] * 5, 1), min_orders=0)
    with pytest.raises(ValueError):
        A.promise_calibration(_calibration_cell("A->B", "Q1", [1] * 5, 1), quantile=1.0)
    with pytest.raises(ValueError):
        A.promise_calibration(
            _calibration_cell("A->B", "Q1", [1] * 5, 1), tolerance_days=-1
        )


def _cut_orders(
    n,
    route,
    approval,
    prep,
    transit,
    promise=5.0,
    start_km=1.0,
    weight_band="Q1",
    payment_type="credit_card",
):
    rows = []
    for i in range(n):
        total = approval + prep + transit
        rows.append(
            {
                "order_id": f"{route}-{i}",
                "route": route,
                "distance_km": start_km + i,
                "approval": approval,
                "prep": prep,
                "transit": transit,
                "promise_days": promise,
                "total_lead_days": total,
                "delay_days": total - promise,
                "is_late": total > promise,
                "review_score": 5,
                "gmv": 100.0,
                "payment_type": payment_type,
                "weight_band": weight_band,
            }
        )
    return pd.DataFrame(rows)


def _cut_fixture():
    # Tuyến nhanh đứng trước để P25 rơi vào nhóm nhanh (Q25 = 1).
    fast = _cut_orders(100, "C->D", 1, 1, 1)
    slow = _cut_orders(100, "A->B", 1, 2, 3, start_km=1000.0)
    return pd.concat([fast, slow], ignore_index=True)


def test_feasible_max_cut_point_and_ci_rule():
    o = _cut_fixture()
    slow = A.feasible_max_cut(
        o, "A->B", quantile=0.25, min_orders=1, n_boot=100, seed=42
    )
    assert slow["cut_approval"] == pytest.approx(0.0)
    assert slow["cut_prep"] == pytest.approx(1.0)
    assert slow["cut_transit"] == pytest.approx(2.0)
    assert slow["total_cut_days"] == pytest.approx(3.0)
    assert slow["baseline_late_rate"] == pytest.approx(1.0)
    assert slow["projected_late_rate"] == pytest.approx(0.0)
    assert slow["avoided_orders"] == 100
    assert slow["delta_pp"] == pytest.approx(100.0)
    assert slow["status"] in {"có cơ sở", "chưa đủ bằng chứng"}

    fast = A.feasible_max_cut(
        o, "C->D", quantile=0.25, min_orders=1, n_boot=100, seed=42
    )
    assert fast["total_cut_days"] == pytest.approx(0.0)
    assert fast["avoided_orders"] == 0
    assert fast["delta_pp"] == pytest.approx(0.0)
    assert fast["delta_ci_low_pp"] == fast["delta_ci_high_pp"] == pytest.approx(0.0)
    assert fast["status"] == "chưa đủ bằng chứng"


def test_status_from_ci():
    assert A._status_from_ci(0.5, 2.0) == "có cơ sở"
    assert A._status_from_ci(-0.5, 2.0) == "chưa đủ bằng chứng"
    assert A._status_from_ci(-2.0, -0.5) == "tác động âm"


def test_feasible_cut_table_contract():
    o = _cut_fixture()
    t = A.feasible_cut_table(
        o, min_orders=50, top=2, n_boot=50, seed=42
    )
    assert len(t) == 2
    assert t.iloc[0]["route"] == "A->B"
    assert t["avoided_orders"].is_monotonic_decreasing
    assert t.attrs["n_routes_eligible"] == 2
    assert t.attrs["n_boot"] == 50
    one = A.feasible_cut_table(o, routes=["C->D"], n_boot=20, seed=42)
    assert len(one) == 1
    assert one.iloc[0]["route"] == "C->D"


def test_marginal_cut_table_contract():
    o = _cut_fixture()
    m = A.marginal_cut_table(o, "A->B", quantile=0.25, step=1.0, stage="prep")
    assert list(m["cut_days"]) == [0.0, 1.0]
    assert m.iloc[0]["avoided_orders"] == 0
    assert m.iloc[1]["avoided_orders"] == 100
    assert m.iloc[1]["marginal_avoided_orders"] == 100
    assert m.iloc[1]["marginal_avoided_per_day"] == pytest.approx(100.0)
    transit = A.marginal_cut_table(o, "A->B", quantile=0.25, step=1.0, stage="transit")
    assert list(transit["cut_days"]) == [0.0, 1.0, 2.0]
    assert transit.iloc[-1]["avoided_orders"] == 100


def test_feasible_max_cut_rejects_bad_input():
    o = _cut_fixture()
    with pytest.raises(ValueError):
        A.feasible_max_cut(pd.DataFrame(), "A->B")
    with pytest.raises(ValueError):
        A.feasible_max_cut(o, "Z->Z")
    with pytest.raises(ValueError):
        A.feasible_max_cut(o, "A->B", alpha=1.0)
    with pytest.raises(ValueError):
        A.feasible_max_cut(o, "A->B", n_boot=0)
    with pytest.raises(ValueError):
        A.feasible_max_cut(o, "A->B", quantile=1.0)
    with pytest.raises(ValueError):
        A.feasible_cut_table(o, routes=["Z->Z"])
    with pytest.raises(ValueError):
        A.feasible_cut_table(o, sort_by="unknown")
    with pytest.raises(ValueError):
        A.marginal_cut_table(o, "A->B", step=0)
    with pytest.raises(ValueError):
        A.marginal_cut_table(o, "A->B", stage="unknown")


def test_attribute_rejects_missing_columns():
    with pytest.raises(ValueError):
        A.attribute(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        A.attribution_summary(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        A.bad_review_uplift(pd.DataFrame({"order_id": ["x"]}))
