"""
Cấu hình chung cho pipeline ETL của dự án Brazillian.

Toàn bộ đường dẫn được tính từ vị trí file này nên script có thể chạy từ
bất kỳ thư mục nào mà vẫn tìm đúng data.

    Brazillian/
    ├── .env                  <- thông tin kết nối PostgreSQL
    ├── data/
    │   ├── raw/              <- dữ liệu gốc từ Olist
    │   └── processed/        <- dữ liệu sau khi làm sạch
    ├── sql/create_tables.sql <- DDL tạo bảng
    └── src/                  <- code ETL (file này)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

# --------------------------------------------------------------------------- #
#  Console
# --------------------------------------------------------------------------- #
# Windows mặc định dùng cp1252, không in được tiếng Việt có dấu (UnicodeEncodeError).
# Module này luôn được import đầu tiên nên ép UTF-8 cho cả stdout lẫn stderr.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # stdout bị thay thế (ví dụ khi import từ shell)
        pass


# --------------------------------------------------------------------------- #
#  Đường dẫn
# --------------------------------------------------------------------------- #
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
ENV_FILE = PROJECT_ROOT / ".env"


def ensure_dirs() -> None:
    """Tạo các thư mục đích nếu chưa tồn tại (an toàn khi chạy lại nhiều lần)."""
    for directory in (RAW_DIR, PROCESSED_DIR, SQL_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
#  File nguồn / file đích
# --------------------------------------------------------------------------- #
RAW_ORDERS = RAW_DIR / "olist_orders_dataset.csv"
RAW_ORDER_ITEMS = RAW_DIR / "olist_order_items_dataset.csv"
RAW_ORDER_REVIEWS = RAW_DIR / "olist_order_reviews_dataset.csv"
RAW_ORDER_PAYMENTS = RAW_DIR / "olist_order_payments_dataset.csv"
RAW_CUSTOMERS = RAW_DIR / "olist_customers_dataset.csv"
RAW_SELLERS = RAW_DIR / "olist_sellers_dataset.csv"
RAW_PRODUCTS = RAW_DIR / "olist_products_dataset.csv"
RAW_GEOLOCATION = RAW_DIR / "olist_geolocation_dataset.csv"
RAW_CATEGORY_TRANSLATION = RAW_DIR / "product_category_name_translation.csv"

# (tên bảng đích -> file CSV sau khi làm sạch)
WAREHOUSE_TABLES: dict[str, Path] = {
    "Dim_Time": PROCESSED_DIR / "cleaned_dim_time.csv",
    "Dim_Location": PROCESSED_DIR / "cleaned_dim_location.csv",
    "Dim_Product": PROCESSED_DIR / "cleaned_dim_product.csv",
    "Fact_Delivery_SLA": PROCESSED_DIR / "cleaned_fact_orders.csv",
}


# --------------------------------------------------------------------------- #
#  Cấu hình kết nối PostgreSQL
# --------------------------------------------------------------------------- #
def load_env_file(path: Path = ENV_FILE) -> None:
    """Đọc file .env đơn giản và nạp vào os.environ (biến đã có sẵn được giữ nguyên)."""
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_database_url(url: str) -> dict:
    """Chuyển DATABASE_URL dạng chuẩn thành kwargs cho psycopg2.connect."""
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"Database URL không hợp lệ (scheme={parsed.scheme!r}).")

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": unquote((parsed.path or "").lstrip("/")) or "postgres",
        "user": unquote(parsed.username) if parsed.username else "postgres",
        "password": unquote(parsed.password) if parsed.password else None,
    }


def get_db_config() -> dict:
    """
    Lấy cấu hình kết nối database.

    Thứ tự ưu tiên:
      1. Biến môi trường DATABASE_URL (do .env nạp vào, hoặc export tay)
      2. Các biến rời PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD
    """
    load_env_file()

    url = os.environ.get("DATABASE_URL")
    if url:
        return parse_database_url(url)

    if all(key in os.environ for key in ("PGHOST", "PGDATABASE", "PGUSER")):
        return {
            "host": os.environ["PGHOST"],
            "port": int(os.environ.get("PGPORT", 5432)),
            "dbname": os.environ["PGDATABASE"],
            "user": os.environ["PGUSER"],
            "password": os.environ.get("PGPASSWORD"),
        }

    raise RuntimeError(
        "Chưa cấu hình kết nối database.\n"
        f"Hãy tạo file {ENV_FILE.name} ở thư mục gốc project với nội dung:\n"
        '    DATABASE_URL="postgresql://<user>:<password>@localhost:5432/Brazillian?schema=public"\n'
        "hoặc đặt biến môi trường DATABASE_URL trước khi chạy."
    )


if __name__ == "__main__":
    ensure_dirs()
    print(f"PROJECT_ROOT : {PROJECT_ROOT}")
    print(f"RAW_DIR      : {RAW_DIR}")
    print(f"PROCESSED_DIR: {PROCESSED_DIR}")

    for table, csv_path in WAREHOUSE_TABLES.items():
        status = "OK" if csv_path.is_file() else "THIEU"
        print(f"  [{status:>5}] {table:<20} -> {csv_path.relative_to(PROJECT_ROOT)}")

    try:
        cfg = get_db_config()
        print(
            f"DB           : {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
        )
    except RuntimeError as exc:
        print(f"DB           : CHUA CAU HINH - {exc}")
