"""ETL - Dimension Product: sinh bảng chiều sản phẩm kèm danh mục tiếng Anh."""

import pandas as pd

try:  # chạy như package:  python -m src.dim_product
    from .config import PROCESSED_DIR, RAW_CATEGORY_TRANSLATION, RAW_PRODUCTS, ensure_dirs
except ImportError:  # chạy trực tiếp: python src/dim_product.py
    from config import PROCESSED_DIR, RAW_CATEGORY_TRANSLATION, RAW_PRODUCTS, ensure_dirs

ensure_dirs()
OUTPUT_FILE = PROCESSED_DIR / "cleaned_dim_product.csv"

print("Đang đọc dữ liệu gốc...")
df_products = pd.read_csv(RAW_PRODUCTS)
df_category_translation = pd.read_csv(RAW_CATEGORY_TRANSLATION)

# ==========================================
# XỬ LÝ BẢNG DIM_PRODUCT
# ==========================================
print("Đang xử lý Dim_Product...")
# Thiết lập validate='m:1' (nhiều-một) vì một danh mục trong bảng translation áp dụng cho nhiều sản phẩm
df_products = df_products.merge(
    df_category_translation,
    on="product_category_name",
    how="left",
    validate="m:1",
)

df_products["volume_cm3"] = (
    df_products["product_length_cm"] * df_products["product_height_cm"] * df_products["product_width_cm"]
)

dim_product = df_products[["product_id", "product_category_name_english", "product_weight_g", "volume_cm3"]].copy()

# Gán lại biến (reassignment) thay vì dùng inplace=True
dim_product = dim_product.rename(
    columns={
        "product_category_name_english": "category_name_english",
        "product_weight_g": "weight_g",
    }
)

dim_product["category_name_english"] = dim_product["category_name_english"].fillna("Unknown")
dim_product["weight_g"] = dim_product["weight_g"].fillna(0)
dim_product["volume_cm3"] = dim_product["volume_cm3"].fillna(0)

dim_product.to_csv(OUTPUT_FILE, index=False)

print(f"Xuất ra: {OUTPUT_FILE}")
print(f"Tổng số Sản phẩm (Dim_Product): {len(dim_product)}")
print("Xử lý hoàn tất!")
