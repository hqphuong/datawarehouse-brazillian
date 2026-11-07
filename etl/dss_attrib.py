"""Khối 2 nâng cấp: benchmark 3 giai đoạn, Shapley attribution, residual promise.

Mỗi giai đoạn dùng một **nhóm peer riêng**, không dùng chung khóa tuyến:

- ``approval``: median theo ``payment_type`` (loại thanh toán).
- ``prep``: median theo ``weight_band`` (nhóm trọng lượng).
- ``transit``: median **xuyên tuyến** theo ``distance_band`` (decile khoảng cách
  toàn cục). Đây là peer group theo khoảng cách, không phải median nội bộ tuyến.

Nhóm nào ít hơn ``min_orders`` hoặc thiếu khóa (``"NA"``) thì fallback về median
toàn cục của chính giai đoạn đó. Cách này đo "tuyến chậm hơn peer cùng điều kiện"
thay vì "chênh lệch trong nội bộ tuyến". Không giữ cột within-route dispersion
để tránh trộn hai chuẩn; hạn chế được ghi trong báo cáo.

Sensitivity chỉ dùng q=0,25 và q=0,5. q=0,75 bị loại vì benchmark 75th percentile
chậm hơn thời gian thực tế, làm ``phi`` âm và phân rã không hợp lệ.

Chênh lệch thời gian của từng giai đoạn (approval/prep/transit) được phân bổ
bằng Shapley cho phần làm đơn trễ, còn phần trễ còn lại khi cả 3 giai đoạn đã
đạt benchmark được gọi là ``residual_promise`` (benchmark ngắn hơn cam kết).

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

import math
from itertools import permutations

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.dss_attrib
    from .dss_models import STAGES, load_orders, scenario
except ImportError:  # chạy trực tiếp: python etl/dss_attrib.py
    from dss_models import STAGES, load_orders, scenario

PHI_COLS = [f"phi_{s}" for s in STAGES]
EXCESS_COLS = [f"excess_{s}" for s in STAGES]
BENCH_COLS = [f"b_{s}" for s in STAGES]
PERMUTATIONS = tuple(permutations(STAGES))
BAD_REVIEW_MAX = 2  # Olist review_score 1..5; 1-2 là đánh giá xấu.

# Mỗi giai đoạn so với peer group riêng (thiết kế v2, G2 phương án 2).
STAGE_KEYS = {
    "approval": "payment_type",
    "prep": "weight_band",
    "transit": "distance_band",
}
LEVEL_COLS = [f"benchmark_level_{s}" for s in STAGES]
BENCH_KEY_COLS = ["route", "distance_band", "weight_band", "payment_type"]


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
    o: pd.DataFrame,
    min_orders: int = 30,
    distance_bands: int = 10,
    quantile: float = 0.5,
) -> pd.DataFrame:
    """Fit benchmark từng giai đoạn theo peer group riêng.

    - ``approval``: median theo ``payment_type``.
    - ``prep``: median theo ``weight_band``.
    - ``transit``: median theo ``distance_band`` = decile khoảng cách toàn cục,
      tính **xuyên tuyến**. Đây là điểm khác cốt lõi so với bản cũ
      (tuyến × decile), nơi benchmark transit chỉ đo dispersion nội bộ tuyến.

    Fallback: nhóm có ``n < min_orders`` hoặc khóa thiếu (``"NA"``) dùng median
    toàn cục của giai đoạn. ``quantile`` mặc định 0,5 (median); sensitivity chỉ
    dùng 0,25 và 0,5, không dùng 0,75 (xem docstring module).

    Trả về DataFrame một dòng / tổ hợp khóa quan sát được, kèm ``b_*`` và
    ``benchmark_level_*`` từng giai đoạn. Các bảng lookup và median toàn cục
    được lưu trong ``.attrs`` để ``attribute()`` dùng lại.
    """
    required = ["order_id", "route", "distance_km", "weight_band", "payment_type", *STAGES]
    missing = [c for c in required if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột cho benchmark: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để fit benchmark")
    if not 0 < quantile < 1:
        raise ValueError("quantile phải trong (0, 1)")

    d = add_distance_band(o, q=distance_bands)
    for key in ("distance_band", "weight_band", "payment_type"):
        d[key] = d[key].fillna("NA").astype(str)

    def qstat(series: pd.Series) -> float:
        return float(series.quantile(quantile))

    global_bench = {s: qstat(d[s]) for s in STAGES}
    stage_benchmarks: dict[str, pd.DataFrame] = {}
    for s in STAGES:
        key = STAGE_KEYS[s]
        g = d.groupby(key, as_index=False).agg(
            **{f"n_{s}": ("order_id", "size"), f"b_{s}": (s, qstat)}
        )
        level_col = f"benchmark_level_{s}"
        is_peer = (g[f"n_{s}"] >= min_orders) & (g[key] != "NA")
        g[level_col] = np.where(is_peer, "peer", "global")
        g.loc[~is_peer, f"b_{s}"] = global_bench[s]
        stage_benchmarks[s] = g[[key, f"b_{s}", f"n_{s}", level_col]]

    combined = d.groupby(BENCH_KEY_COLS, as_index=False).agg(
        n_orders=("order_id", "size")
    )
    for s in STAGES:
        combined = combined.merge(stage_benchmarks[s], on=STAGE_KEYS[s], how="left")
    combined["benchmark_level"] = np.select(
        [
            (combined[LEVEL_COLS] == "peer").all(axis=1),
            (combined[LEVEL_COLS] == "global").all(axis=1),
        ],
        ["peer", "global"],
        default="mixed",
    )
    combined = combined[
        [*BENCH_KEY_COLS, "n_orders", *BENCH_COLS, *LEVEL_COLS, "benchmark_level"]
    ].reset_index(drop=True)

    combined.attrs["stage_benchmarks"] = stage_benchmarks
    combined.attrs["global_benchmark"] = global_bench
    combined.attrs["stage_keys"] = dict(STAGE_KEYS)
    combined.attrs["min_orders"] = int(min_orders)
    combined.attrs["distance_bands"] = int(distance_bands)
    combined.attrs["quantile"] = float(quantile)
    return combined


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


def _stage_lookup(benchmarks: pd.DataFrame, stage: str) -> pd.DataFrame | None:
    """Bảng tra benchmark của một giai đoạn theo đúng khóa peer của nó."""
    key = STAGE_KEYS[stage]
    value_col = f"b_{stage}"
    if key not in benchmarks.columns or value_col not in benchmarks.columns:
        return None
    level_col = f"benchmark_level_{stage}"
    cols = [key, value_col] + ([level_col] if level_col in benchmarks.columns else [])
    return benchmarks[cols].drop_duplicates(subset=[key]).set_index(key)


def attribute(o: pd.DataFrame, benchmarks: pd.DataFrame | None = None, min_orders: int = 30):
    """Gắn benchmark, phần vượt, residual promise và ``phi_*`` cho từng đơn.

    Nếu ``benchmarks=None`` thì fit trên chính ``o``. Mỗi giai đoạn lấy benchmark
    theo khóa peer riêng (``payment_type`` / ``weight_band`` / ``distance_band``);
    khóa chưa có hoặc giai đoạn đó fallback sẽ dùng median toàn cục.
    """
    need = [
        "order_id",
        "route",
        "distance_km",
        "weight_band",
        "payment_type",
        "promise_days",
        "total_lead_days",
        *STAGES,
    ]
    missing = [c for c in need if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột để attribute: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để attribute")

    if benchmarks is None:
        benchmarks = fit_benchmarks(o, min_orders=min_orders)
    b = benchmarks
    missing_b = [f"b_{s}" for s in STAGES if f"b_{s}" not in b.columns]
    if missing_b:
        raise ValueError(f"Benchmark thiếu cột: {missing_b}")

    d = add_distance_band(o, q=int(b.attrs.get("distance_bands", 10)))
    m = d.copy()
    for key in ("distance_band", "weight_band", "payment_type"):
        m[key] = m[key].fillna("NA").astype(str)

    global_b = b.attrs.get("global_benchmark")
    if global_b is None:
        quantile = float(b.attrs.get("quantile", 0.5))
        global_b = {s: float(o[s].quantile(quantile)) for s in STAGES}

    for s in STAGES:
        key = STAGE_KEYS[s]
        value_col = f"b_{s}"
        level_col = f"benchmark_level_{s}"
        lookup = _stage_lookup(b, s)
        if lookup is None:
            m[value_col] = np.nan
            m[level_col] = np.nan
        else:
            m[value_col] = m[key].map(lookup[value_col])
            if level_col in lookup.columns:
                m[level_col] = m[key].map(lookup[level_col])
            else:
                m[level_col] = np.where(m[value_col].notna(), "peer", np.nan)
        m[value_col] = m[value_col].fillna(global_b[s])
        m[level_col] = m[level_col].fillna("global")

    m["benchmark_level"] = np.select(
        [
            (m[LEVEL_COLS] == "peer").all(axis=1),
            (m[LEVEL_COLS] == "global").all(axis=1),
        ],
        ["peer", "global"],
        default="mixed",
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
    # Tỷ trọng 4 nguyên nhân trên toàn bộ đơn trễ: 3 stage + residual promise.
    late_positive = out["late_rate"] > 0
    out["share_promise"] = np.where(
        late_positive, out["residual_late_rate"] / out["late_rate"], np.nan
    )
    for s in STAGES:
        out[f"cause_share_{s}"] = np.where(
            late_positive, out[f"phi_{s}"] / out["late_rate"], np.nan
        )
    out["top_stage"] = (
        out[PHI_COLS].idxmax(axis=1).str.replace("phi_", "", regex=False)
    )
    out["low_sample"] = out["orders"] < min_orders
    if min_orders > 0:
        out = out[~out["low_sample"]].copy()
    return out.sort_values("phi_total", ascending=False).reset_index(drop=True)


PROMISE_LABELS = ("tight", "ok", "loose")


def promise_calibration(
    o: pd.DataFrame,
    min_orders: int = 100,
    quantile: float = 0.95,
    tolerance_days: float = 1.0,
) -> pd.DataFrame:
    """Hiệu chỉnh cam kết giao hàng theo ô ``route × weight_band`` (S3).

    Đơn vị là **đơn-tuyến** (một dòng = một cặp ``order_id`` + ``route``). Mỗi ô
    cần tối thiểu ``min_orders`` đơn-tuyến để đủ tin cậy; ô nhỏ hơn bị loại khỏi
    bảng và được đếm trong ``.attrs`` (không âm thầm bỏ).

    Ý tưởng: cam kết hiện tại (``promise_days``) là một con số nghiệp vụ, còn
    ``needed_days = ceil(Q95 total_lead_days)`` là số ngày cần để 95% đơn trong
    ô giao đúng hạn theo **thời gian giao thực tế**. So sánh hai giá trị:

    - ``gap_days = median_promise_days − needed_days``.
    - ``tight``: gap < −``tolerance_days`` → cam kết chặt hơn mức giao thực tế.
    - ``loose``: gap > +``tolerance_days`` → cam kết lỏng hơn mức giao thực tế.
    - ``ok``: phần còn lại (trong khoảng ±``tolerance_days``).

    ``avoidable_orders`` = số đơn **đang trễ nhưng sẽ đúng hạn nếu cam kết bằng
    ``needed_days``** (``total_lead_days ≤ needed_days``). Đây chỉ là thay đổi
    **định nghĩa trễ**, không rút ngắn thời gian giao thực tế; vì vậy không được
    diễn giải là "giảm trễ" theo nghĩa vận hành.

    Trả về DataFrame một dòng / ô đủ mẫu, sắp theo ``avoidable_orders`` giảm dần.
    Các thông tin tổng hợp nằm trong ``.attrs``: số ô giữ/loại, số đơn-tuyến,
    tổng ``avoidable_orders``, phân bố nhãn và tham số.

    Tham số:
        o: bảng đơn-tuyến từ :func:`etl.dss_models.load_orders`.
        min_orders: ngưỡng mẫu tối thiểu cho mỗi ô (mặc định 100).
        quantile: phân vị thời gian giao dùng làm cam kết mục tiêu (mặc định 0,95).
        tolerance_days: dung sai ± ngày để coi là ``ok`` (mặc định 1,0).
    """
    required = [
        "order_id",
        "route",
        "weight_band",
        "promise_days",
        "total_lead_days",
        "is_late",
    ]
    missing = [c for c in required if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột để promise_calibration: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để promise_calibration")
    if min_orders < 1:
        raise ValueError("min_orders phải >= 1")
    if not 0 < quantile < 1:
        raise ValueError("quantile phải trong (0, 1)")
    if tolerance_days < 0:
        raise ValueError("tolerance_days phải >= 0")

    d = o.copy()
    d["weight_band"] = d["weight_band"].fillna("NA").astype(str)

    def needed_days(series: pd.Series) -> int:
        return int(math.ceil(float(series.quantile(quantile))))

    cells = d.groupby(["route", "weight_band"], as_index=False).agg(
        n_orders=("order_id", "size"),
        late_orders=("is_late", "sum"),
        median_promise_days=("promise_days", "median"),
        needed_days=("total_lead_days", needed_days),
    )
    cells["current_late_rate"] = cells["late_orders"] / cells["n_orders"]
    cells["gap_days"] = cells["median_promise_days"] - cells["needed_days"]
    cells["label"] = np.select(
        [
            cells["gap_days"] < -float(tolerance_days),
            cells["gap_days"] > float(tolerance_days),
        ],
        ["tight", "loose"],
        default="ok",
    )

    # Đánh giá từng đơn-tuyến dưới cam kết hiệu chỉnh = needed_days của ô.
    m = d.merge(
        cells[["route", "weight_band", "needed_days"]],
        on=["route", "weight_band"],
        how="left",
    )
    currently_late = m["is_late"].astype(bool)
    calibrated_late = m["total_lead_days"] > m["needed_days"]
    m["avoidable_order"] = currently_late & ~calibrated_late
    m["calibrated_late"] = calibrated_late
    per_order = m.groupby(["route", "weight_band"], as_index=False).agg(
        avoidable_orders=("avoidable_order", "sum"),
        calibrated_late_orders=("calibrated_late", "sum"),
    )
    cells = cells.merge(per_order, on=["route", "weight_band"], how="left")
    cells["calibrated_late_rate"] = (
        cells["calibrated_late_orders"] / cells["n_orders"]
    )
    cells["avoidable_share_of_late"] = np.where(
        cells["late_orders"] > 0,
        cells["avoidable_orders"] / cells["late_orders"],
        np.nan,
    )

    small = cells[cells["n_orders"] < min_orders]
    out = (
        cells[cells["n_orders"] >= min_orders]
        .sort_values(["avoidable_orders", "n_orders"], ascending=False)
        .reset_index(drop=True)
    )

    out.attrs["min_orders"] = int(min_orders)
    out.attrs["quantile"] = float(quantile)
    out.attrs["tolerance_days"] = float(tolerance_days)
    out.attrs["n_cells_total"] = int(len(cells))
    out.attrs["n_cells_kept"] = int(len(out))
    out.attrs["n_cells_small"] = int(len(small))
    out.attrs["n_orders_total"] = int(len(d))
    out.attrs["n_orders_kept"] = int(out["n_orders"].sum())
    out.attrs["n_orders_small_cells"] = int(small["n_orders"].sum())
    out.attrs["late_orders_kept"] = int(out["late_orders"].sum())
    out.attrs["avoidable_orders"] = int(out["avoidable_orders"].sum())
    out.attrs["calibrated_late_orders"] = int(out["calibrated_late_orders"].sum())
    out.attrs["label_counts"] = {
        label: int((out["label"] == label).sum()) for label in PROMISE_LABELS
    }
    return out


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
    print("\n## Fallback benchmark theo giai đoạn")
    for stage in STAGES:
        levels = a[f"benchmark_level_{stage}"].value_counts(normalize=True)
        print(f"- {stage}: {levels.round(6).to_dict()}")
    print("\n## Bất biến")
    print(check_attrib(a))
    print("\n## Đánh giá xấu theo trạng thái giao")
    print(bad_review_uplift(a))


if __name__ == "__main__":
    main()
