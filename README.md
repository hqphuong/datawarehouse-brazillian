# Brazillian — Olist Logistics DSS

Đồ án Data Warehouse & Hệ hỗ trợ quyết định (DSS) cho bài toán logistics, xây
dựng từ bộ dữ liệu **Olist Brazilian E-commerce**.

Hệ thống gồm 4 phần:

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Data Warehouse | PostgreSQL (Star Schema) | Lưu dữ liệu phân tích |
| ETL | Python + pandas + psycopg2 | Làm sạch, tính toán, nạp DW |
| Backend | Django 6 | Ánh xạ DW, Admin, nền tảng cho API |
| Frontend | React 19 + Vite | Giao diện DSS |

---

## Trạng thái hiện tại

- **ETL**: hoàn chỉnh, sinh 5 file CSV trong `data/processed/` và nạp được vào
  PostgreSQL.
- **DW**: 5 bảng `Dim_Time`, `Dim_Location`, `Dim_Product`, `Dim_Seller`,
  `Fact_Delivery_SLA` đã được tạo và nạp dữ liệu.
- **Backend**: Django + app `analytics` (model ánh xạ DW, `managed = False`) và
  app `dss`. API DSS tại `/api/dss/` gồm `routes`, `scenario`, `promise`,
  `actions`; tài liệu: `reports/api_dss.md`.
- **Frontend**: `web/Olist_Logistics_DSS_v3.html` — tab **DSS** gọi API Django
  thật; 3 tab còn lại vẫn là mock (xem cảnh báo bên dưới).
- **Mockup UI**: `web/Olist_Logistics_DSS_v3.html` — mở trực tiếp bằng trình duyệt.
- **Prisma**: schema mô tả DW và Prisma Client (dùng cho tooling/Node).
- **Kiểm thử**: 38 pytest, 16 Django test (`manage.py test dss`).

> **⚠️ Nhãn cảnh báo giao diện:**
> - Tab **Dashboard**, **OLAP**, **ETL Monitor** hiển thị **dữ liệu mẫu** (mock
>   data, do thành viên khác phát triển bằng Flask, chưa nối Django thật). Số
>   liệu trên các tab này **không phản ánh dữ liệu Olist thực tế**.

---

## Cấu trúc thư mục

```
Brazillian/
├── .env                        # DATABASE_URL cho ETL & Prisma (không commit)
├── .gitignore
├── requirements.txt            # Thư viện Python cho ETL
├── package.json                # Prisma & tiện ích Node ở thư mục gốc
├── prisma.config.ts
├── Assignment.code-workspace   # Mở project bằng VS Code
├── web/Olist_Logistics_DSS_v3.html  # Giao diện DSS (tab DSS gọi API thật)
│
├── data/
│   ├── raw/                    # 9 file CSV gốc Olist — KHÔNG sửa
│   └── processed/              # CSV sau ETL (sinh tự động, không commit)
│
├── etl/                        # Pipeline ETL
│   ├── config.py               # Đường dẫn + cấu hình kết nối DB
│   ├── main.py                 # Điểm chạy pipeline (Transform / --load)
│   ├── dim_time.py             # Sinh Dim_Time
│   ├── dim_location.py         # Sinh Dim_Location
│   ├── dim_product.py          # Sinh Dim_Product
│   ├── dim_seller.py           # Sinh Dim_Seller
│   ├── fact_delivery_sla.py    # Sinh Fact_Delivery_SLA
│   └── load_data.py            # Nạp CSV vào PostgreSQL (1 transaction)
│
├── sql/
│   └── create_tables.sql       # DDL tạo 5 bảng DW
│
├── prisma/
│   └── schema.prisma           # Mô hình DW cho Prisma Client
│
├── backend/                    # Django 6
│   ├── manage.py
│   ├── .env                    # Cấu hình Django + PostgreSQL (không commit)
│   ├── .env.new                # File mẫu cấu hình
│   ├── core/                   # settings, urls, wsgi, asgi
│   ├── config/                 # EnvConfig, LoggingConfig, utils
│   ├── analytics/              # App ánh xạ DW (models, admin, views)
│   ├── logs/                   # Log theo ngày
│   └── env/                    # Virtualenv Python của backend (không commit)
│
└── frontend/                   # Vite + React
    ├── src/
    ├── public/
    └── package.json
```

