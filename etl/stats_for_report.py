# src/stats_for_report.py  — chạy từ thư mục gốc: python -m src.stats_for_report
import pandas as pd
from .config import (PROCESSED_DIR, RAW_CATEGORY_TRANSLATION, RAW_CUSTOMERS, RAW_GEOLOCATION,
                     RAW_ORDER_ITEMS, RAW_ORDER_PAYMENTS, RAW_ORDER_REVIEWS, RAW_ORDERS,
                     RAW_PRODUCTS, RAW_SELLERS)

raw = {"orders": RAW_ORDERS, "order_items": RAW_ORDER_ITEMS, "order_payments": RAW_ORDER_PAYMENTS,
       "order_reviews": RAW_ORDER_REVIEWS, "customers": RAW_CUSTOMERS, "sellers": RAW_SELLERS,
       "products": RAW_PRODUCTS, "category_translation": RAW_CATEGORY_TRANSLATION, "geolocation": RAW_GEOLOCATION}
print("== N1-N9: số dòng bảng nguồn ==")
for k, p in raw.items():
    print(k, len(pd.read_csv(p)))

o = pd.read_csv(RAW_ORDERS, parse_dates=["order_purchase_timestamp"])
print("== N10: khoảng thời gian ==", o.order_purchase_timestamp.min(), "->", o.order_purchase_timestamp.max())
print("== trạng thái đơn ==\n", o.order_status.value_counts().to_string())

print("== L1-L4: số dòng kho dữ liệu ==")
fact = pd.read_csv(PROCESSED_DIR / "cleaned_fact_orders.csv")
for name in ["dim_product", "dim_time", "dim_location"]:
    print(name, len(pd.read_csv(PROCESSED_DIR / f"cleaned_{name}.csv")))
print("fact_delivery_sla", len(fact))

print("== Q1 (tham khảo) ==")
print("order_items không vào fact:", len(pd.read_csv(RAW_ORDER_ITEMS)) - len(fact))
print("== kiểm tra Fact ==")
print("số đơn khác nhau:", fact.order_id.nunique(), "| tỷ lệ trễ theo đơn:", round(fact.drop_duplicates("order_id").is_late.mean(), 4))
print("có delay_days:", "delay_days" in fact.columns)
