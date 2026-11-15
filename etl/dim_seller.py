"""ETL - Dimension Seller: sinh bảng chiều người bán."""

import pandas as pd

try:  # chạy như package:  python -m src.dim_seller
    from .config import PROCESSED_DIR, RAW_SELLERS, ensure_dirs
    from .transform_rules import normalize_location_id
except ImportError:  # chạy trực tiếp: python src/dim_seller.py
    from config import PROCESSED_DIR, RAW_SELLERS, ensure_dirs
    from transform_rules import normalize_location_id

ensure_dirs()
OUTPUT_FILE = PROCESSED_DIR / "cleaned_dim_seller.csv"

print("Đang đọc dữ liệu gốc...")
df_sellers = pd.read_csv(RAW_SELLERS, dtype={"seller_zip_code_prefix": str})

print("Đang xử lý Dim_Seller...")
dim_seller = df_sellers[
    ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"]
].copy()
dim_seller = dim_seller.rename(
    columns={
        "seller_zip_code_prefix": "location_id",
        "seller_city": "city",
        "seller_state": "state",
    }
)
dim_seller["location_id"] = normalize_location_id(
    dim_seller["location_id"], "location_id"
)
if dim_seller["seller_id"].duplicated().any():
    raise ValueError("seller_id bị trùng trong Dim_Seller")

dim_seller = dim_seller[["seller_id", "location_id", "city", "state"]]
dim_seller.to_csv(OUTPUT_FILE, index=False)

print(f"Xuất ra: {OUTPUT_FILE}")
print(f"Tổng số Người bán (Dim_Seller): {len(dim_seller)}")
