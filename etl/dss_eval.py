"""Đánh giá mô hình DSS: backtest, độ nhạy ngưỡng, top tuyến, thời gian âm.

Module này chỉ đọc dữ liệu đã xử lý và gọi các hàm trong ``etl.dss_models``.
Không sửa dữ liệu kho, không phụ thuộc Django.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.dss_eval
    from . import dss_attrib as ATTRIB
    from . import dss_models as M
    from .config import (
        RAW_ORDER_ITEMS,
        RAW_ORDER_PAYMENTS,
        RAW_ORDER_REVIEWS,
        RAW_ORDERS,
    )
except ImportError:  # chạy trực tiếp: python etl/dss_eval.py
    import dss_attrib as ATTRIB
    import dss_models as M
    from config import (
        RAW_ORDER_ITEMS,
        RAW_ORDER_PAYMENTS,
        RAW_ORDER_REVIEWS,
        RAW_ORDERS,
    )


def raw_data_summary() -> dict:
    """Đếm đơn bị loại và share bản ghi suy biến từ dữ liệu gốc."""
    orders = pd.read_csv(RAW_ORDERS)
    items = pd.read_csv(RAW_ORDER_ITEMS)
    payments = pd.read_csv(RAW_ORDER_PAYMENTS)
    reviews = pd.read_csv(RAW_ORDER_REVIEWS)

    status = orders["order_status"].value_counts(dropna=False).to_dict()
    delivered = orders[orders["order_status"] == "delivered"].copy()
    time_cols = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in time_cols:
        delivered[col] = pd.to_datetime(delivered[col])
    delivered_clean = delivered.dropna(subset=time_cols)

    payment_rows = payments.groupby("order_id").agg(
        n_rows=("payment_sequential", "size"),
        n_types=("payment_type", "nunique"),
    )
    review_rows = reviews.groupby("order_id").size()

    return {
        "orders": int(len(orders)),
        "status": {str(k): int(v) for k, v in status.items()},
        "non_delivered": int(len(orders) - len(delivered)),
        "delivered": int(len(delivered)),
        "delivered_dropna": int(len(delivered_clean)),
        "delivered_dropped_nan_time": int(len(delivered) - len(delivered_clean)),
        "item_rows": int(len(items)),
        "item_orders": int(items["order_id"].nunique()),
        "delivered_item_rows": int(items["order_id"].isin(delivered_clean["order_id"]).sum()),
        "payment_orders": int(len(payment_rows)),
        "payment_multi_row_share": float((payment_rows["n_rows"] > 1).mean()),
        "payment_multi_type_share": float((payment_rows["n_types"] > 1).mean()),
        "review_orders": int(len(review_rows)),
        "review_multi_share": float((review_rows > 1).mean()),
    }


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
    any_negative = (o[["approval", "prep", "transit"]] < 0).any(axis=1)
    return {
        "order_route_rows": int(len(o)),
        "approval_negative": int((o["approval"] < 0).sum()),
        "prep_negative": int((o["prep"] < 0).sum()),
        "transit_negative": int((o["transit"] < 0).sum()),
        "any_negative": int(any_negative.sum()),
        "nan_stage": int(o[["approval", "prep", "transit"]].isna().any(axis=1).sum()),
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
    routes = list(M.route_priority(o[o["stage_valid"]], top=n, ensure_red=False)["route"])
    clean = o[o["stage_valid"]].copy()
    removed = ~o["stage_valid"]

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


def _attrib_shares(frame: pd.DataFrame) -> dict:
    """Tỷ trọng 4 nguyên nhân trên toàn bộ đơn trễ: 3 stage + residual promise."""
    late = float(frame["late_actual"].mean())
    out = {"orders": int(len(frame)), "late_rate": late}
    if late <= 0:
        return out
    for stage in ATTRIB.STAGES:
        out[f"share_{stage}"] = float(frame[f"phi_{stage}"].mean()) / late
    out["share_promise"] = float(frame["late_benchmark"].mean()) / late
    return out


def attribution_report(o: pd.DataFrame) -> None:
    """In attribution theo thiết kế peer group từng giai đoạn, q=0,5 và 0,25."""
    print("\n## Attribution (peer group theo giai đoạn + Shapley)")
    print(
        "- Thiết kế: approval theo payment_type; prep theo weight_band; "
        "transit theo distance_band (decile khoảng cách toàn cục, XUYÊN tuyến)."
    )
    print(
        '- Fallback: nhóm < min_orders hoặc khóa "NA" dùng median toàn cục '
        "của chính giai đoạn."
    )
    print(
        "- Sensitivity chỉ q=0,25 và q=0,5. q=0,75 bị loại: benchmark 75th "
        "percentile chậm hơn actual, phi âm, phân rã không hợp lệ."
    )
    print(
        "- NHÃN: `cause_share_*`/`share_promise` là TỶ TRỌNG trong tập ĐƠN TRỄ, "
        "KHÔNG phải tỷ lệ trễ. Transit là khâu dài nhất nên chiếm tỷ trọng lớn "
        "là điều dễ hiểu."
    )
    print(
        "- Cột `orders` đếm ĐƠN-TUYẾN (order-route), không phải đơn hàng duy nhất."
    )
    print(
        "- Giá trị DSS nằm ở so sánh giữa các tuyến + số đơn trễ có thể tránh; "
        "phần promise chỉ nêu dạng khoảng theo q (≈1–13% toàn hệ thống ở "
        "q=0,25–0,5), không kết luận mạnh."
    )

    att_reference = None
    for q in (0.5, 0.25):
        bench = ATTRIB.fit_benchmarks(o, quantile=q)
        att = ATTRIB.attribute(o, bench)
        if q == 0.5:
            att_reference = att
        print(f"\n### q={q}")
        print("- Bất biến:", ATTRIB.check_attrib(att))
        levels = {
            stage: att[f"benchmark_level_{stage}"].value_counts(normalize=True).round(6).to_dict()
            for stage in ATTRIB.STAGES
        }
        print("- Fallback theo giai đoạn:", levels)
        shares = _attrib_shares(att)
        print(
            "- Toàn hệ thống:",
            {k: round(v, 6) for k, v in shares.items()},
        )
        summary = ATTRIB.attribution_summary(att, min_orders=30)
        view = summary.sort_values("orders", ascending=False).head(5)[
            [
                "route",
                "orders",
                "late_rate",
                "cause_share_approval",
                "cause_share_prep",
                "cause_share_transit",
                "share_promise",
                "phi_transit",
                "top_stage",
            ]
        ].copy()
        for col in view.columns:
            if col not in {"route", "orders", "top_stage"}:
                view[col] = view[col].round(6)
        print(_md_table(view))
        if q == 0.5:
            for route in ("SP->RJ", "SP->SP"):
                sub = att[att["route"] == route]
                late = float(sub["late_actual"].mean())
                promise_share = (
                    float(sub["late_benchmark"].mean()) / late if late > 0 else float("nan")
                )
                print(
                    f"- {route}: phi_transit={sub['phi_transit'].mean():.6f} "
                    f"({sub['phi_transit'].mean() * 100:.4f} pp), "
                    f"late_rate={late:.6f}, "
                    f"share_promise (tỷ trọng trong đơn trễ)={promise_share:.6f}"
                )

    if att_reference is not None:
        print(
            "- Đánh giá xấu (late vs on-time):",
            ATTRIB.bad_review_uplift(att_reference),
        )


def _promise_share(o: pd.DataFrame, route: str, quantile: float) -> float:
    """Tỷ trọng residual promise trong đơn trễ của một tuyến, tại một q."""
    bench = ATTRIB.fit_benchmarks(o, quantile=quantile)
    att = ATTRIB.attribute(o, bench)
    sub = att[att["route"] == route]
    late = float(sub["late_actual"].mean())
    return float(sub["late_benchmark"].mean()) / late if late > 0 else float("nan")


def promise_policy_report(o: pd.DataFrame) -> None:
    """In S3: hiệu chỉnh cam kết theo ô route×weight_band bằng Q95 lead time."""
    c = ATTRIB.promise_calibration(o)
    print("\n## Promise calibration (S3: route × weight_band, Q95)")
    print(
        "- Đơn vị: ĐƠN-TUYẾN (order-route). Nhóm route × weight_band; "
        f"ô < {c.attrs['min_orders']} đơn-tuyến bị loại khỏi bảng."
    )
    print(
        "- needed_days = ceil(Q95 total_lead_days); "
        "gap_days = median promise_days − needed_days."
    )
    print(
        f"- Nhãn: tight nếu gap < −{c.attrs['tolerance_days']:g} ngày; "
        f"loose nếu gap > +{c.attrs['tolerance_days']:g} ngày; còn lại ok."
    )
    print(
        "- avoidable_orders = số đơn ĐANG TRỄ nhưng sẽ đúng hạn nếu đặt "
        "promise = needed_days."
    )
    print(
        "- CẢNH BÁO: đổi promise = đổi ĐỊNH NGHĨA trễ, KHÔNG rút ngắn thời "
        "gian giao thực tế; không đọc là 'giảm trễ' vận hành."
    )
    print(
        f"- Ô giữ/loại: {c.attrs['n_cells_kept']}/{c.attrs['n_cells_total']} "
        f"(loại {c.attrs['n_cells_small']} ô nhỏ = "
        f"{c.attrs['n_orders_small_cells']} đơn-tuyến)."
    )
    print(
        f"- Đơn-tuyến trong ô đủ mẫu: {c.attrs['n_orders_kept']}/"
        f"{c.attrs['n_orders_total']}."
    )
    counts = c.attrs["label_counts"]
    print(
        f"- Số ô tight/ok/loose: "
        f"{counts.get('tight', 0)}/{counts.get('ok', 0)}/{counts.get('loose', 0)}."
    )
    kept = c.attrs["n_orders_kept"]
    late = c.attrs["late_orders_kept"]
    avoidable = c.attrs["avoidable_orders"]
    cal_late = c.attrs["calibrated_late_orders"]
    print(
        f"- Tổng đơn trễ có thể tránh (đổi định nghĩa): {avoidable}/{late} "
        f"đơn-tuyến trễ."
    )
    if kept:
        print(
            f"- Tỷ lệ trễ hiện tại (ô đủ mẫu): {late / kept:.6f}; "
            f"nếu promise = needed_days: {cal_late / kept:.6f}."
        )

    cols = [
        "route",
        "weight_band",
        "n_orders",
        "median_promise_days",
        "needed_days",
        "gap_days",
        "label",
        "late_orders",
        "avoidable_orders",
        "calibrated_late_rate",
    ]
    view = c.head(10)[cols].copy()
    for col in ("median_promise_days", "needed_days", "gap_days", "calibrated_late_rate"):
        view[col] = view[col].round(6)
    print("\n### Top 10 ô theo số đơn trễ có thể tránh")
    print(_md_table(view))

    print("\n### SP->SP (kiểm riêng)")
    sp = c[c["route"] == "SP->SP"][cols].copy()
    if len(sp):
        for col in ("median_promise_days", "needed_days", "gap_days", "calibrated_late_rate"):
            sp[col] = sp[col].round(6)
        print(_md_table(sp))
    else:
        print("- Không có ô SP->SP đủ mẫu.")
    s50 = _promise_share(o, "SP->SP", 0.5)
    s25 = _promise_share(o, "SP->SP", 0.25)
    print(
        f"- share_promise SP->SP (tỷ trọng trong đơn trễ): "
        f"q=0,5 = {s50:.6f} ({s50 * 100:.4f}%); "
        f"q=0,25 = {s25:.6f} ({s25 * 100:.4f}%)."
    )
    if len(sp):
        labels = sp["label"].value_counts().to_dict()
        print(f"- Nhãn S3 tại SP->SP: {labels}.")
        if bool((sp["label"] == "tight").all()):
            print(
                "- S3 (Q95 lead time) ủng hộ 'cam kết chặt' tại SP->SP: "
                "mọi ô đủ mẫu có promise < Q95."
            )
        elif bool((sp["label"] == "tight").any()):
            print(
                "- S3 chỉ ủng hộ 'cam kết chặt' ở một phần ô SP->SP; "
                "không kết luận cho toàn tuyến."
            )
        else:
            print(
                "- S3 KHÔNG ủng hộ 'cam kết chặt' tại SP->SP "
                "(không ô đủ mẫu nào tight)."
            )
    print(
        "- Lưu ý: share_promise phụ thuộc mạnh vào q của benchmark; q=0,5 và "
        "q=0,25 cho hai bức tranh khác nhau. S3 dùng Q95 nên là lát cắt "
        "'mức phục vụ 95%', không đồng nhất với benchmark q=0,5."
    )


def feasible_cut_report(o: pd.DataFrame) -> None:
    """In S4: feasible max cut theo peer P25 + bootstrap CI + bảng cắt biên."""
    table = ATTRIB.feasible_cut_table(o, top=10, n_boot=300, seed=42)
    print("\n## Feasible max cut (S4: peer P25 + bootstrap 300×, seed 42)")
    print(
        "- Peer P25 dùng CÙNG định nghĩa peer với S1: approval theo payment_type; "
        "prep theo weight_band; transit theo distance_band (decile khoảng cách "
        "toàn cục, XUYÊN tuyến)."
    )
    print(
        "- cut_s = max(0, mean(actual_s) − mean(peer_p25_s)); mô phỏng bằng "
        "scenario, chặn theo thời gian thực tế từng đơn."
    )
    print(
        "- Đây là MÔ PHỎNG theo luật, không có counterfactual thật: nói "
        "'NẾU cắt được ... THÌ ƯỚC TÍNH', không nói 'sẽ giảm'."
    )
    print(
        "- Bootstrap 300 lần theo đơn-tuyến trong mỗi tuyến; CI 95% cho mức "
        "giảm tỷ lệ trễ (điểm phần trăm). CI chứa 0 → 'chưa đủ bằng chứng'."
    )
    if len(table) == 0:
        print("- Không có tuyến đủ mẫu.")
        return
    print(
        f"- Tuyến đủ mẫu {table.attrs['min_orders']} đơn-tuyến: "
        f"{table.attrs['n_routes_eligible']}/{table.attrs['n_routes_total']}; "
        f"bootstrap {table.attrs['n_routes_returned']} tuyến."
    )
    cols = [
        "route",
        "n_orders",
        "cut_approval",
        "cut_prep",
        "cut_transit",
        "total_cut_days",
        "baseline_late_rate",
        "projected_late_rate",
        "avoided_orders",
        "delta_pp",
        "delta_ci_low_pp",
        "delta_ci_high_pp",
        "status",
    ]
    view = table[cols].copy()
    for col in cols:
        if col not in {"route", "n_orders", "avoided_orders", "status"}:
            view[col] = view[col].round(6)
    print("\n### Top 10 tuyến theo số đơn trễ có thể tránh")
    print(_md_table(view))

    print(
        "\n### Kiểm tra H10: cắt 1 ngày mỗi giai đoạn tại SP->RJ "
        "(một giai đoạn tại một thời điểm)"
    )
    for stage in ATTRIB.STAGES:
        result = M.scenario(o, "SP->RJ", {stage: 1})
        print(
            f"- {stage}: projected={result['projected']:.6f}, "
            f"avoided={result['avoided']} "
            f"(baseline={result['baseline']:.6f})"
        )

    top_route = str(table.iloc[0]["route"])
    marginal = ATTRIB.marginal_cut_table(o, top_route)
    for col in ("cut_days", "projected_late_rate", "marginal_avoided_per_day"):
        marginal[col] = marginal[col].round(6)
    print(
        f"\n### Cắt biên tại {top_route} (mỗi giai đoạn cắt riêng, "
        f"các giai đoạn khác = 0)"
    )
    print(_md_table(marginal))


def seller_report(o: pd.DataFrame) -> None:
    """In S5: scorecard + portfolio người bán trên đơn single-seller."""
    card = M.seller_scorecard(o)
    port = M.seller_portfolio(o, scorecard=card, top=10)
    summary = port["summary"]
    print("\n## Seller scorecard (S5: chỉ đơn single-seller)")
    print(
        "- Đơn vị: ĐƠN HÀNG (unique order_id), không phải đơn-tuyến. "
        "Đơn nhiều người bán bị loại vì không quy được trách nhiệm cho một seller."
    )
    print(
        f"- Loại {summary['n_orders_multi_seller']} đơn nhiều seller + "
        f"{summary['n_orders_missing_seller']} đơn thiếu seller_id = "
        f"{summary['excluded_order_share']:.4%} số đơn "
        f"({summary['excluded_order_route_share']:.4%} số đơn-tuyến)."
    )
    print(
        f"- Đơn single-seller dùng được: {summary['orders']}/"
        f"{summary['n_orders_total']}; {summary['n_sellers']} seller; "
        f"tỷ lệ trễ chung {summary['late_rate']:.6f}."
    )
    print(
        "- `level`: red nếu Wilson low > tỷ lệ chung; amber nếu điểm ước lượng "
        "> chung nhưng CI còn chứa chung; ok còn lại. CI Wilson giả định các "
        "đơn độc lập (V2)."
    )
    print(
        "- `segment`: ưu tiên (đủ mẫu + red/amber), ổn định (đủ mẫu + ok), "
        "cần thêm dữ liệu (dưới min_orders)."
    )
    print(
        "- `bad_review_rate` (review ≤ 2) chỉ là LIÊN HỆ, không phải nhân quả; "
        "đơn trễ có review xấu nhiều hơn nhưng không chứng minh trễ gây review xấu."
    )
    print(
        f"- Seller đủ mẫu: {summary['n_sellers_scored']}/{summary['n_sellers']} "
        f"(min_orders={summary['min_orders']})."
    )

    if len(port["segments"]):
        segments = port["segments"].copy()
        for col in ("late_rate", "late_orders_share", "gmv_share"):
            segments[col] = segments[col].round(6)
        print("\n### Phân khúc người bán")
        print(_md_table(segments))

    print(
        f"\n### Top 10 seller theo số đơn trễ "
        f"(chiếm {summary['top_seller_share_late_orders']:.4%} đơn trễ, "
        f"{summary['top_seller_share_gmv']:.4%} GMV)"
    )
    cols = [
        "seller_id",
        "orders",
        "late_orders",
        "late_rate",
        "wilson_low",
        "wilson_high",
        "late_rate_lift",
        "level",
        "segment",
        "bad_review_rate",
        "gmv_share",
    ]
    view = port["top_sellers"][cols].copy()
    for col in cols:
        if col not in {
            "seller_id",
            "orders",
            "late_orders",
            "level",
            "segment",
        }:
            view[col] = view[col].round(6)
    print(_md_table(view))


def main() -> None:
    raw = M.load_orders(include_invalid=True)
    o = M.load_orders()

    print("## Thông tin dữ liệu")
    print("- Tóm tắt dữ liệu gốc:", raw_data_summary())
    print(f"- Số dòng (đơn, tuyến) dùng cho DSS: {len(o)}")
    print(f"- Số đơn duy nhất: {o.order_id.nunique()}")
    print(
        "- Tỷ lệ trễ trên đơn-tuyến: "
        f"{o.is_late.mean():.6f} ({o.is_late.mean() * 100:.4f}%)"
    )
    print(
        "- Tỷ lệ trễ trên đơn đã giao (unique order_id): "
        f"{o.attrs['late_rate_order']:.6f} ({o.attrs['late_rate_order'] * 100:.4f}%)"
    )
    print(
        "- Loại do giai đoạn âm/NaN: "
        f"{o.attrs['excluded_stage_invalid_rows']} order-route "
        f"({o.attrs['excluded_stage_invalid_share']:.4%}), "
        f"prep<0={o.attrs['excluded_prep_negative']}, "
        f"transit<0={o.attrs['excluded_transit_negative']}, "
        f"nan={o.attrs['excluded_nan_stage']}"
    )
    print(
        "- promise_days − (total_lead_days − delay_days) max abs: "
        f"{o.attrs['promise_gap_max']:.3g}"
    )
    mismatch = int((o.is_late != (o.total_lead_days > o.promise_days)).sum())
    print(f"- late0 != (delay_days > 0): {mismatch} dòng")
    multi_route = int((o.groupby("order_id").size() > 1).sum())
    multi_seller = int((o.groupby("order_id").seller_id.nunique() > 1).sum())
    print(f"- Đơn nằm trên >1 tuyến: {multi_route}")
    print(f"- Đơn có >1 người bán: {multi_seller}")
    print(f"- GMV (tổng price trong đơn-tuyến): {o.gmv.sum():.2f}")
    print(f"- Số order-route trước khi loại (gồm dòng không hợp lệ): {len(raw)}")

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
    print("Thống kê cấp (đơn, tuyến):", negative_rows_summary(raw))
    print("Đã loại khỏi DSS:", o.attrs["excluded_stage_invalid_rows"], "order-route")
    print(_md_table(negative_time_comparison(raw, n=3)))

    attribution_report(o)

    promise_policy_report(o)

    feasible_cut_report(o)

    seller_report(o)


if __name__ == "__main__":
    main()
