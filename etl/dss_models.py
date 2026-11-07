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
BAD_REVIEW_MAX = 2  # Olist review_score 1..5; 1-2 là đánh giá xấu.
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


def load_orders(include_invalid: bool = False) -> pd.DataFrame:
    """Đọc Fact + 3 Dim, trả về bảng 1 dòng = 1 (đơn hàng, tuyến).

    Lưu ý: Fact có hạt là item nên phải gộp về cấp đơn hàng. Một đơn có thể
    phát sinh từ nhiều bang người bán, khi đó đơn xuất hiện ở nhiều tuyến
    (khóa là cặp order_id + route, không phải order_id đơn thuần).

    Dòng có bất kỳ giai đoạn nào < 0 hoặc NaN bị loại khỏi mọi thống kê DSS
    (không clip ngầm); số dòng bị loại lưu ở ``o.attrs``.
    """
    f = pd.read_csv(
        PROCESSED_DIR / "cleaned_fact_orders.csv",
        dtype={"customer_location_id": str, "seller_location_id": str},
    )
    loc = pd.read_csv(
        PROCESSED_DIR / "cleaned_dim_location.csv", dtype={"location_id": str}
    )[["location_id", "state"]]
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

    o = f.groupby(["order_id", "route"], as_index=False).agg(
        period=("period", "first"),
        seller_state=("seller_state", "first"),
        cust_state=("cust_state", "first"),
        seller_id=("seller_id", "first"),
        n_sellers=("seller_id", "nunique"),
        is_late=("is_late", "max"),
        delay_days=("delay_days", "first"),
        promise_days=("promise_days", "first"),
        total_lead_days=("total_lead_days", "first"),
        handoff_slack_days=("handoff_slack_days", "max"),
        distance_km=("distance_km", "first"),
        complaint=("has_logistics_complaint", "max"),
        approval=("approval_time_days", "first"),
        prep=("seller_prep_time_days", "first"),
        transit=("carrier_transit_time_days", "first"),
        price=("price", "sum"),
        freight=("freight_value", "sum"),
        n_items=("order_item_id", "count"),
        payment_type=("payment_type", "first"),
        review_score=("review_score", "first"),
        category=("category_name_english", "first"),
        weight=("weight_g", "sum"),
        volume=("volume_cm3", "sum"),
    )
    o = o.rename(columns={"price": "gmv"})

    # F5: loại order-route có giai đoạn âm/NaN, báo share thay vì clip.
    invalid = (o[STAGES] < 0).any(axis=1) | o[STAGES].isna().any(axis=1)
    n_all = len(o)
    o["stage_valid"] = ~invalid
    o.attrs["excluded_prep_negative"] = int((o["prep"] < 0).sum())
    o.attrs["excluded_transit_negative"] = int((o["transit"] < 0).sum())
    o.attrs["excluded_any_negative"] = int(
        (o[["approval", "prep", "transit"]] < 0).any(axis=1).sum()
    )
    o.attrs["excluded_nan_stage"] = int(o[STAGES].isna().any(axis=1).sum())
    if not include_invalid:
        o = o.loc[~invalid].copy()

    # F6: promise_days phải bằng total_lead_days − delay_days (sai số số học).
    gap = (o["promise_days"] - (o["total_lead_days"] - o["delay_days"])).abs()
    o.attrs["promise_gap_max"] = float(gap.max()) if len(gap) else 0.0
    o.attrs["excluded_stage_invalid_rows"] = int(invalid.sum())
    o.attrs["excluded_stage_invalid_share"] = (
        float(invalid.sum() / n_all) if n_all else 0.0
    )
    o.attrs["n_order_route"] = int(len(o))
    o.attrs["n_orders"] = int(o["order_id"].nunique())
    o.attrs["late_rate_order_route"] = float(o["is_late"].mean()) if len(o) else float("nan")
    # Tỷ lệ trễ cấp đơn: mỗi order_id chỉ tính 1 lần (đơn nhiều tuyến không nhân đôi).
    order_late = o.groupby("order_id")["is_late"].max()
    o.attrs["late_rate_order"] = float(order_late.mean()) if len(order_late) else float("nan")

    # weight_band: qcut 4 phần bằng nhau trên weight_g ở runtime.
    try:
        bands = pd.qcut(
            o["weight"], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop"
        )
    except ValueError:
        bands = pd.Series(pd.NA, index=o.index, dtype="object")
    if bands.isna().any() or bands.nunique(dropna=True) != 4:
        # Nhiều weight trùng (ví dụ 0) làm qcut gộp bin: chia theo rank để vẫn đủ 4 nhóm.
        bands = pd.qcut(
            o["weight"].rank(method="first"), q=4, labels=["Q1", "Q2", "Q3", "Q4"]
        )
    o["weight_band"] = bands.astype(str)

    return o


