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


def backtest(
    o: pd.DataFrame,
    min_orders: int = 30,
    min_period_orders: int = 500,
    start_year: int = 2017,
    red: float = 2.0,
    amber: float = 1.5,
):
    """Backtest một bước: tuyến gắn cờ ở kỳ t có trễ hơn ở kỳ t+1 không?

    Quy trình cho từng kỳ t:
    1. Chạy ``route_priority`` trên riêng dữ liệu kỳ t để lấy tuyến đỏ/vàng.
    2. Sang kỳ t+1, so tỷ lệ trễ của các đơn thuộc tuyến đã gắn cờ với phần còn lại.
    3. Bỏ kỳ 2016 (quá ít đơn) và kỳ không có kỳ kế tiếp liền kề theo lịch.

    Trả về ``(periods, summary)``:
    - ``periods``: DataFrame mỗi dòng một kỳ, có cột ``diff = flagged - other``.
    - ``summary``: dict tóm tắt một dòng (số kỳ cờ trễ hơn / số kỳ so sánh được,
      chênh lệch trung bình có trọng số theo tổng số đơn của kỳ t+1).

    Kỳ không có tuyến nào gắn cờ vẫn xuất hiện trong ``periods`` với
    ``flagged_late_rate``/``diff`` bằng NaN, nhưng không được tính vào mẫu số
    ``periods_evaluated``.
    """
    periods = sorted({int(p) for p in o["period"].dropna().unique()})
    available = set(periods)
    rows = []

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
        mask = future["route"].isin(routes)
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

        rows.append(
            {
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
        )

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
    frame = pd.DataFrame(rows, columns=columns)
    comparable = frame.dropna(subset=["diff"])

    higher = int((comparable["diff"] > 0).sum())
    # weighted_diff: trung bình có trọng số của (flagged_late_rate - other_late_rate)
    # trọng số = total_orders kỳ t+1 (= flagged_orders + other_orders).
    # Lý do: kỳ có nhiều đơn hơn đại diện tốt hơn cho mẫu, và tỷ lệ trễ ổn định hơn.
    # Cách thay thế (trọng số = flagged_orders kỳ t+1) cho weighted_diff_flagged = +10.32 pp;
    # cách này nhấn mạnh các kỳ nhiều đơn thuộc nhóm gắn cờ hơn.
    # Số chính được chọn là weighted_diff với trọng số total_orders (+8.14 pp)
    # vì nó trung lập hơn và phù hợp với ý nghĩa "kỳ có nhiều dữ liệu quan trọng hơn".
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
        # Tham khảo: trọng số = flagged_orders kỳ t+1 (nhấn mạnh kỳ có nhiều đơn bị gắn cờ)
        "weighted_diff_flagged": weighted_diff_flagged,
        "mean_diff": (
            float(comparable["diff"].mean()) if len(comparable) else None
        ),
    }
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

    Mỗi dòng gồm số đơn, baseline, root cause (excess từng giai đoạn), kết quả
    cắt 1/3/5 ngày cho từng giai đoạn, goal seek cam kết và goal seek cắt.
    """
    priority = M.route_priority(o, top=n)
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
    routes = list(M.route_priority(o, top=n)["route"])
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


def main() -> None:
    o = M.load_orders()

    print("## Thông tin dữ liệu")
    print(f"- Số dòng (đơn, tuyến): {len(o)}")
    print(f"- Tỷ lệ trễ toàn hệ thống: {o.is_late.mean():.6f}")

    print("\n## Backtest theo min_orders")
    for min_orders in (30, 50, 100):
        frame, summary = backtest(o, min_orders=min_orders)
        print(f"\n### min_orders={min_orders}")
        print(_md_table(frame))
        print("\nTóm tắt:", summary)

    print("\n## Độ nhạy ngưỡng")
    print(_md_table(threshold_sensitivity(o)))

    print("\n## Top 3 tuyến")
    print(_md_table(top_routes_report(o, n=3)))

    print("\n## Thời gian âm")
    print("Thống kê cấp (đơn, tuyến):", negative_rows_summary(o))
    print(_md_table(negative_time_comparison(o, n=3)))


if __name__ == "__main__":
    main()
