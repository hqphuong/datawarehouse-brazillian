"""Load - Nạp dữ liệu từ thư mục data/processed vào PostgreSQL Data Warehouse."""

import csv

import psycopg2

try:  # chạy như package:  python -m src.load_data
    from .config import WAREHOUSE_TABLES, ensure_dirs, get_db_config
except ImportError:  # chạy trực tiếp: python src/load_data.py
    from config import WAREHOUSE_TABLES, ensure_dirs, get_db_config


def load_data_warehouse():
    ensure_dirs()
    db_config = get_db_config()
    print(f"Đang kết nối đến PostgreSQL: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}...")

    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # --- BƯỚC MỚI: DỌN DẸP SẠCH SẼ DATABASE TRƯỚC KHI NẠP ---
        print("Đang dọn dẹp dữ liệu cũ để tránh lỗi trùng lặp...")
        cur.execute("TRUNCATE TABLE Fact_Delivery_SLA, Dim_Product, Dim_Location, Dim_Time CASCADE;")
        conn.commit()
        print("Đã dọn dẹp xong!")
        # --------------------------------------------------------

        for table_name, file_path in WAREHOUSE_TABLES.items():
            if not file_path.is_file():
                raise FileNotFoundError(f"Thiếu file dữ liệu: {file_path}\nHãy chạy các script ETL trước.")

            print(f"Đang nạp dữ liệu vào bảng {table_name} (từ {file_path.name})...")

            # COPY ... CSV HEADER chỉ bỏ qua dòng header chứ không map theo tên cột,
            # nên phải chỉ định rõ danh sách cột để tránh lệch thứ tự giữa CSV và bảng.
            with open(file_path, "r", encoding="utf-8", newline="") as f:
                header = next(csv.reader(f))
            columns = ", ".join(f'"{column}"' for column in header)

            with open(file_path, "r", encoding="utf-8") as f:
                copy_sql = (
                    f"COPY {table_name} ({columns}) "
                    "FROM STDIN WITH CSV HEADER DELIMITER ','"
                )
                cur.copy_expert(copy_sql, f)

            conn.commit()
            print(f"-> Nạp thành công {table_name}!")

        cur.close()
        conn.close()
        print("\nHOÀN TẤT! Toàn bộ dữ liệu đã nằm gọn trong Data Warehouse.")

    except Exception as e:
        print(f"\n❌ LỖI: {e}")
        if conn is not None:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    load_data_warehouse()