def wilson_interval(late_orders, orders, z=1.96):
    """Khoảng tin cậy Wilson 95% cho tỷ lệ trễ (``late_orders / orders``)."""
    n = int(orders)
    if n <= 0:
        return 0.0, 1.0
    p = float(late_orders) / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (
        z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    )
    return max(0.0, center - half), min(1.0, center + half)


def _single_seller_orders(o: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Gộp về cấp đơn và chỉ giữ đơn do **một người bán** phụ trách.

    Một đơn nhiều người bán không quy được trách nhiệm cho một seller, nên bị
    loại khỏi scorecard; số đơn và số đơn-tuyến bị loại được trả trong ``stats``
    để báo cáo minh bạch (không âm thầm bỏ).

    Trả về ``(order_frame, stats)``; ``order_frame`` có 1 dòng / đơn, cột
    ``is_late`` = max theo các tuyến của đơn, ``gmv`` = tổng, ``review_score`` =
    first. Đơn thiếu ``seller_id`` cũng bị loại và đếm riêng.
    """
    required = ["order_id", "seller_id", "is_late", "gmv", "review_score"]
    missing = [c for c in required if c not in o.columns]
    if missing:
        raise ValueError(f"Thiếu cột cho seller scorecard: {missing}")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để seller scorecard")

    sellers_per_order = o.groupby("order_id", dropna=False)["seller_id"].nunique(
        dropna=False
    )
    n_orders_total = int(sellers_per_order.size)
    single_ids = sellers_per_order[sellers_per_order == 1].index
    single_rows = o[o["order_id"].isin(single_ids) & o["seller_id"].notna()].copy()

    order = single_rows.groupby(["order_id", "seller_id"], as_index=False).agg(
        is_late=("is_late", "max"),
        gmv=("gmv", "sum"),
        review_score=("review_score", "first"),
    )
    n_orders_single = int(len(order))
    n_multi = int((sellers_per_order > 1).sum())
    stats = {
        "n_orders_total": n_orders_total,
        "n_orders_single_seller": n_orders_single,
        "n_orders_multi_seller": n_multi,
        "n_orders_missing_seller": int(n_orders_total - n_orders_single - n_multi),
        "excluded_order_share": (
            (n_orders_total - n_orders_single) / n_orders_total
            if n_orders_total
            else float("nan")
        ),
        "n_order_routes_total": int(len(o)),
        "n_order_routes_single_seller": int(len(single_rows)),
        "excluded_order_route_share": (
            1.0 - len(single_rows) / len(o) if len(o) else float("nan")
        ),
        "n_sellers": int(order["seller_id"].nunique()) if len(order) else 0,
        "system_late_rate": (
            float(order["is_late"].mean()) if len(order) else float("nan")
        ),
    }
    return order, stats


def seller_scorecard(o: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    """Scorecard cấp người bán, chỉ trên **đơn single-seller** (S5).

    Đơn vị là **đơn hàng** (không phải đơn-tuyến): một đơn nhiều tuyến của cùng
    một seller chỉ tính một lần; ``is_late`` = max, ``gmv`` = tổng. Đơn nhiều
    seller bị loại và share loại nằm trong ``.attrs``.

    Cột chính:

    - ``orders``, ``late_orders``, ``late_rate``, Wilson CI 95%.
    - ``late_rate_lift`` = late_rate / tỷ lệ trễ chung của đơn single-seller.
    - ``ci_status``: ``"cao hơn hệ thống"`` nếu Wilson low > hệ thống,
      ``"thấp hơn hệ thống"`` nếu Wilson high < hệ thống, còn lại
      ``"chưa phân biệt được"``.
    - ``level``: ``red`` nếu Wilson low > hệ thống; ``amber`` nếu điểm ước lượng
      > hệ thống nhưng CI còn chứa hệ thống; ``ok`` còn lại.
    - ``segment``: ``"ưu tiên"`` (đủ mẫu + red/amber), ``"ổn định"`` (đủ mẫu +
      ok), ``"cần thêm dữ liệu"`` (dưới ``min_orders``).
    - ``bad_review_rate`` (review_score ≤ 2) **chỉ là liên hệ**, không nhân quả.

    Sắp theo ``late_orders`` giảm dần (tác động), rồi ``orders`` giảm dần.
    """
    if min_orders < 1:
        raise ValueError("min_orders phải >= 1")

    order, stats = _single_seller_orders(o)
    columns = [
        "seller_id",
        "orders",
        "late_orders",
        "late_rate",
        "wilson_low",
        "wilson_high",
        "system_late_rate",
        "late_rate_lift",
        "ci_status",
        "level",
        "segment",
        "low_sample",
        "gmv",
        "gmv_share",
        "late_orders_share",
        "n_reviewed",
        "bad_review_orders",
        "bad_review_rate",
    ]
    if len(order) == 0:
        out = pd.DataFrame(columns=columns)
        out.attrs.update(stats)
        out.attrs["min_orders"] = int(min_orders)
        out.attrs["n_sellers_scored"] = 0
        out.attrs["level_counts"] = {}
        out.attrs["segment_counts"] = {}
        return out

    order = order.copy()
    order["bad_review"] = order["review_score"] <= BAD_REVIEW_MAX
    g = order.groupby("seller_id", as_index=False).agg(
        orders=("order_id", "nunique"),
        late_orders=("is_late", "sum"),
        gmv=("gmv", "sum"),
        n_reviewed=("review_score", "count"),
        bad_review_orders=("bad_review", "sum"),
    )
    g["late_rate"] = g["late_orders"] / g["orders"]
    g["bad_review_rate"] = np.where(
        g["n_reviewed"] > 0, g["bad_review_orders"] / g["n_reviewed"], np.nan
    )

    system_late = float(stats["system_late_rate"])
    g["system_late_rate"] = system_late
    g["late_rate_lift"] = np.where(
        system_late > 0, g["late_rate"] / system_late, np.nan
    )

    intervals = [
        wilson_interval(int(late), int(total))
        for late, total in zip(g["late_orders"], g["orders"])
    ]
    g["wilson_low"] = [interval[0] for interval in intervals]
    g["wilson_high"] = [interval[1] for interval in intervals]
    g["ci_status"] = np.select(
        [
            g["wilson_low"] > system_late,
            g["wilson_high"] < system_late,
        ],
        ["cao hơn hệ thống", "thấp hơn hệ thống"],
        default="chưa phân biệt được",
    )
    g["level"] = np.select(
        [g["wilson_low"] > system_late, g["late_rate"] > system_late],
        ["red", "amber"],
        default="ok",
    )
    g["low_sample"] = g["orders"] < min_orders
    scored = g["orders"] >= min_orders
    above = g["level"].isin(["red", "amber"])
    g["segment"] = np.select(
        [scored & above, scored & ~above],
        ["ưu tiên", "ổn định"],
        default="cần thêm dữ liệu",
    )

    total_late = int(g["late_orders"].sum())
    total_gmv = float(g["gmv"].sum())
    g["late_orders_share"] = (
        g["late_orders"] / total_late if total_late > 0 else np.nan
    )
    g["gmv_share"] = g["gmv"] / total_gmv if total_gmv > 0 else np.nan
    out = (
        g[columns]
        .sort_values(["late_orders", "orders"], ascending=False)
        .reset_index(drop=True)
    )
    out.attrs.update(stats)
    out.attrs["min_orders"] = int(min_orders)
    out.attrs["n_sellers_scored"] = int((out["orders"] >= min_orders).sum())
    out.attrs["level_counts"] = out["level"].value_counts().to_dict()
    out.attrs["segment_counts"] = out["segment"].value_counts().to_dict()
    return out


def seller_portfolio(
    o: pd.DataFrame,
    min_orders: int = 30,
    top: int = 10,
    scorecard: pd.DataFrame | None = None,
) -> dict:
    """Portfolio người bán: tổng quan, phân khúc và top seller theo tác động (S5).

    Chỉ dùng scorecard single-seller (tự tính nếu ``scorecard=None``). Trả về:

    - ``summary``: tổng số seller/đơn/đơn trễ/GMV, share loại đơn nhiều seller,
      mức tập trung của ``top`` seller (share đơn trễ và GMV).
    - ``segments``: bảng theo ``segment`` (ưu tiên / ổn định / cần thêm dữ liệu).
    - ``top_sellers``: top theo ``late_orders``, kèm CI và cờ mẫu nhỏ.

    Đây là mô tả **liên hệ**, không phải kết luận nhân quả về người bán.
    """
    if top < 1:
        raise ValueError("top phải >= 1")
    if scorecard is None:
        scorecard = seller_scorecard(o, min_orders=min_orders)
    required = [
        "seller_id",
        "orders",
        "late_orders",
        "gmv",
        "level",
        "segment",
    ]
    missing = [c for c in required if c not in scorecard.columns]
    if missing:
        raise ValueError(f"Thiếu cột scorecard: {missing}")

    if len(scorecard) == 0:
        return {
            "summary": dict(scorecard.attrs),
            "segments": pd.DataFrame(),
            "top_sellers": pd.DataFrame(),
        }

    total_orders = int(scorecard["orders"].sum())
    total_late = int(scorecard["late_orders"].sum())
    total_gmv = float(scorecard["gmv"].sum())
    top_sellers = scorecard.sort_values(
        ["late_orders", "orders"], ascending=False
    ).head(top).copy()

    segments = (
        scorecard.groupby("segment", as_index=False)
        .agg(
            n_sellers=("seller_id", "nunique"),
            orders=("orders", "sum"),
            late_orders=("late_orders", "sum"),
            gmv=("gmv", "sum"),
        )
    )
    segments["late_rate"] = segments["late_orders"] / segments["orders"]
    segments["late_orders_share"] = (
        segments["late_orders"] / total_late if total_late > 0 else np.nan
    )
    segments["gmv_share"] = (
        segments["gmv"] / total_gmv if total_gmv > 0 else np.nan
    )
    segment_order = {"ưu tiên": 0, "ổn định": 1, "cần thêm dữ liệu": 2}
    segments = (
        segments.assign(
            _order=segments["segment"].map(segment_order).fillna(99)
        )
        .sort_values("_order")
        .drop(columns="_order")
        .reset_index(drop=True)
    )

    summary = dict(scorecard.attrs)
    summary.update(
        {
            "n_sellers": int(scorecard["seller_id"].nunique()),
            "n_sellers_scored": int((scorecard["orders"] >= min_orders).sum()),
            "orders": total_orders,
            "late_orders": total_late,
            "late_rate": (
                total_late / total_orders if total_orders else float("nan")
            ),
            "gmv": total_gmv,
            "top_n": int(top),
            "top_seller_share_late_orders": (
                float(top_sellers["late_orders"].sum()) / total_late
                if total_late > 0
                else float("nan")
            ),
            "top_seller_share_gmv": (
                float(top_sellers["gmv"].sum()) / total_gmv
                if total_gmv > 0
                else float("nan")
            ),
            "level_counts": scorecard["level"].value_counts().to_dict(),
            "segment_counts": scorecard["segment"].value_counts().to_dict(),
        }
    )
    return {
        "summary": summary,
        "segments": segments,
        "top_sellers": top_sellers,
    }


def route_priority(
    o, red=2.0, amber=1.5, min_orders=100, top=10, ensure_red=True
):
    """Khối 1: xếp hạng tuyến theo mức vượt tỷ lệ trễ toàn hệ thống.

    ``red``/``amber`` là bội số so với tỷ lệ trễ chung; chỉ giữ tuyến có tối
    thiểu ``min_orders`` đơn để tránh kết luận từ mẫu quá nhỏ.

    Mặc định ``ensure_red=True``: trả **tất cả** tuyến đỏ trước (sắp theo
    ``late_orders`` giảm dần), rồi mới đến tuyến vàng cho đủ ``top``. Nếu số
    tuyến đỏ nhiều hơn ``top`` thì trả hết tuyến đỏ (nhiều hơn ``top``) để
    không che tuyến đỏ nào. ``ensure_red=False`` giữ cách xếp hạng cũ (thuần
    theo ``late_orders``, cắt đúng ``top``) cho các bảng chi tiết.

    Cột ``uncertain``: ``True`` khi cận dưới Wilson 95% của tuyến nằm dưới
    ngưỡng phân loại của chính mình (``ci_low < overall * red`` với tuyến đỏ;
    ``ci_low < overall * amber`` với tuyến vàng). Nghĩa là khoảng tin cậy
    **chứa** ngưỡng phân loại — tức nhãn đỏ/vàng chưa được xác nhận chắc chắn
    bởi CI. Cột này chỉ để **hiển thị cảnh báo trên UI**, không đổi ``level``,
    không đổi thứ tự xếp hạng, không đổi ``stage``/``has_bottleneck``.

    Sáu điều kiện khi ``uncertain=True`` đối với tuyến r:
      1. level=red  AND ci_low < overall × θ_red
      2. level=amber AND ci_low < overall × θ_amber
    (điều kiện 3–6 trong spec là các ví dụ cụ thể của hai điều kiện trên.)
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
    g = g[g.orders >= min_orders].copy()
    g["level"] = np.where(
        g.late_rate >= overall * red,
        "red",
        np.where(g.late_rate >= overall * amber, "amber", "ok"),
    )

    intervals = [
        wilson_interval(k, n) for k, n in zip(g["late_orders"], g["orders"])
    ]
    g["ci_low"] = [lo for lo, _ in intervals]
    g["ci_high"] = [hi for _, hi in intervals]
    g["low_sample"] = g["orders"] < 200

    # uncertain: ci_low nằm dưới ngưỡng phân loại của tuyến → CI chứa ngưỡng
    red_thr = float(overall) * red
    amber_thr = float(overall) * amber
    g["uncertain"] = np.where(
        g["level"] == "red",
        g["ci_low"] < red_thr,
        np.where(g["level"] == "amber", g["ci_low"] < amber_thr, False),
    )

    flagged = g[g.level != "ok"]
    if top <= 0:
        return flagged.head(0)
    if not ensure_red:
        return flagged.sort_values("late_orders", ascending=False).head(top)

    reds = flagged[flagged.level == "red"].sort_values(
        "late_orders", ascending=False
    )
    ambers = flagged[flagged.level == "amber"].sort_values(
        "late_orders", ascending=False
    )
    if len(reds) >= top:
        return reds
    return pd.concat([reds, ambers.head(top - len(reds))])


def low_sample_targets(
    o, min_orders=200, red=2.0, amber=1.5, top=10, include_unflagged=False
):
    """S7: tách riêng nhóm tuyến **chưa đủ mẫu** ("cần thêm dữ liệu").

    Hàm này **không thay đổi** :func:`route_priority` (giữ nguyên hành vi theo
    H7); nó chỉ trả một bảng phụ để UI/báo cáo không trộn tuyến mẫu nhỏ vào
    danh sách ưu tiên chính.

    Chỉ lấy tuyến có ``orders < min_orders`` (mặc định 200, cùng ngưỡng
    ``low_sample`` của ``route_priority``). ``level`` là nhãn **tạm** theo cùng
    luật bội số ``red``/``amber`` so với tỷ lệ trễ chung, nhưng ``status`` luôn
    là ``"cần thêm dữ liệu"`` và có thêm ``needed_orders`` = số đơn còn thiếu
    để đạt ngưỡng. Mặc định chỉ giữ tuyến có tín hiệu (level khác ``ok``);
    đặt ``include_unflagged=True`` để lấy tất cả tuyến mẫu nhỏ.

    Sắp theo ``late_orders`` giảm dần (tác động), rồi ``orders`` giảm dần.
    Thông tin tổng hợp nằm trong ``.attrs``.
    """
    if min_orders < 1:
        raise ValueError("min_orders phải >= 1")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để low_sample_targets")
    if top < 0:
        raise ValueError("top phải >= 0")

    overall = float(o.is_late.mean())
    g = (
        o.groupby("route")
        .agg(
            orders=("order_id", "nunique"),
            late_orders=("is_late", "sum"),
            late_rate=("is_late", "mean"),
        )
        .reset_index()
    )
    low = g[g["orders"] < min_orders].copy()
    low["level"] = np.where(
        low["late_rate"] >= overall * red,
        "red",
        np.where(low["late_rate"] >= overall * amber, "amber", "ok"),
    )
    intervals = [
        wilson_interval(int(k), int(n))
        for k, n in zip(low["late_orders"], low["orders"])
    ]
    low["ci_low"] = [lo for lo, _ in intervals]
    low["ci_high"] = [hi for _, hi in intervals]
    low["status"] = "cần thêm dữ liệu"
    low["needed_orders"] = (min_orders - low["orders"]).astype(int)
    low["late_orders_share_of_low"] = np.where(
        low["late_orders"].sum() > 0,
        low["late_orders"] / low["late_orders"].sum(),
        np.nan,
    )

    n_low = int(len(low))
    n_candidates = int((low["level"] != "ok").sum())
    candidates = low if include_unflagged else low[low["level"] != "ok"]
    out = candidates.sort_values(
        ["late_orders", "orders"], ascending=False
    ).reset_index(drop=True)
    if top > 0:
        out = out.head(top).reset_index(drop=True)

    out.attrs["min_orders"] = int(min_orders)
    out.attrs["red"] = float(red)
    out.attrs["amber"] = float(amber)
    out.attrs["overall_late_rate"] = overall
    out.attrs["n_routes_total"] = int(len(g))
    out.attrs["n_low_sample"] = n_low
    out.attrs["n_low_sample_candidates"] = n_candidates
    out.attrs["n_low_sample_late_orders"] = int(low["late_orders"].sum())
    out.attrs["n_candidate_late_orders"] = int(
        low.loc[low["level"] != "ok", "late_orders"].sum()
    )
    out.attrs["n_returned"] = int(len(out))
    return out


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


def sensitivity(o, route, stage, max_days=5, base_cut=None):
    """Phân tích độ nhạy: tỷ lệ trễ dự báo khi cắt 0..max_days ngày ở ``stage``.

    ``base_cut`` (dict, tuỳ chọn) là các mức cắt cố định của các giai đoạn
    *khác* để giữ bối cảnh What-if hiện tại. Ví dụ nếu người dùng đang xem
    ``prep=2`` và quét ``transit``, truyền ``base_cut={"prep": 2}`` để mỗi
    điểm trên đường cong phản ánh đúng kịch bản đang chọn.

    Khi ``base_cut=None`` (mặc định) hàm hoạt động y như trước — chỉ cắt
    ``stage``, các giai đoạn còn lại để 0 — đảm bảo tương thích ngược.

    Điểm ``cut = c`` trên series sẽ bằng ``projected`` của
    ``scenario(o, route, {**base_cut, stage: c})``.
    """
    fixed = dict(base_cut) if base_cut else {}
    # Loại bỏ giai đoạn đang quét khỏi base_cut nếu vô tình truyền vào
    fixed.pop(stage, None)
    return [
        {"cut": x, "projected": scenario(o, route, {**fixed, stage: x})["projected"]}
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
