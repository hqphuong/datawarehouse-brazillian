"""ETL - Dimension Location: sinh bảng chiều địa điểm (khách hàng + người bán)."""

import pandas as pd

try:  # chạy như package:  python -m src.dim_location
    from .config import PROCESSED_DIR, RAW_CUSTOMERS, RAW_GEOLOCATION, RAW_SELLERS, ensure_dirs
    from .transform_rules import normalize_location_id
except ImportError:  # chạy trực tiếp: python src/dim_location.py
    from config import PROCESSED_DIR, RAW_CUSTOMERS, RAW_GEOLOCATION, RAW_SELLERS, ensure_dirs
    from transform_rules import normalize_location_id

ensure_dirs()
OUTPUT_FILE = PROCESSED_DIR / "cleaned_dim_location.csv"

print("Đang đọc dữ liệu gốc...")
df_customers = pd.read_csv(
    RAW_CUSTOMERS, dtype={"customer_zip_code_prefix": str}
)
df_sellers = pd.read_csv(RAW_SELLERS, dtype={"seller_zip_code_prefix": str})
df_geo = pd.read_csv(RAW_GEOLOCATION, dtype={"geolocation_zip_code_prefix": str})

print("Đang xử lý Tọa độ địa lý (Geolocation)...")
# Gom nhóm để lấy tọa độ trung tâm (mean) của từng mã bưu điện
geo_grouped = df_geo.groupby("geolocation_zip_code_prefix").agg(
    {
        "geolocation_lat": "mean",
        "geolocation_lng": "mean",
    }
).reset_index()

# Đảm bảo mã zip code là chuỗi (String) và bù thêm số 0 ở đầu (pad) cho đủ 5 ký tự
# (Vì pandas khi đọc file geo đã tự động biến mã 01037 thành số 1037 gây mất dữ liệu)
geo_grouped["geolocation_zip_code_prefix"] = normalize_location_id(
    geo_grouped["geolocation_zip_code_prefix"], "geolocation_zip_code_prefix"
)

print("Đang xử lý Dim_Location...")
# Lấy danh sách địa điểm từ Khách hàng
loc_customer = df_customers[["customer_zip_code_prefix", "customer_city", "customer_state"]].drop_duplicates()
loc_customer.columns = ["location_id", "city", "state"]

# Lấy danh sách địa điểm từ Người bán
loc_seller = df_sellers[["seller_zip_code_prefix", "seller_city", "seller_state"]].drop_duplicates()
loc_seller.columns = ["location_id", "city", "state"]

# Gộp danh sách
dim_location = pd.concat([loc_customer, loc_seller], ignore_index=True)
# Khóa địa điểm phải luôn đủ 5 ký tự (mã bưu điện Brazil). Hàm chặn NaN trước
# zfill và dừng pipeline thay vì âm thầm nạp dữ liệu sai.
dim_location["location_id"] = normalize_location_id(
    dim_location["location_id"], "location_id"
)
dim_location = dim_location.drop_duplicates(subset=["location_id"], keep="first")
dim_location["zip_code_prefix"] = dim_location["location_id"]

# Kết nối (Merge) Bảng địa điểm với Bảng tọa độ
dim_location = dim_location.merge(
    geo_grouped,
    left_on="zip_code_prefix",
    right_on="geolocation_zip_code_prefix",
    how="left",
)

# Đổi tên cột cho gọn gàng theo chuẩn Star Schema
dim_location = dim_location.rename(
    columns={"geolocation_lat": "latitude", "geolocation_lng": "longitude"}
)

# Sắp xếp lại thứ tự cột và xuất file
dim_location = dim_location[["location_id", "zip_code_prefix", "city", "state", "latitude", "longitude"]]
dim_location.to_csv(OUTPUT_FILE, index=False)

print(f"Xuất ra: {OUTPUT_FILE}")
print("Xử lý hoàn tất!")
print(f"Tổng số Địa điểm (Dim_Location): {len(dim_location)}")
