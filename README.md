# Brazillian — Data Warehouse (Olist E-commerce)

Project bài tập Data Warehouse (Star Schema) xây dựng từ bộ dữ liệu Olist
(Brazilian e-commerce), dùng PostgreSQL làm DW và Prisma để định nghĩa schema.

---

## Cấu trúc thư mục

```
Brazillian/
├── .env                        # DATABASE_URL — thông tin kết nối PostgreSQL
├── .gitignore
├── requirements.txt            # thư viện Python
├── Assignment.code-workspace   # mở folder này bằng VS Code
│
├── data/
│   ├── raw/                    # Dữ liệu gốc Olist (9 file CSV) — KHÔNG sửa
│   └── processed/              # CSV sau khi làm sạch (sinh ra từ ETL)
│
├── src/                        # Code pipeline ETL
│   ├── config.py               # Đường dẫn + cấu hình DB (đọc .env)
│   ├── main.py                 # Điểm chạy pipeline
│   ├── dim_time.py             # Dimension Time
│   ├── dim_location.py         # Dimension Location
│   ├── dim_product.py          # Dimension Product
│   ├── fact_delivery_sla.py    # Fact Delivery SLA
│   └── load_data.py            # Nạp CSV vào PostgreSQL
│
├── sql/
│   └── create_tables.sql       # DDL tạo 4 bảng DW
│
├── prisma/
│   └── schema.prisma           # Model hóa DW sang Prisma Client
├── prisma.config.ts
├── package.json
│
├── env/                        # Python virtualenv (không commit)
└── node_modules/               # (không commit)
```

---

## Cài đặt

### 1. Môi trường Python

```powershell
cd Brazillian
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Tạo database

```powershell
psql -U postgres -c "CREATE DATABASE ""Brazillian"";"
psql -U postgres -d Brazillian -f sql\create_tables.sql
```

### 3. Cấu hình kết nối

Sửa file `.env` cho đúng máy của bạn:

```env
DATABASE_URL="postgresql://brazillian_admin:123456789@localhost:5432/Brazillian?schema=public"
```

### 4. Node / Prisma (tuỳ chọn)

```powershell
npm install
npx prisma generate
```

---

## Chạy pipeline

```powershell
# Chỉ Transform — sinh CSV trong data/processed/
python src\main.py

# Transform + Load — nạp thẳng vào PostgreSQL
python src\main.py --load
```

Chạy từng bước riêng lẻ:

```powershell
python src\dim_time.py
python src\dim_location.py
python src\dim_product.py
python src\fact_delivery_sla.py
python src\load_data.py
```

Kiểm tra nhanh đường dẫn & cấu hình DB:

```powershell
python src\config.py
```

> Toàn bộ đường dẫn được tính bằng `pathlib` trong `src/config.py`, nên script chạy
> đúng dù bạn mở terminal ở thư mục nào.

---

## Mô hình dữ liệu (Star Schema)

| Bảng | Loại | Ý nghĩa |
|---|---|---|
| `Dim_Time` | Dimension | Ngày / tháng / quý / năm mua hàng |
| `Dim_Location` | Dimension | Địa điểm khách hàng & người bán (kèm tọa độ) |
| `Dim_Product` | Dimension | Sản phẩm, danh mục (EN), khối lượng, thể tích |
| `Fact_Delivery_SLA` | Fact | Độ đo chuỗi cung ứng & chất lượng giao hàng |

Các cột đo chính của `Fact_Delivery_SLA`: `approval_time_days`,
`seller_prep_time_days`, `carrier_transit_time_days`, `freight_value`,
`review_score`, cùng 2 cờ phân loại `is_late` và `has_logistics_complaint`.
