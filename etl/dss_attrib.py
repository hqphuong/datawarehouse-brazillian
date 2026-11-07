"""Khối 2 nâng cấp: benchmark 3 giai đoạn, Shapley attribution, residual promise.

Mỗi đơn hàng được so với benchmark của **cùng tuyến và cùng decile khoảng cách**.
Chênh lệch thời gian của từng giai đoạn (approval/prep/transit) được phân bổ
bằng Shapley cho phần làm đơn trễ, còn phần trễ còn lại khi cả 3 giai đoạn đã
đạt benchmark được gọi là ``residual_promise`` (cam kết giao hàng quá chặt).

Định nghĩa game cho một đơn:

- ``b_s`` = benchmark (median) của giai đoạn s.
- ``e_s = actual_s - b_s`` = phần vượt benchmark.
- ``v(S)`` = 1 nếu đơn trễ khi các giai đoạn trong S giữ thời gian thực tế,
  các giai đoạn ngoài S được kéo về benchmark; ngược lại bằng 0.
- ``phi_s`` = giá trị Shapley của giai đoạn s trong game ``v``.
- ``residual = v(∅)`` = đơn có trễ không khi **cả 3 giai đoạn đều đạt benchmark**.

Vì ``v(N) = late_actual`` và ``v(∅) = late_benchmark``, ta luôn có::

    late_actual = late_benchmark + phi_approval + phi_prep + phi_transit

Đây là invariant L1 (efficiency) ở cấp từng đơn; L2 là cùng đẳng thức ở cấp
tổng hợp; L3 kiểm tra miền giá trị/dữ liệu hữu hạn.
"""

from __future__ import annotations

from itertools import permutations

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.dss_attrib
    from .dss_models import STAGES, load_orders
except ImportError:  # chạy trực tiếp: python etl/dss_attrib.py
    from dss_models import STAGES, load_orders

PHI_COLS = [f"phi_{s}" for s in STAGES]
EXCESS_COLS = [f"excess_{s}" for s in STAGES]
BENCH_COLS = [f"b_{s}" for s in STAGES]
PERMUTATIONS = tuple(permutations(STAGES))
BAD_REVIEW_MAX = 2  # Olist review_score 1..5; 1-2 là đánh giá xấu.


def add_distance_band(o: pd.DataFrame, q: int = 10) -> pd.DataFrame:
    """Thêm cột ``distance_band`` = decile khoảng cách; thiếu km → ``"NA"``."""
    out = o.copy()
    band = pd.Series("NA", index=out.index, dtype="object")
    dist = out["distance_km"]
    mask = dist.notna()
    if mask.any():
        labels = [f"D{i}" for i in range(1, q + 1)]
        try:
            cut = pd.qcut(dist[mask], q=q, labels=labels, duplicates="drop")
        except ValueError:
            # Nhiều giá trị trùng (hoặc quá ít điểm) làm qcut gộp bin.
            ranks = dist[mask].rank(method="first")
            q_eff = min(q, int(ranks.nunique()))
            if q_eff < 2:
                band.loc[mask] = "D1"
                out["distance_band"] = band
                return out
            cut = pd.qcut(
                ranks, q=q_eff, labels=[f"D{i}" for i in range(1, q_eff + 1)]
            )
        band.loc[mask] = cut.astype(str)
    out["distance_band"] = band
    return out