---

## Yêu cầu môi trường

- Python **3.13**
- PostgreSQL (đã tạo database và user)
- Node.js **18+** (Prisma và frontend)

---

## Cài đặt

### 1. Tạo database

Ví dụ với user `brazillian_admin` (đổi thông tin cho khớp `.env` của bạn):

```powershell
psql -U postgres -c "CREATE USER brazillian_admin WITH PASSWORD '123456789';"
psql -U postgres -c "CREATE DATABASE ""Brazillian"" OWNER brazillian_admin;"

# Tạo 4 bảng DW
psql -U brazillian_admin -d Brazillian -f sql\create_tables.sql
```

> Nếu database/user đã tồn tại, bỏ qua bước `CREATE` tương ứng. `create_tables.sql`
> không dùng `IF NOT EXISTS`, nên nếu 4 bảng đã có thì cần drop trước khi tạo lại.

### 2. Môi trường Python cho ETL

```powershell
cd Brazillian
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Có thể dùng chung virtualenv `backend\env` nếu đã cài đủ `pandas`,
> `numpy`, `psycopg2-binary`.

### 3. Cấu hình kết nối

**ETL & Prisma** đọc file `.env` ở thư mục gốc:

```env
DATABASE_URL="postgresql://brazillian_admin:123456789@localhost:5432/Brazillian?schema=public"
```

**Django** đọc file `backend/.env` (xem mẫu `backend/.env.new`):

```env
SECRET_KEY=...
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

POSTGRES_DB=Brazillian
POSTGRES_USER=brazillian_admin
POSTGRES_PASSWORD=123456789
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### 4. Backend Django

```powershell
cd backend
.\env\Scripts\Activate.ps1
pip install django psycopg2-binary python-dotenv

python manage.py check
python manage.py runserver
```

Backend chạy tại `http://127.0.0.1:8000/`. Các model DW dùng
`managed = False` nên **không cần migrate cho 4 bảng DW**. Nếu muốn dùng
Django Admin:

```powershell
python manage.py migrate          # chỉ tạo các bảng hệ thống của Django
python manage.py createsuperuser
```

Sau đó truy cập `http://127.0.0.1:8000/admin/`.

### 5. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend chạy tại `http://localhost:5173/` (Vite).

### 6. Prisma (tuỳ chọn)

```powershell
cd Brazillian
npm install
npx prisma generate
npx prisma validate
```

---

## Chạy pipeline ETL

```powershell
# Chỉ Transform — sinh CSV trong data/processed/
python etl\main.py

# Transform + Load — nạp thẳng vào PostgreSQL
python etl\main.py --load
```

Chạy từng bước riêng lẻ:

```powershell
python etl\dim_time.py
python etl\dim_location.py
python etl\dim_product.py
python etl\fact_delivery_sla.py
python etl\load_data.py
```

Kiểm tra nhanh đường dẫn và cấu hình DB:

```powershell
python etl\config.py
```

**Lưu ý:**

- Toàn bộ đường dẫn được tính bằng `pathlib` trong `etl/config.py`, nên chạy
  được từ bất kỳ thư mục nào.
- `load_data.py` sẽ `TRUNCATE` cả 4 bảng DW rồi nạp lại toàn bộ, nên chạy lại
  nhiều lần vẫn không bị trùng dữ liệu.
- `data/processed/` nằm trong `.gitignore` vì có thể sinh lại từ `data/raw/`.
- Lệnh `COPY` chỉ định rõ danh sách cột theo header CSV để tránh lệch thứ tự
  giữa file và bảng.

---

## Quy trình xử lý ETL

1. **Lọc đơn hàng**: chỉ giữ `order_status = 'delivered'` và các đơn có đủ 5
   mốc thời gian (mua, duyệt, giao cho vận chuyển, giao khách, dự kiến giao).
2. **Tính độ đo thời gian**:
   - `approval_time_days`: mua → duyệt đơn
   - `seller_prep_time_days`: duyệt đơn → giao cho vận chuyển
   - `carrier_transit_time_days`: giao cho vận chuyển → giao khách
   - `delay_days`: giao thực tế − dự kiến giao
