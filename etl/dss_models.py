"""Model Base của DSS: các mô hình phân tích chạy trên dữ liệu kho."""

import math

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.<script>
    from .config import PROCESSED_DIR
except ImportError:  # chạy trực tiếp: python etl/dss_models.py
    from config import PROCESSED_DIR

# Ba giai đoạn của vòng đời đơn hàng được dùng làm biến giải thích.
STAGES = ["approval", "prep", "transit"]
OWNER = {
    "approval": "Duyệt thanh toán",
    "prep": "Người bán",
    "transit": "Đơn vị vận chuyển",
}
RULES = {
    "approval": "Rà soát khâu duyệt thanh toán của tuyến này.",
    "prep": "Làm việc với nhóm người bán trên tuyến để rút ngắn thời gian chuẩn bị hàng.",
    "transit": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng.",
}


def load_orders() -> pd.DataFrame:
    """Đọc Fact + 3 Dim, trả về bảng 1 dòng = 1 (đơn hàng, tuyến).

    Lưu ý: Fact có hạt là item nên phải gộp về cấp đơn hàng. Một đơn có thể
    phát sinh từ nhiều bang người bán, khi đó đơn xuất hiện ở nhiều tuyến
    (khóa là cặp order_id + route, không phải order_id đơn thuần).
    """
    f = pd.read_csv(PROCESSED_DIR / "cleaned_fact_orders.csv")
    loc = pd.read_csv(PROCESSED_DIR / "cleaned_dim_location.csv")[["location_id", "state"]]
    t = pd.read_csv(PROCESSED_DIR / "cleaned_dim_time.csv")[["time_id", "year", "month"]]
    p = pd.read_csv(PROCESSED_DIR / "cleaned_dim_product.csv")

    f = (
        f.merge(
            loc.rename(columns={"location_id": "customer_location_id", "state": "cust_state"}),
            on="customer_location_id",
            how="left",
        )
        .merge(
            loc.rename(columns={"location_id": "seller_location_id", "state": "seller_state"}),
            on="seller_location_id",
            how="left",
        )
        .merge(t, on="time_id", how="left")
        .merge(p, on="product_id", how="left")
    )

    # Fact không có cột is_late; quy ước đơn trễ khi delay_days > 0.
    f["is_late"] = f["delay_days"] > 0
    f["route"] = f["seller_state"] + "->" + f["cust_state"]
    f["period"] = f["year"] * 100 + f["month"]

    return f.groupby(["order_id", "route"], as_index=False).agg(
        period=("period", "first"),
        seller_state=("seller_state", "first"),
        cust_state=("cust_state", "first"),
        is_late=("is_late", "max"),
        delay_days=("delay_days", "first"),
        complaint=("has_logistics_complaint", "max"),
        approval=("approval_time_days", "first"),
        prep=("seller_prep_time_days", "first"),
        transit=("carrier_transit_time_days", "first"),
        freight=("freight_value", "sum"),
        n_items=("order_item_id", "count"),
        payment_type=("payment_type", "first"),
        review_score=("review_score", "first"),
        category=("category_name_english", "first"),
        weight=("weight_g", "sum"),
        volume=("volume_cm3", "sum"),
    )


def route_priority(o, red=2.0, amber=1.5, min_orders=100, top=10):
    """Khối 1: xếp hạng tuyến theo mức vượt tỷ lệ trễ toàn hệ thống.

    ``red``/``amber`` là bội số so với tỷ lệ trễ chung; chỉ giữ tuyến có tối
    thiểu ``min_orders`` đơn để tránh kết luận từ mẫu quá nhỏ.
    """
    overall = o.is_late.mean()
    g = (
        o.groupby("route")
        .agg(
            orders=("order_id", "nunique"),
            late_orders=("is_late", "sum"),
            late_rate=("is_late", "mean"),
        )
        .reset_index()
    )
    g = g[g.orders >= min_orders]
    g["level"] = np.where(
        g.late_rate >= overall * red,
        "red",
        np.where(g.late_rate >= overall * amber, "amber", "ok"),
    )
    return g[g.level != "ok"].sort_values("late_orders", ascending=False).head(top)


def root_cause(o, route):
    """Khối 2: tìm giai đoạn vượt mức trung bình hệ thống nhiều nhất.

    ``stage`` luôn là giai đoạn có phần vượt lớn nhất (kể cả khi mọi giai đoạn
    đều không vượt trung bình) để các hàm khác giữ nguyên hợp đồng dữ liệu.
    ``has_bottleneck`` cho biết thực sự có giai đoạn nào vượt trung bình không.
    """
    r = o[o.route == route]
    exc = {s: float(r[s].mean() - o[s].mean()) for s in STAGES}
    worst = max(exc, key=exc.get)
    has_bottleneck = max(exc.values()) > 0
    return {
        "stage": worst,
        "owner": OWNER[worst],
        "excess": exc,
        "has_bottleneck": has_bottleneck,
        "recommendation": (
            RULES[worst]
            if has_bottleneck
            else "Không có giai đoạn nào vượt mức trung bình hệ thống."
        ),
    }


def scenario(o, route=None, cut=None):
    """Khối 3 (What-if): cắt giảm thời gian từng giai đoạn (ngày), tính lại tỷ lệ trễ.

    Mức cắt của mỗi giai đoạn bị chặn bởi thời gian thực tế của đơn
    (``np.minimum``) và không nhận giá trị âm.
    """
    cut = {"approval": 0, "prep": 0, "transit": 0, **(cut or {})}
    d = o if route is None else o[o.route == route]
    total = sum(
        np.minimum(max(0.0, float(v)), d[s].clip(lower=0)) for s, v in cut.items()
    )
    new_late = (d.delay_days - total) > 0
    return {
        "orders": len(d),
        "baseline": float(d.is_late.mean()),
        "projected": float(new_late.mean()),
        "avoided": int(d.is_late.sum() - new_late.sum()),
    }


def sensitivity(o, route, stage, max_days=5):
    """Phân tích độ nhạy: tỷ lệ trễ dự báo khi cắt 0..max_days ngày ở một giai đoạn."""
    return [
        {"cut": x, "projected": scenario(o, route, {stage: x})["projected"]}
        for x in range(max_days + 1)
    ]


def goal_seek_promise(o, route, target=0.05):
    """Tìm mục tiêu 1: cần kéo dài cam kết giao hàng bao nhiêu ngày để tỷ lệ trễ <= target."""
    d = o[o.route == route]
    x = max(0, math.ceil(d.delay_days.quantile(1 - target)))
    return {"extra_days": x, "late_after": float((d.delay_days - x > 0).mean())}


def goal_seek_cut(o, route, stage, target=0.05, step=0.5, max_days=10):
    """Tìm mục tiêu 2: cần cắt tối thiểu bao nhiêu ngày ở một giai đoạn (None nếu không đạt)."""
    x = 0.0
    while x <= max_days:
        if scenario(o, route, {stage: x})["projected"] <= target:
            return x
        x += step
    return None
