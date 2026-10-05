"""ETL - Dimension Time: sinh bảng chiều thời gian từ dữ liệu đơn hàng."""

import pandas as pd

try:  # chạy như package:  python -m src.dim_time
    from .config import PROCESSED_DIR, RAW_ORDERS, ensure_dirs
except ImportError:  # chạy trực tiếp: python src/dim_time.py
    from config import PROCESSED_DIR, RAW_ORDERS, ensure_dirs

ensure_dirs()
OUTPUT_FILE = PROCESSED_DIR / "cleaned_dim_time.csv"

print("Đang đọc dữ liệu cho Dim_Time...")
df_orders = pd.read_csv(RAW_ORDERS)

# Lọc đơn hàng thành công và loại bỏ dữ liệu khuyết
df_cleaned = df_orders[df_orders["order_status"] == "delivered"].copy()
df_cleaned = df_cleaned.dropna(subset=["order_purchase_timestamp"])

# Chuyển đổi sang datetime
df_cleaned["order_purchase_timestamp"] = pd.to_datetime(df_cleaned["order_purchase_timestamp"])

# Khởi tạo bảng Dim_Time
dim_time = pd.DataFrame()
dim_time["time_id"] = df_cleaned["order_purchase_timestamp"].dt.strftime("%Y%m%d")
dim_time["full_date"] = df_cleaned["order_purchase_timestamp"].dt.date
dim_time["month"] = df_cleaned["order_purchase_timestamp"].dt.month
dim_time["year"] = df_cleaned["order_purchase_timestamp"].dt.year
dim_time["quarter"] = df_cleaned["order_purchase_timestamp"].dt.quarter
dim_time["day_of_week"] = df_cleaned["order_purchase_timestamp"].dt.day_name()

# Loại bỏ các ngày trùng lặp (giữ tính duy nhất cho khóa chính time_id)
dim_time = dim_time.drop_duplicates(subset=["time_id"])

# Xuất file
dim_time.to_csv(OUTPUT_FILE, index=False)

print(f"Xuất ra: {OUTPUT_FILE}")
print(f"Xử lý hoàn tất Dim_Time! Tổng số dòng: {len(dim_time)}")