3. **Review (text mining)**: lấy review mới nhất của mỗi đơn, dò từ khoá
   logistics tiếng Bồ Đào Nha; đánh dấu `has_logistics_complaint` khi
   `review_score <= 2` **và** có từ khoá.
4. **Payment**: chọn bản ghi thanh toán có `payment_value` lớn nhất của mỗi đơn
   làm `payment_type`.
5. **Ghép bảng**: order items (inner) → địa điểm khách/người bán → review →
   payment.
6. **Xuất CSV** và (tuỳ chọn) nạp vào PostgreSQL.

---

## Mô hình dữ liệu (Star Schema)

| Bảng | Loại | Ý nghĩa |
|---|---|---|
| `Dim_Time` | Dimension | Ngày / tháng / quý / năm mua hàng |
| `Dim_Location` | Dimension | Địa điểm khách hàng & người bán (kèm tọa độ) |
| `Dim_Product` | Dimension | Sản phẩm, danh mục tiếng Anh, khối lượng, thể tích |
| `Fact_Delivery_SLA` | Fact | Độ đo chuỗi cung ứng & chất lượng giao hàng |

### `Dim_Time`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `time_id` | INT (PK) | `YYYYMMDD` của ngày mua |
| `full_date` | DATE | Ngày đầy đủ |
| `month`, `year`, `quarter` | INT | Thành phần thời gian |
| `day_of_week` | VARCHAR(15) | Tên thứ (tiếng Anh) |

### `Dim_Location`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `location_id` | VARCHAR(50) (PK) | Prefix mã bưu điện (5 ký tự) |
| `zip_code_prefix` | VARCHAR(5) | Mã bưu điện |
| `city`, `state` | VARCHAR | Thành phố / bang |
| `latitude`, `longitude` | DOUBLE | Toạ độ trung bình theo mã bưu điện |

### `Dim_Product`

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `product_id` | VARCHAR(50) (PK) | Mã sản phẩm |
| `category_name_english` | VARCHAR(100) | Danh mục đã dịch sang tiếng Anh |
| `weight_g`, `volume_cm3` | DOUBLE | Khối lượng / thể tích |

### `Fact_Delivery_SLA`

Khóa chính kết hợp: `(order_id, order_item_id)`.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `order_id`, `order_item_id` | VARCHAR, INT | PK kết hợp |
| `product_id` | VARCHAR | FK → `Dim_Product` |
| `customer_location_id` | VARCHAR | FK → `Dim_Location` |
| `seller_location_id` | VARCHAR | FK → `Dim_Location` |
| `time_id` | INT | FK → `Dim_Time` (ngày mua) |
| `payment_type` | VARCHAR(50) | Chiều suy biến (degenerate dimension) |
| `approval_time_days` | DOUBLE | Số ngày từ mua đến duyệt đơn |
| `seller_prep_time_days` | DOUBLE | Số ngày người bán chuẩn bị hàng |
| `carrier_transit_time_days` | DOUBLE | Số ngày vận chuyển đến khách |
| `freight_value` | DOUBLE | Phí vận chuyển |
| `review_score` | INT | Điểm đánh giá 1–5 (NULL nếu chưa có) |
| `delay_days` | DOUBLE | Số ngày giao muộn so với cam kết |
| `has_logistics_complaint` | BOOLEAN | Khiếu nại liên quan logistics |

**Quy ước `delay_days`:**

- `> 0`: giao **muộn** so với ngày dự kiến
- `= 0`: giao **đúng hạn**
- `< 0`: giao **sớm**

Cột `is_late` cũ đã được thay thế hoàn toàn bằng `delay_days`; nếu cần cờ nhị
phân, dùng điều kiện `delay_days > 0`.

---

## Ghi chú phát triển

- Model Django (`backend/analytics/models.py`) và Prisma
  (`prisma/schema.prisma`) phải được cập nhật đồng bộ khi thay đổi DDL.
- Bảng DW do `sql/create_tables.sql` quản lý, không dùng migration của Django.
- Khi thay đổi cấu trúc bảng, quy trình đúng là:
  1. Cập nhật `sql/create_tables.sql`
  2. Drop & tạo lại bảng (hoặc `ALTER TABLE`)
  3. Chạy lại ETL: `python etl\main.py --load`
  4. Cập nhật model Django / Prisma nếu có cột thay đổi
