"""Đánh giá mô hình DSS: backtest, độ nhạy ngưỡng, top tuyến, thời gian âm.

Module này chỉ đọc dữ liệu đã xử lý và gọi các hàm trong ``etl.dss_models``.
Không sửa dữ liệu kho, không phụ thuộc Django.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.dss_eval
    from . import dss_models as M
except ImportError:  # chạy trực tiếp: python etl/dss_eval.py
    import dss_models as M


def _next_period(period: int) -> int:
    """Kỳ kế tiếp theo lịch tháng (YYYYMM)."""
    year, month = divmod(int(period), 100)
    return (year + 1) * 100 + 1 if month == 12 else year * 100 + (month + 1)


def _group_metrics(future: pd.DataFrame, mask: pd.Series):
    """Số đơn và tỷ lệ trễ của nhóm gắn cờ / nhóm còn lại trong kỳ t+1."""
    flagged_orders = int(mask.sum())
    other_orders = int((~mask).sum())
    flagged_rate = (
        float(future.loc[mask, "is_late"].mean()) if flagged_orders else np.nan
    )
    other_rate = (
        float(future.loc[~mask, "is_late"].mean()) if other_orders else np.nan
    )
    diff = (
        flagged_rate - other_rate
        if not (math.isnan(flagged_rate) or math.isnan(other_rate))
        else np.nan
    )
    return flagged_orders, other_orders, flagged_rate, other_rate, diff


def _historical_baseline_routes(
    o: pd.DataFrame,
    period: int,
    current: pd.DataFrame,
    min_orders: int,
    k: int,
    include_current: bool = False,
):
    """Chọn ``k`` tuyến theo tỷ lệ trễ gộp của lịch sử.

    Mặc định chỉ dùng các kỳ **trước** ``period`` (biến thể "prior"). Nếu
    ``include_current=True`` thì dùng lịch sử **đến hết kỳ ``period``** (biến
    thể "through"), tức cùng lượng thông tin DSS nhìn thấy ở kỳ hiện tại.

    Baseline chỉ xét các tuyến có đủ ``min_orders`` đơn trong kỳ hiện tại và có
    ít nhất một dòng lịch sử (để tính được tỷ lệ trễ trung bình). Xếp hạng theo
    tỷ lệ trễ lịch sử, phá hòa bằng số đơn lịch sử rồi theo tên tuyến.
    """
    if k <= 0:
        return set()

    if include_current:
        history = o[o["period"] <= period]
    else:
        history = o[o["period"] < period]
    if history.empty:
        return set()

    hist = history.groupby("route").agg(
        hist_orders=("is_late", "size"),
        hist_late_rate=("is_late", "mean"),
    )
    eligible = (
        current.groupby("route")
        .size()
        .rename("current_orders")
        .reset_index()
        .merge(hist, on="route", how="inner")
    )
    eligible = eligible[eligible["current_orders"] >= min_orders]
    picked = eligible.sort_values(
        ["hist_late_rate", "hist_orders", "route"],
        ascending=[False, False, True],
    ).head(k)
    return set(picked["route"])


def backtest(
    o: pd.DataFrame,
    min_orders: int = 30,
    min_period_orders: int = 500,
    start_year: int = 2017,
    red: float = 2.0,
    amber: float = 1.5,
    baseline: bool = False,
    baseline_through: bool = False,
):
    """Backtest một bước: tuyến gắn cờ ở kỳ t có trễ hơn ở kỳ t+1 không?

    Quy trình cho từng kỳ t:
    1. Chạy ``route_priority`` trên riêng dữ liệu kỳ t để lấy tuyến đỏ/vàng.
    2. Sang kỳ t+1, so tỷ lệ trễ của các đơn thuộc tuyến đã gắn cờ với phần còn lại.
    3. Bỏ kỳ 2016 (quá ít đơn) và kỳ không có kỳ kế tiếp liền kề theo lịch.

    Trả về ``(periods, summary)``:
    - ``periods``: DataFrame mỗi dòng một kỳ, có cột ``diff = flagged - other``.
    - ``summary``: dict tóm tắt một dòng. Số chính ``weighted_diff`` dùng trọng
      số là ``total_orders`` kỳ t+1 (= flagged_orders + other_orders). Cột
      ``weighted_diff_flagged`` dùng trọng số là ``flagged_orders`` kỳ t+1.

    Nếu ``baseline=True``, thêm baseline lịch sử: với mỗi kỳ t, chọn đúng số
    tuyến như DSS nhưng xếp hạng theo tỷ lệ trễ gộp của mọi kỳ trước t (chỉ xét
    tuyến đủ ``min_orders`` đơn trong kỳ t). Kết quả baseline nằm ở các cột
    ``baseline_*`` và phần tóm tắt ``baseline_*``/``dss_better_periods``.

    Nếu ``baseline_through=True`` (tự bật ``baseline``), thêm biến thể baseline
    dùng lịch sử **đến hết kỳ t** (gồm cả kỳ t, cùng thông tin DSS nhìn thấy).
    Kết quả nằm ở các cột ``baseline_through_*`` và phần tóm tắt
    ``baseline_through_*``/``dss_better_vs_through_periods``.

    Kỳ không có tuyến nào gắn cờ vẫn xuất hiện trong ``periods`` với
    ``flagged_late_rate``/``diff`` bằng NaN, nhưng không được tính vào mẫu số
    ``periods_evaluated``.
    """
    periods = sorted({int(p) for p in o["period"].dropna().unique()})
    available = set(periods)
    rows = []

    if baseline_through:
        baseline = True

    for t in periods:
        nxt = _next_period(t)
        if t // 100 < start_year or nxt not in available:
            continue

        current = o[o["period"] == t]
        future = o[o["period"] == nxt]
        if len(current) < min_period_orders or len(future) < min_period_orders:
            continue

        flagged = M.route_priority(
            current,
            red=red,
            amber=amber,
            min_orders=min_orders,
            top=len(current),
        )
        routes = set(flagged["route"])
        (
            flagged_orders,
            other_orders,
            flagged_rate,
            other_rate,
            diff,
        ) = _group_metrics(future, future["route"].isin(routes))

        row = {
            "period": t,
            "next_period": nxt,
            "flagged_routes": len(routes),
            "flagged_orders": flagged_orders,
            "other_orders": other_orders,
            "total_orders": len(future),
            "flagged_late_rate": flagged_rate,
            "other_late_rate": other_rate,
            "diff": diff,
        }

        if baseline:
            baseline_routes = _historical_baseline_routes(
                o, t, current, min_orders, len(routes)
            )
            (
                baseline_flagged_orders,
                baseline_other_orders,
                baseline_flagged_rate,
                baseline_other_rate,
                baseline_diff,
            ) = _group_metrics(future, future["route"].isin(baseline_routes))
            row.update(
                {
                    "baseline_routes": len(baseline_routes),
                    "baseline_flagged_orders": baseline_flagged_orders,
                    "baseline_other_orders": baseline_other_orders,
                    "baseline_flagged_late_rate": baseline_flagged_rate,
                    "baseline_other_late_rate": baseline_other_rate,
                    "baseline_diff": baseline_diff,
                }
            )

        if baseline_through:
            through_routes = _historical_baseline_routes(
                o, t, current, min_orders, len(routes), include_current=True
            )
            (
                through_flagged_orders,
                through_other_orders,
                through_flagged_rate,
                through_other_rate,
                through_diff,
            ) = _group_metrics(future, future["route"].isin(through_routes))
            row.update(
                {
                    "baseline_through_routes": len(through_routes),
                    "baseline_through_flagged_orders": through_flagged_orders,
                    "baseline_through_other_orders": through_other_orders,
                    "baseline_through_flagged_late_rate": through_flagged_rate,
                    "baseline_through_other_late_rate": through_other_rate,
                    "baseline_through_diff": through_diff,
                }
            )

        rows.append(row)

    columns = [
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
    if baseline:
        columns += [
            "baseline_routes",
            "baseline_flagged_orders",
            "baseline_other_orders",
            "baseline_flagged_late_rate",
            "baseline_other_late_rate",
            "baseline_diff",
        ]
    if baseline_through:
        columns += [
            "baseline_through_routes",
            "baseline_through_flagged_orders",
            "baseline_through_other_orders",
            "baseline_through_flagged_late_rate",
            "baseline_through_other_late_rate",
            "baseline_through_diff",
        ]
    frame = pd.DataFrame(rows, columns=columns)
    comparable = frame.dropna(subset=["diff"])

    higher = int((comparable["diff"] > 0).sum())
    # weighted_diff (số chính): trung bình có trọng số của
    # (flagged_late_rate - other_late_rate), trọng số = total_orders kỳ t+1
    # (= flagged_orders + other_orders). Cách này coi mỗi kỳ là một đơn vị và
    # đặt trọng số cao hơn cho kỳ có nhiều đơn (ước lượng ổn định hơn).
    # weighted_diff_flagged: cùng công thức nhưng trọng số = flagged_orders kỳ
    # t+1; dùng để đối chiếu, không phải số chính.
    weighted_diff = (
        float(
            np.average(comparable["diff"], weights=comparable["total_orders"])
        )
        if len(comparable)
        else None
    )
    # Cách tính thay thế: trọng số = flagged_orders (số đơn thuộc nhóm gắn cờ ở kỳ t+1)
    weighted_diff_flagged = (
        float(
            np.average(comparable["diff"], weights=comparable["flagged_orders"])
        )
        if len(comparable)
        else None
    )
    summary = {
        "min_orders": min_orders,
        "red": red,
        "amber": amber,
        "start_year": start_year,
        "min_period_orders": min_period_orders,
        "periods_considered": int(len(frame)),
        "periods_evaluated": int(len(comparable)),
        "periods_without_flags": int((frame["flagged_routes"] == 0).sum()),
        "periods_without_flagged_orders": int(
            ((frame["flagged_routes"] > 0) & (frame["flagged_orders"] == 0)).sum()
        ),
        "higher_periods": higher,
        "share_higher": (higher / len(comparable)) if len(comparable) else None,
        # Số chính: trọng số = total_orders kỳ t+1 (trung lập, kỳ nhiều dữ liệu hơn có trọng số cao hơn)
        "weighted_diff": weighted_diff,
        "weighted_diff_basis": "total_orders",
        # Tham khảo: trọng số = flagged_orders kỳ t+1 (nhấn mạnh kỳ có nhiều đơn bị gắn cờ)
        "weighted_diff_flagged": weighted_diff_flagged,
        "mean_diff": (
            float(comparable["diff"].mean()) if len(comparable) else None
        ),
    }

    if baseline:
        baseline_comparable = frame.dropna(subset=["baseline_diff"])
        baseline_higher = int((baseline_comparable["baseline_diff"] > 0).sum())
        baseline_weighted = (
            float(
                np.average(
                    baseline_comparable["baseline_diff"],
                    weights=baseline_comparable["total_orders"],
                )
            )
            if len(baseline_comparable)
            else None
        )
        baseline_weighted_flagged = (
            float(
                np.average(
                    baseline_comparable["baseline_diff"],
                    weights=baseline_comparable["baseline_flagged_orders"],
                )
            )
            if len(baseline_comparable)
            else None
        )

        paired = frame.dropna(subset=["diff", "baseline_diff"])
        baseline_better = int((paired["baseline_diff"] > paired["diff"]).sum())
        dss_better = int((paired["diff"] > paired["baseline_diff"]).sum())
        tied = int(len(paired) - baseline_better - dss_better)

        summary.update(
            {
                "baseline_periods_evaluated": int(len(baseline_comparable)),
                "baseline_periods_without_flags": int(
                    (frame["baseline_routes"] == 0).sum()
                ),
                "baseline_higher_periods": baseline_higher,
                "baseline_share_higher": (
                    baseline_higher / len(baseline_comparable)
                    if len(baseline_comparable)
                    else None
                ),
                "baseline_weighted_diff": baseline_weighted,
                "baseline_weighted_diff_flagged": baseline_weighted_flagged,
                "baseline_mean_diff": (
                    float(baseline_comparable["baseline_diff"].mean())
                    if len(baseline_comparable)
                    else None
                ),
                "paired_periods": int(len(paired)),
                "baseline_better_periods": baseline_better,
                "dss_better_periods": dss_better,
                "tied_periods": tied,
            }
        )

    if baseline_through:
        through_comparable = frame.dropna(subset=["baseline_through_diff"])
        through_higher = int(
            (through_comparable["baseline_through_diff"] > 0).sum()
        )
        through_weighted = (
            float(
                np.average(
                    through_comparable["baseline_through_diff"],
                    weights=through_comparable["total_orders"],
                )
            )
            if len(through_comparable)
            else None
        )
        through_weighted_flagged = (
            float(
                np.average(
                    through_comparable["baseline_through_diff"],
                    weights=through_comparable["baseline_through_flagged_orders"],
                )
            )
            if len(through_comparable)
            else None
        )

        through_paired = frame.dropna(
            subset=["diff", "baseline_through_diff"]
        )
        through_better = int(
            (
                through_paired["baseline_through_diff"]
                > through_paired["diff"]
            ).sum()
        )
        dss_better_vs_through = int(
            (
                through_paired["diff"]
                > through_paired["baseline_through_diff"]
            ).sum()
        )
        through_tied = int(
            len(through_paired) - through_better - dss_better_vs_through
        )

        summary.update(
            {
                "baseline_through_periods_evaluated": int(
                    len(through_comparable)
                ),
                "baseline_through_periods_without_flags": int(
                    (frame["baseline_through_routes"] == 0).sum()
                ),
                "baseline_through_higher_periods": through_higher,
                "baseline_through_share_higher": (
                    through_higher / len(through_comparable)
                    if len(through_comparable)
                    else None
                ),
                "baseline_through_weighted_diff": through_weighted,
                "baseline_through_weighted_diff_flagged": (
                    through_weighted_flagged
                ),
                "baseline_through_mean_diff": (
                    float(through_comparable["baseline_through_diff"].mean())
                    if len(through_comparable)
                    else None
                ),
                "paired_through_periods": int(len(through_paired)),
                "baseline_through_better_periods": through_better,
                "dss_better_vs_through_periods": dss_better_vs_through,
                "tied_vs_through_periods": through_tied,
            }
        )

    return frame, summary


def threshold_sensitivity(
    o: pd.DataFrame,
    min_orders_values=(50, 100, 200),
    threshold_pairs=((2.0, 1.5), (1.5, 1.25)),
) -> pd.DataFrame:
    """Số tuyến đỏ/vàng theo các tổ hợp ``min_orders`` và ngưỡng ``(red, amber)``."""
    rows = []
    for min_orders in min_orders_values:
        for red, amber in threshold_pairs:
            flagged = M.route_priority(
                o,
                red=red,
                amber=amber,
                min_orders=min_orders,
                top=len(o),
            )
            rows.append(
                {
                    "min_orders": min_orders,
                    "red": red,
                    "amber": amber,
                    "flagged_routes": len(flagged),
                    "red_routes": int((flagged["level"] == "red").sum()),
                    "amber_routes": int((flagged["level"] == "amber").sum()),
                }
            )
    return pd.DataFrame(rows)


def top_routes_report(
    o: pd.DataFrame,
    n: int = 3,
    target: float = 0.05,
    cuts=(1, 3, 5),
) -> pd.DataFrame:
    """Bảng chi tiết cho ``n`` tuyến đứng đầu ``route_priority``.

    Mỗi dòng gồm số đơn, baseline, root cause (excess từng giai đoạn và
    excess_ratio = excess / |mean_sys|), kết quả cắt 1/3/5 ngày cho từng
    giai đoạn, goal seek cam kết và goal seek cắt.

    Cột ``excess_ratio_<stage>`` chỉ để **tham khảo** (so sánh tương đối
    giữa các giai đoạn khi mean hệ thống chênh lệch nhiều); ``stage`` và
    ``has_bottleneck`` vẫn xác định theo excess tuyệt đối để giữ nhất quán
    với logic DSS. Nếu ``stage`` theo excess_ratio khác ``stage`` theo tuyệt
    đối, cột ``stage_ratio_diff`` sẽ bằng ``True``.
    """
    # Bảng chi tiết giữ đúng n tuyến theo late_orders (không dùng red-first)
    priority = M.route_priority(o, top=n, ensure_red=False)
    sys_means = {s: float(o[s].mean()) for s in M.STAGES}
    rows = []
    for _, item in priority.iterrows():
        route = item["route"]
        cause = M.root_cause(o, route)
        row = {
            "route": route,
            "orders": int(item["orders"]),
            "late_orders": int(item["late_orders"]),
            "baseline": float(item["late_rate"]),
            "level": item["level"],
            "stage": cause["stage"],
            "has_bottleneck": cause["has_bottleneck"],
        }
        for stage in M.STAGES:
            row[f"excess_{stage}"] = cause["excess"][stage]
        # excess_ratio: chỉ tham khảo — không đổi stage/has_bottleneck
        for stage in M.STAGES:
            denom = abs(sys_means[stage])
            row[f"excess_ratio_{stage}"] = (
                cause["excess"][stage] / denom if denom > 1e-9 else None
            )
        stage_by_ratio = max(
            M.STAGES,
            key=lambda s: (
                cause["excess"][s] / abs(sys_means[s])
                if abs(sys_means[s]) > 1e-9
                else float("-inf")
            ),
        )
        row["stage_ratio_diff"] = stage_by_ratio != cause["stage"]

        for stage in M.STAGES:
            for cut in cuts:
                row[f"{stage}_cut_{cut}"] = M.scenario(
                    o, route, {stage: cut}
                )["projected"]
            row[f"{stage}_goal_cut"] = M.goal_seek_cut(o, route, stage, target)

        promise = M.goal_seek_promise(o, route, target)
        row["promise_days"] = promise["extra_days"]
        row["promise_late_after"] = promise["late_after"]
        rows.append(row)

    return pd.DataFrame(rows)


def negative_rows_summary(o: pd.DataFrame) -> dict:
    """Đếm dòng thời gian âm ở cấp (đơn, tuyến) đang dùng cho mô hình."""
    any_negative = (o[["prep", "transit"]] < 0).any(axis=1)
    return {
        "order_route_rows": int(len(o)),
        "prep_negative": int((o["prep"] < 0).sum()),
        "transit_negative": int((o["transit"] < 0).sum()),
        "any_negative": int(any_negative.sum()),
        "removed_rows": int(any_negative.sum()),
    }


def negative_time_comparison(
    o: pd.DataFrame,
    n: int = 3,
    target: float = 0.05,
) -> pd.DataFrame:
    """So sánh root_cause của top ``n`` tuyến trước/sau khi bỏ dòng âm.

    Dòng âm bị loại nếu ``prep < 0`` hoặc ``transit < 0``. Việc loại bỏ được
    thực hiện trên toàn bộ dữ liệu, nên cả trung bình hệ thống (mẫu số của
    ``excess``) cũng thay đổi, không chỉ trung bình riêng tuyến.
    """
    routes = list(M.route_priority(o, top=n, ensure_red=False)["route"])
    clean = o[(o["prep"] >= 0) & (o["transit"] >= 0)].copy()
    removed = (o[["prep", "transit"]] < 0).any(axis=1)

    rows = []
    for route in routes:
        keep = M.root_cause(o, route)
        drop = M.root_cause(clean, route)
        row = {
            "route": route,
            "removed_rows": int((removed & (o["route"] == route)).sum()),
            "orders_keep": int((o["route"] == route).sum()),
            "orders_drop": int((clean["route"] == route).sum()),
            "baseline_keep": float(o.loc[o["route"] == route, "is_late"].mean()),
            "baseline_drop": float(
                clean.loc[clean["route"] == route, "is_late"].mean()
            ),
            "stage_keep": keep["stage"],
            "stage_drop": drop["stage"],
            "has_bottleneck_keep": keep["has_bottleneck"],
            "has_bottleneck_drop": drop["has_bottleneck"],
        }
        for stage in M.STAGES:
            row[f"excess_{stage}_keep"] = keep["excess"][stage]
            row[f"excess_{stage}_drop"] = drop["excess"][stage]
        rows.append(row)

    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame) -> str:
    """Xuất bảng Markdown không cần thư viện tabulate."""

    def cell(value) -> str:
        if value is None:
            return ""
        if isinstance(value, (bool, np.bool_)):
            return "True" if value else "False"
        if isinstance(value, (float, np.floating)):
            if math.isnan(float(value)) or math.isinf(float(value)):
                return "—"
            return f"{float(value):.6g}"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value).replace("|", "\\|")

    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(cell(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def bootstrap_ci(
    frame: pd.DataFrame,
    n_boot: int = 10_000,
    seed: int = 42,
    alpha: float = 0.05,
    weight_col: str = "total_orders",
) -> dict:
    """Bootstrap CI 95% cho ``weighted_diff`` và các so sánh với baseline.

    Thực hiện hai loại bootstrap:

    * **pair** — lấy mẫu có hoàn lại theo kỳ (đơn vị = một kỳ).
    * **block** — circular block bootstrap, kích thước khối = 3 tháng, để tính
      đến tự tương quan giữa các kỳ gần nhau.

    Cả hai loại đều dùng ``weight_col`` (mặc định ``total_orders``) làm trọng số
    khi tính ``weighted_diff`` trong mỗi mẫu bootstrap.

    Tham số:
        frame: DataFrame trả về bởi :func:`backtest` (cần có cột ``diff``,
            ``baseline_diff``, ``baseline_through_diff``, ``total_orders``).
        n_boot: Số lần lặp bootstrap (tối thiểu 10 000 để CI ổn định).
        seed: Seed cố định để tái hiện kết quả.
        alpha: Mức ý nghĩa; 0.05 → CI 95%.
        weight_col: Cột dùng làm trọng số cho ``np.average``.

    Trả về dict với các khoá:
        ``n_boot``, ``seed``, ``weight_col``,
        ``pair_ci_vs_zero``, ``pair_ci_vs_prior``, ``pair_ci_vs_through``,
        ``block_ci_vs_zero``, ``block_ci_vs_prior``, ``block_ci_vs_through``.

    Mỗi CI là tuple ``(lo_pp, hi_pp)`` — **đơn vị: điểm phần trăm (pp)**.

    Ghi chú về cách đọc:
        * ``ci_vs_zero``: CI của ``weighted_diff`` (DSS so với 0). Nếu CI không
          chứa 0 → nói "vượt" có cơ sở thống kê.
        * ``ci_vs_prior``: CI của ``dss_weighted_diff − baseline_prior_weighted``
          (chênh lệch DSS so với baseline lịch sử prior).
        * ``ci_vs_through``: CI của ``dss_weighted_diff − baseline_through_weighted``
          (chênh lệch DSS so với baseline through — so sánh chính vì through cùng
          lượng thông tin với DSS).
    """
    comp = frame.dropna(
        subset=["diff", "baseline_diff", "baseline_through_diff"]
    ).sort_values("period").reset_index(drop=True)

    if len(comp) == 0:
        empty_ci = (float("nan"), float("nan"))
        return {
            "n_boot": n_boot,
            "seed": seed,
            "weight_col": weight_col,
            "pair_ci_vs_zero": empty_ci,
            "pair_ci_vs_prior": empty_ci,
            "pair_ci_vs_through": empty_ci,
            "block_ci_vs_zero": empty_ci,
            "block_ci_vs_prior": empty_ci,
            "block_ci_vs_through": empty_ci,
        }

    diffs = comp["diff"].values
    base_diffs = comp["baseline_diff"].values
    through_diffs = comp["baseline_through_diff"].values
    weights = comp[weight_col].values
    n = len(diffs)

    def _w_avg(d: np.ndarray, w: np.ndarray) -> float:
        return float(np.average(d, weights=w))

    def _percentile_ci(samples: np.ndarray) -> tuple[float, float]:
        lo = float(np.percentile(samples, 100 * alpha / 2))
        hi = float(np.percentile(samples, 100 * (1 - alpha / 2)))
        return round(lo, 4), round(hi, 4)

    # ── Pair bootstrap ──────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    boot_dss_p = np.empty(n_boot)
    boot_prior_p = np.empty(n_boot)
    boot_through_p = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        w_s = weights[idx]
        boot_dss_p[i] = _w_avg(diffs[idx], w_s)
        boot_prior_p[i] = _w_avg(base_diffs[idx], w_s)
        boot_through_p[i] = _w_avg(through_diffs[idx], w_s)

    pair_ci_vs_zero = _percentile_ci(boot_dss_p * 100)
    pair_ci_vs_prior = _percentile_ci((boot_dss_p - boot_prior_p) * 100)
    pair_ci_vs_through = _percentile_ci((boot_dss_p - boot_through_p) * 100)

    # ── Block bootstrap (circular, block_size=3) ────────────────────────────
    block_size = 3
    n_blocks = int(np.ceil(n / block_size))
    rng_blk = np.random.default_rng(seed)
    boot_dss_b = np.empty(n_boot)
    boot_prior_b = np.empty(n_boot)
    boot_through_b = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng_blk.integers(0, n, size=n_blocks)
        idx = np.concatenate(
            [np.arange(s, s + block_size) % n for s in starts]
        )[:n]
        w_s = weights[idx]
        boot_dss_b[i] = _w_avg(diffs[idx], w_s)
        boot_prior_b[i] = _w_avg(base_diffs[idx], w_s)
        boot_through_b[i] = _w_avg(through_diffs[idx], w_s)

    block_ci_vs_zero = _percentile_ci(boot_dss_b * 100)
    block_ci_vs_prior = _percentile_ci((boot_dss_b - boot_prior_b) * 100)
    block_ci_vs_through = _percentile_ci((boot_dss_b - boot_through_b) * 100)

    return {
        "n_boot": n_boot,
        "seed": seed,
        "weight_col": weight_col,
        "pair_ci_vs_zero": pair_ci_vs_zero,
        "pair_ci_vs_prior": pair_ci_vs_prior,
        "pair_ci_vs_through": pair_ci_vs_through,
        "block_ci_vs_zero": block_ci_vs_zero,
        "block_ci_vs_prior": block_ci_vs_prior,
        "block_ci_vs_through": block_ci_vs_through,
    }


def main() -> None:
    o = M.load_orders()

    print("## Thông tin dữ liệu")
    print(f"- Số dòng (đơn, tuyến): {len(o)}")
    print(f"- Tỷ lệ trễ toàn hệ thống: {o.is_late.mean():.6f}")

    print("\n## Backtest theo min_orders")
    main_frame = None
    for min_orders in (30, 50, 100):
        frame, summary = backtest(
            o, min_orders=min_orders, baseline=True, baseline_through=True
        )
        print(f"\n### min_orders={min_orders}")
        print(_md_table(frame))
        print("\nTóm tắt:", summary)
        if min_orders == 30:
            main_frame = frame
            print("\n#### So sánh baseline lịch sử (min_orders=30)")
            print(
                _md_table(
                    frame[
                        [
                            "period",
                            "flagged_routes",
                            "baseline_routes",
                            "baseline_through_routes",
                            "diff",
                            "baseline_diff",
                            "baseline_through_diff",
                        ]
                    ]
                )
            )

    print("\n## Bootstrap CI (min_orders=30, n_boot=10 000, seed=42, trọng số=total_orders)")
    ci = bootstrap_ci(main_frame, n_boot=10_000, seed=42, weight_col="total_orders")
    print(f"- weight_col: {ci['weight_col']}, seed: {ci['seed']}")
    lo, hi = ci["pair_ci_vs_zero"]
    print(f"\n### Pair bootstrap (resample kỳ)")
    print(f"  vs 0 (DSS > 0):     [{lo:+.2f}; {hi:+.2f}] pp")
    lo, hi = ci["pair_ci_vs_prior"]
    print(f"  vs prior:           [{lo:+.2f}; {hi:+.2f}] pp")
    lo, hi = ci["pair_ci_vs_through"]
    print(f"  vs through (so sánh chính): [{lo:+.2f}; {hi:+.2f}] pp")
    lo, hi = ci["block_ci_vs_zero"]
    print(f"\n### Block bootstrap (khối 3 tháng, circular)")
    print(f"  vs 0 (DSS > 0):     [{lo:+.2f}; {hi:+.2f}] pp")
    lo, hi = ci["block_ci_vs_prior"]
    print(f"  vs prior:           [{lo:+.2f}; {hi:+.2f}] pp")
    lo, hi = ci["block_ci_vs_through"]
    print(f"  vs through (so sánh chính): [{lo:+.2f}; {hi:+.2f}] pp")
    print()
    lo_z, hi_z = ci["pair_ci_vs_zero"]
    lo_t, hi_t = ci["pair_ci_vs_through"]
    print(f"Kết luận pair bootstrap:")
    print(f"  DSS vs 0:     CI=[{lo_z:+.2f}; {hi_z:+.2f}] → {'CI không chứa 0 → có thể nói vượt 0' if lo_z > 0 else 'CI chứa 0 → không nói vượt'}")
    print(f"  DSS vs through: CI=[{lo_t:+.2f}; {hi_t:+.2f}] → {'CI không chứa 0 → DSS vượt through' if lo_t > 0 else 'CI chứa 0 → không nói vượt through'}")

    print("\n## Độ nhạy ngưỡng")
    print(_md_table(threshold_sensitivity(o)))

    print("\n## Top 3 tuyến")
    print(_md_table(top_routes_report(o, n=3)))

    print("\n## Thời gian âm")
    print("Thống kê cấp (đơn, tuyến):", negative_rows_summary(o))
    print(_md_table(negative_time_comparison(o, n=3)))


if __name__ == "__main__":
    main()
