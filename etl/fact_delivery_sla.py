"""ETL - Fact Delivery SLA: sinh bảng fact đo lường chuỗi cung ứng & chất lượng giao hàng."""

import pandas as pd

try:  # chạy như package:  python -m src.fact_delivery_sla
    from .config import (
        PROCESSED_DIR,
        RAW_CUSTOMERS,
        RAW_ORDER_ITEMS,
        RAW_ORDER_PAYMENTS,
        RAW_ORDER_REVIEWS,
        RAW_ORDERS,
        RAW_SELLERS,
        ensure_dirs,
    )
    from .transform_rules import select_latest_reviews, select_payment_type
except ImportError:  # chạy trực tiếp: python src/fact_delivery_sla.py
    from config import (
        PROCESSED_DIR,
        RAW_CUSTOMERS,
        RAW_ORDER_ITEMS,
        RAW_ORDER_PAYMENTS,
        RAW_ORDER_REVIEWS,
        RAW_ORDERS,
        RAW_SELLERS,
        ensure_dirs,
    )
    from transform_rules import select_latest_reviews, select_payment_type

ensure_dirs()
OUTPUT_FILE = PROCESSED_DIR / "cleaned_fact_orders.csv"

print("Đang đọc dữ liệu cho Fact_Delivery_SLA...")
df_orders = pd.read_csv(RAW_ORDERS)
df_items = pd.read_csv(RAW_ORDER_ITEMS)
df_reviews = pd.read_csv(RAW_ORDER_REVIEWS)
df_customers = pd.read_csv(
    RAW_CUSTOMERS, dtype={"customer_zip_code_prefix": str}
)
df_sellers = pd.read_csv(RAW_SELLERS, dtype={"seller_zip_code_prefix": str})
df_payments = pd.read_csv(RAW_ORDER_PAYMENTS)

print("Đang biến đổi và tính toán (Transform)...")
# 1. XỬ LÝ THỜI GIAN
df_cleaned = df_orders[df_orders["order_status"] == "delivered"].copy()
time_cols = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
for col in time_cols:
    df_cleaned[col] = pd.to_datetime(df_cleaned[col])

df_cleaned = df_cleaned.dropna(subset=time_cols)

df_cleaned["approval_time_days"] = (df_cleaned["order_approved_at"] - df_cleaned["order_purchase_timestamp"]).dt.total_seconds() / 86400.0
df_cleaned["seller_prep_time_days"] = (df_cleaned["order_delivered_carrier_date"] - df_cleaned["order_approved_at"]).dt.total_seconds() / 86400.0
df_cleaned["carrier_transit_time_days"] = (df_cleaned["order_delivered_customer_date"] - df_cleaned["order_delivered_carrier_date"]).dt.total_seconds() / 86400.0
# delay_days > 0: giao muộn so với cam kết; < 0: giao sớm; = 0: đúng hạn
df_cleaned["delay_days"] = (df_cleaned["order_delivered_customer_date"] - df_cleaned["order_estimated_delivery_date"]).dt.total_seconds() / 86400.0

# Đảm bảo time_id là số nguyên INT
df_cleaned["time_id"] = df_cleaned["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int)

# 2. XỬ LÝ REVIEWS (Text Mining - DSS)
# Quy tắc: mỗi đơn giữ đúng 1 review mới nhất theo review_creation_date;
# hòa thì theo review_answer_timestamp, rồi review_id (lớn hơn = mới hơn).
n_reviews_per_order = df_reviews.groupby("order_id").size()
df_reviews = select_latest_reviews(df_reviews)
logistics_keywords = [
    "atraso",
    "demora",
    "não recebi",
    "nao recebi",
    "nunca chegou",
    "transportadora",
    "correios",
    "demorou",
    "prazo",
    "aguardando",
    "aguardo",
    "extraviado",
    "roubado",
    "não entregue",
    "nao entregue",
]


def check_logistics_issue(text):
    if pd.isna(text):
        return False
    return any(keyword in str(text).lower() for keyword in logistics_keywords)


df_reviews["has_logistics_keyword"] = df_reviews["review_comment_message"].apply(check_logistics_issue)
df_reviews["has_logistics_complaint"] = (df_reviews["review_score"] <= 2) & (df_reviews["has_logistics_keyword"])

# 3. XỬ LÝ PAYMENTS (Chiều suy biến)
# Quy tắc: payment_type của đơn = loại có TỔNG payment_value lớn nhất;
# hòa thì chọn loại có payment_sequential nhỏ nhất (rồi theo tên loại).
n_payment_types_per_order = df_payments.groupby("order_id")["payment_type"].nunique()
main_payments = select_payment_type(df_payments)

print("Đang kết nối các bảng (Merge)...")
# Nối bảng chi tiết hàng hóa
fact_df = df_cleaned.merge(df_items, on="order_id", how="inner")

# Nối địa điểm khách hàng
fact_df = fact_df.merge(df_customers[["customer_id", "customer_zip_code_prefix"]], on="customer_id", how="left")
fact_df = fact_df.rename(columns={"customer_zip_code_prefix": "customer_location_id"})

# Nối địa điểm người bán
fact_df = fact_df.merge(df_sellers[["seller_id", "seller_zip_code_prefix"]], on="seller_id", how="left")
fact_df = fact_df.rename(columns={"seller_zip_code_prefix": "seller_location_id"})

# Chuẩn hóa khóa địa điểm về đúng 5 ký tự, khớp Dim_Location.
for col in ("customer_location_id", "seller_location_id"):
    fact_df[col] = fact_df[col].astype(str).str.zfill(5)
    bad = fact_df[col].str.len() != 5
    if bad.any():
        raise ValueError(
            f"{col} không đủ 5 ký tự: {int(bad.sum())} dòng "
            f"{fact_df.loc[bad, col].head(5).tolist()}"
        )

# Nối Đánh giá & Thanh toán
fact_df = fact_df.merge(df_reviews[["order_id", "review_score", "has_logistics_complaint"]], on="order_id", how="left")
fact_df = fact_df.merge(main_payments[["order_id", "payment_type"]], on="order_id", how="left")

# Lấp đầy giá trị Boolean khuyết để tránh báo lỗi NULL khi Copy
# (delay_days đã được đảm bảo đủ dữ liệu bởi dropna ở trên; giữ NULL nếu thiếu
# thay vì gán 0 để không làm sai lệch thống kê giao hàng)
fact_df["has_logistics_complaint"] = fact_df["has_logistics_complaint"].fillna(False)
fact_df["review_score"] = fact_df["review_score"].astype("Int64")

fact_cols = [
    "order_id",
    "order_item_id",
    "product_id",
    "customer_location_id",
    "seller_location_id",
    "time_id",
    "payment_type",
    "approval_time_days",
    "seller_prep_time_days",
    "carrier_transit_time_days",
    "freight_value",
    "review_score",
    "delay_days",
    "has_logistics_complaint",
]

fact_orders = fact_df[fact_cols].copy()
fact_orders.to_csv(OUTPUT_FILE, index=False)

print(f"Xuất ra: {OUTPUT_FILE}")
print(
    "Đơn có >1 payment_type: "
    f"{int((n_payment_types_per_order > 1).sum())}/{len(n_payment_types_per_order)} "
    f"({(n_payment_types_per_order > 1).mean():.4%})"
)
print(
    "Đơn có >1 review: "
    f"{int((n_reviews_per_order > 1).sum())}/{len(n_reviews_per_order)} "
    f"({(n_reviews_per_order > 1).mean():.4%})"
)
print(f"Xử lý hoàn tất Fact_Delivery_SLA! Tổng dòng: {len(fact_orders)}")
