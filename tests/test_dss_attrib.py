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


def _orders(n, route="A->B", start_km=1.0, approval=1.0, prep=2.0, transit=3.0, promise=7.0):
    rows = []
    for i in range(n):
        rows.append(
            {
                "order_id": f"{route}-{i}",
                "route": route,
                "distance_km": start_km + i,
                "approval": approval,
                "prep": prep,
                "transit": transit,
                "promise_days": promise,
                "total_lead_days": approval + prep + transit,
                "delay_days": approval + prep + transit - promise,
                "is_late": approval + prep + transit > promise,
                "review_score": 1 if i % 3 == 0 else 5,
                "gmv": 100.0,
            }
        )
    return pd.DataFrame(rows)


def _benchmark(route="A->B", band="D1", b=(0.5, 0.5, 1.0)):
    return pd.DataFrame(
        [
            {
                "route": route,
                "distance_band": band,
                "n_orders": 100,
                "b_approval": b[0],
                "b_prep": b[1],
                "b_transit": b[2],
                "benchmark_level": "route_band",
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


def test_fit_benchmarks_fallback_levels():
    # 100 đơn / 10 decile = 10 đơn mỗi ô.
    o = pd.concat([_orders(100, "R1->X", 1.0), _orders(10, "R2->X", 1.0)])
    b = A.fit_benchmarks(o, min_orders=5)
    assert set(b.loc[b.route == "R1->X", "benchmark_level"]) == {"route_band"}

    b = A.fit_benchmarks(o, min_orders=20)
    assert set(b.loc[b.route == "R1->X", "benchmark_level"]) == {"route"}
    # Tuyến R2 chỉ có 10 đơn < 20 -> dùng global, kể cả khi ô có >= 1 đơn.
    assert set(b.loc[b.route == "R2->X", "benchmark_level"]) == {"global"}


def test_fit_benchmarks_rejects_bad_input():
    with pytest.raises(ValueError):
        A.fit_benchmarks(pd.DataFrame({"route": []}))
    with pytest.raises(ValueError):
        A.fit_benchmarks(_orders(3).drop(columns=["distance_km"]))


def test_benchmarks_cover_every_order(attributed):
    assert not attributed[A.BENCH_COLS].isna().any().any()
    assert set(attributed["benchmark_level"]).issubset({"route_band", "route", "global"})
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
    share_sum = positive[[f"share_{s}" for s in A.STAGES]].sum(axis=1)
    assert np.allclose(share_sum, 1.0, atol=1e-12)


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


def test_attribute_rejects_missing_columns():
    with pytest.raises(ValueError):
        A.attribute(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        A.attribution_summary(pd.DataFrame({"order_id": ["x"]}))
    with pytest.raises(ValueError):
        A.bad_review_uplift(pd.DataFrame({"order_id": ["x"]}))