def fit_benchmarks(
    o: pd.DataFrame, min_orders: int = 30, distance_bands: int = 10
) -> pd.DataFrame:
    """Fit benchmark median 3 giai đoạn theo (tuyến, decile khoảng cách).

    Thứ tự fallback khi một ô quá ít đơn:

    1. ``route_band``: median của (tuyến, decile khoảng cách) nếu ``n >= min_orders``.
    2. ``route``: median toàn tuyến nếu tuyến có ``n >= min_orders``.
    3. ``global``: median toàn bộ đơn.

    Trả về DataFrame một dòng / (route, distance_band) với các cột ``b_*``,
    ``n_orders`` và ``benchmark_level``. Các bảng fallback được lưu trong
    ``.attrs`` để ``attribute()`` dùng lại, tránh fit lại trên dữ liệu khác.
    """
    missing = [c for c in ["route", "distance_km", *STAGES] if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột cho benchmark: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để fit benchmark")

    d = add_distance_band(o, q=distance_bands)
    agg = {"n_orders": ("order_id", "size"), **{f"b_{s}": (s, "median") for s in STAGES}}
    cell = d.groupby(["route", "distance_band"], as_index=False).agg(**agg)

    route = (
        d.groupby("route", as_index=False)
        .agg(route_orders=("order_id", "size"), **{f"b_{s}_route": (s, "median") for s in STAGES})
    )
    global_bench = {s: float(d[s].median()) for s in STAGES}

    cell = cell.merge(route, on="route", how="left")
    cell["benchmark_level"] = "route_band"

    low_cell = cell["n_orders"] < min_orders
    for s in STAGES:
        cell.loc[low_cell, f"b_{s}"] = cell.loc[low_cell, f"b_{s}_route"]
    cell.loc[low_cell, "benchmark_level"] = "route"

    low_route = cell["route_orders"] < min_orders
    for s in STAGES:
        cell.loc[low_route, f"b_{s}"] = global_bench[s]
    cell.loc[low_route, "benchmark_level"] = "global"

    keep = ["route", "distance_band", "n_orders", *BENCH_COLS, "benchmark_level"]
    cell = cell[keep].reset_index(drop=True)
    cell.attrs["min_orders"] = int(min_orders)
    cell.attrs["distance_bands"] = int(distance_bands)
    cell.attrs["global_benchmark"] = global_bench
    cell.attrs["route_benchmark"] = route.rename(
        columns={f"b_{s}_route": f"route_b_{s}" for s in STAGES}
    )
    return cell


def _shapley_orders(
    actual: pd.DataFrame, benchmark: pd.DataFrame, promise: pd.Series
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Tính Shapley từng đơn cho game ``v(S)`` (xem docstring module).

    ``actual``/``benchmark`` có 3 cột theo ``STAGES``; ``promise`` là Series
    cùng index. Trả về ``(phi, late_actual, late_benchmark)``.
    """
    n = len(actual)
    base = benchmark.sum(axis=1).to_numpy(dtype=float)
    p = promise.to_numpy(dtype=float)
    excess = {s: (actual[s] - benchmark[s]).to_numpy(dtype=float) for s in STAGES}

    # v(S) cho 8 tập con, mã hoá bằng bitmask theo thứ tự STAGES.
    values: dict[int, np.ndarray] = {}
    for mask in range(1 << len(STAGES)):
        total = base.copy()
        for i, s in enumerate(STAGES):
            if mask & (1 << i):
                total = total + excess[s]
        values[mask] = (total > p).astype(float)

    phi = {s: np.zeros(n, dtype=float) for s in STAGES}
    for perm in PERMUTATIONS:
        mask = 0
        prev = values[0]
        for s in perm:
            mask |= 1 << STAGES.index(s)
            cur = values[mask]
            phi[s] += cur - prev
            prev = cur
    n_perm = len(PERMUTATIONS)
    for s in STAGES:
        phi[s] /= n_perm

    return phi, values[(1 << len(STAGES)) - 1], values[0]


def attribute(o: pd.DataFrame, benchmarks: pd.DataFrame | None = None, min_orders: int = 30):
    """Gắn benchmark, phần vượt, residual promise và ``phi_*`` cho từng đơn.

    Nếu ``benchmarks=None`` thì fit trên chính ``o``. Ô (tuyến, decile) chưa có
    trong benchmark sẽ fallback về median tuyến, rồi median toàn cục.
    """
    need = ["order_id", "route", "distance_km", "promise_days", "total_lead_days", *STAGES]
    missing = [c for c in need if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột để attribute: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để attribute")

    if benchmarks is None:
        benchmarks = fit_benchmarks(o, min_orders=min_orders)
    b = benchmarks
    missing_b = [c for c in ["route", "distance_band", *BENCH_COLS] if c not in b.columns]
    if missing_b:
        raise ValueError(f"Benchmark thiếu cột: {missing_b}")

    d = add_distance_band(o)
    m = d.merge(
        b[["route", "distance_band", *BENCH_COLS, "benchmark_level"]],
        on=["route", "distance_band"],
        how="left",
    )

    route_b = b.attrs.get("route_benchmark")
    if route_b is None:
        route_b = (
            o.groupby("route", as_index=False)[STAGES]
            .median()
            .rename(columns={s: f"route_b_{s}" for s in STAGES})
        )
    m = m.merge(route_b[["route", *[f"route_b_{s}" for s in STAGES]]], on="route", how="left")

    global_b = b.attrs.get("global_benchmark") or {s: float(o[s].median()) for s in STAGES}
    cell_found = m["b_approval"].notna()
    route_found = m["route_b_approval"].notna()
    for s in STAGES:
        m[f"b_{s}"] = m[f"b_{s}"].fillna(m[f"route_b_{s}"])
        m[f"b_{s}"] = m[f"b_{s}"].fillna(global_b[s])
    m["benchmark_level"] = np.select(
        [cell_found, route_found], ["route_band", "route"], default="global"
    )

    for s in STAGES:
        m[f"excess_{s}"] = m[s] - m[f"b_{s}"]
    m["benchmark_total"] = m[BENCH_COLS].sum(axis=1)
    # Dương = cam kết chặt hơn benchmark (cần thêm ngày mới đạt benchmark).
    m["residual_promise_days"] = m["benchmark_total"] - m["promise_days"]

    phi, late_actual, late_benchmark = _shapley_orders(
        m[STAGES],
        m[BENCH_COLS].rename(columns={f"b_{s}": s for s in STAGES}),
        m["promise_days"],
    )
    for s in STAGES:
        m[f"phi_{s}"] = phi[s]
    m["phi_total"] = m[PHI_COLS].sum(axis=1)
    m["late_actual"] = late_actual.astype(int)
    m["late_benchmark"] = late_benchmark.astype(int)

    # L1 (efficiency) từng đơn; giữ lại để check_attrib và test đối chiếu.
    m["attrib_error"] = m["late_actual"] - m["late_benchmark"] - m["phi_total"]
    m.attrs["check_shapley"] = check_attrib(m)
    return m


def attribution_summary(
    o_attr: pd.DataFrame, by: str = "route", min_orders: int = 0
) -> pd.DataFrame:
    """Tổng hợp attribution theo ``by`` (mặc định tuyến).

    Cột chính: ``late_rate`` (thực tế), ``residual_late_rate`` (khi cả 3 giai
    đoạn đạt benchmark — "promise quá chặt"), ``phi_*`` (điểm % trễ do từng
    giai đoạn), ``phi_total`` và ``share_*`` (tỷ trọng trong phần vượt).
    """
    need = ["order_id", "late_actual", "late_benchmark", "residual_promise_days", *PHI_COLS]
    missing = [c for c in need if c not in o_attr.columns]
    if missing:
        raise ValueError(f"Thiếu cột để summary: {missing}")
    if by not in o_attr.columns:
        raise ValueError(f"Không có cột nhóm: {by}")

    agg = {
        "orders": ("order_id", "nunique"),
        "late_rate": ("late_actual", "mean"),
        "residual_late_rate": ("late_benchmark", "mean"),
        "residual_promise_days": ("residual_promise_days", "mean"),
        **{f"mean_excess_{s}": (f"excess_{s}", "mean") for s in STAGES},
        **{f"phi_{s}": (f"phi_{s}", "mean") for s in STAGES},
    }
    out = o_attr.groupby(by, as_index=False).agg(**agg)
    out["phi_total"] = out[PHI_COLS].sum(axis=1)
    out["reconstructed_late_rate"] = out["residual_late_rate"] + out["phi_total"]
    out["efficiency_error"] = out["late_rate"] - out["reconstructed_late_rate"]

    positive = out["phi_total"] > 0
    for s in STAGES:
        out[f"share_{s}"] = np.where(positive, out[f"phi_{s}"] / out["phi_total"], np.nan)
    out["top_stage"] = (
        out[PHI_COLS].idxmax(axis=1).str.replace("phi_", "", regex=False)
    )
    out["low_sample"] = out["orders"] < min_orders
    if min_orders > 0:
        out = out[~out["low_sample"]].copy()
    return out.sort_values("phi_total", ascending=False).reset_index(drop=True)


def bad_review_uplift(o_attr: pd.DataFrame) -> dict:
    """So sánh tỷ lệ đánh giá xấu (review_score ≤ 2) giữa đơn trễ và đúng hạn.

    Trả về dict; các tỷ lệ là 0..1, ``absolute_uplift_pp`` theo điểm phần trăm.
    Đơn thiếu ``review_score`` bị loại khỏi phép so sánh và được đếm riêng.
    """
    need = ["late_actual", "review_score"]
    missing = [c for c in need if c not in o_attr.columns]
    if missing:
        raise ValueError(f"Thiếu cột để bad_review_uplift: {missing}")

    valid = o_attr[o_attr["review_score"].notna()].copy()
    valid["bad_review"] = valid["review_score"] <= BAD_REVIEW_MAX
    late = valid[valid["late_actual"] == 1]
    ontime = valid[valid["late_actual"] == 0]

    def rate(frame: pd.DataFrame) -> float:
        return float(frame["bad_review"].mean()) if len(frame) else float("nan")

    rate_late = rate(late)
    rate_ontime = rate(ontime)
    return {
        "n_reviewed": int(len(valid)),
        "n_missing_review": int(len(o_attr) - len(valid)),
        "n_late": int(len(late)),
        "n_ontime": int(len(ontime)),
        "bad_review_rate_late": rate_late,
        "bad_review_rate_ontime": rate_ontime,
        "absolute_uplift_pp": (rate_late - rate_ontime) * 100.0,
        "relative_uplift": (
            rate_late / rate_ontime if rate_ontime and not np.isnan(rate_ontime) else float("nan")
        ),
    }


def check_attrib(o_attr: pd.DataFrame, tol: float = 1e-9) -> dict:
    """Kiểm tra 3 invariant của attribution.

    - **L1** (efficiency từng đơn): ``late_actual - late_benchmark - Σphi == 0``.
    - **L2** (efficiency tổng hợp): trung bình 3 vế trên cũng bằng 0.
    - **L3** (validity): không NaN/inf; ``phi`` trong [-1, 1]; ``late_*`` là 0/1;
      benchmark không âm; ``residual_promise_days`` hữu hạn.
    """
    need = ["late_actual", "late_benchmark", *PHI_COLS, *BENCH_COLS, "residual_promise_days"]
    missing = [c for c in need if c not in o_attr.columns]
    if missing:
        raise ValueError(f"Thiếu cột để check_attrib: {missing}")

    late_actual = o_attr["late_actual"].to_numpy(dtype=float)
    late_bench = o_attr["late_benchmark"].to_numpy(dtype=float)
    phi_total = o_attr[PHI_COLS].sum(axis=1).to_numpy(dtype=float)
    row_error = np.abs(late_actual - late_bench - phi_total)
    l1_max = float(row_error.max()) if len(row_error) else 0.0

    agg_error = abs(float(late_actual.mean()) - float(late_bench.mean()) - float(phi_total.mean()))
    phi_values = o_attr[PHI_COLS].to_numpy(dtype=float)
    bench_values = o_attr[BENCH_COLS].to_numpy(dtype=float)
    residual = o_attr["residual_promise_days"].to_numpy(dtype=float)
    l3_ok = bool(
        np.isfinite(phi_values).all()
        and np.isfinite(bench_values).all()
        and np.isfinite(residual).all()
        and np.isin(late_actual, [0.0, 1.0]).all()
        and np.isin(late_bench, [0.0, 1.0]).all()
        and (np.abs(phi_values) <= 1.0 + tol).all()
        and (bench_values >= -tol).all()
    )

    result = {
        "n_orders": int(len(o_attr)),
        "l1_row_efficiency": bool(l1_max <= tol),
        "l1_max_error": l1_max,
        "l2_aggregate_efficiency": bool(agg_error <= tol),
        "l2_error": float(agg_error),
        "l3_validity": l3_ok,
    }
    result["passed"] = bool(result["l1_row_efficiency"] and result["l2_aggregate_efficiency"] and l3_ok)
    return result


def main() -> None:
    """In attribution cho các tuyến nhiều đơn nhất và kiểm tra invariant."""
    o = load_orders()
    b = fit_benchmarks(o)
    a = attribute(o, b)
    s = attribution_summary(a)
    top = s.sort_values("orders", ascending=False).head(8)
    print("## Attribution theo tuyến (top theo số đơn)")
    cols = [
        "route", "orders", "late_rate", "residual_late_rate",
        "residual_promise_days", *PHI_COLS, "phi_total", "top_stage",
    ]
    print(top[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n## Bất biến")
    print(check_attrib(a))
    print("\n## Đánh giá xấu theo trạng thái giao")
    print(bad_review_uplift(a))


if __name__ == "__main__":
    main()
