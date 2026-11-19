# Brazillian — Olist Logistics DSS

Đồ án Data Warehouse & Hệ hỗ trợ quyết định (DSS) cho bài toán logistics, xây
dựng từ bộ dữ liệu **Olist Brazilian E-commerce**.

Hệ thống gồm 4 phần:

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Data Warehouse | PostgreSQL (Star Schema) | Lưu dữ liệu phân tích |
| ETL | Python + pandas + psycopg2 | Làm sạch, tính toán, nạp DW |
| Backend | Flask 3 (app factory + Blueprint) | API DSS, BI/OLAP, auth trên một cổng `:8000`, psycopg2 |
| Frontend | React 19 + Vite 8 + Tailwind | Dashboard, OLAP, Analytics và tab DSS gọi API thật; ETL Monitor còn mock |

---

## Trạng thái hiện tại

- **ETL**: hoàn chỉnh, sinh 5 file CSV trong `data/processed/` và nạp được vào
  PostgreSQL.
- **DW**: 5 bảng `Dim_Time`, `Dim_Location`, `Dim_Product`, `Dim_Seller`,
  `Fact_Delivery_SLA` đã được tạo và nạp dữ liệu.
- **Backend**: Flask 3, app factory `create_app()`, một app duy nhất phục vụ
  `:8000`: 9 route `/api/dss/*`, 13 route BI/OLAP (`/api/olap/*`,
  `/api/dashboard/*`, `/api/analytics/*`, `/api/health`) và 3 route auth
  `/api/auth/*`. Tài liệu DSS: `reports/api_dss.md`.
  Dữ liệu phân tích đọc từ CSV (`data/processed/`); `dss_action_log` và
  `accounts` dùng `psycopg2` trực tiếp.
- **Frontend**: React 19 + Vite 8 trong `frontend/`, gọi 5 endpoint thật
  (`/api/olap/metadata`, `/api/olap/query`, `/api/dashboard/overview`,
  `/api/analytics/sla-breakdown`, `/api/analytics/regions`). Dev chạy Vite
  `:5173` và proxy `/api` sang Flask `:8000`.
- **Kiểm thử**: chạy `pytest -q`; dùng `tests/golden_compare.py` để đối chiếu
  snapshot Django → Flask và `scripts/verify_report_numbers.py` để kiểm tra
  số liệu báo cáo.

### Các khối DSS và API

| Endpoint | Chức năng |
|---|---|
| `/routes`, `/scenario`, `/promise`, `/actions` | Tuyến, mô phỏng, promise và ghi nhận hành động |
| `/brief` | Decision Brief gồm các nhóm hành động và GMV |
| `/attribution` | Attribution theo peer benchmark; `q` chỉ nhận `0.25` hoặc `0.5` |
| `/promise-policy` | Bảng mức phục vụ 85/90/95%, không phải khuyến nghị đặt promise |
| `/sellers`, `/portfolio` | Seller scorecard và danh mục seller; `k=102` bao phủ 50,10% đơn trễ |

Decision Brief chỉ dùng NET cho promise; tổng các nhóm là top-N, có thể chồng
lấn và không phải tổng đơn tránh được. Nội dung what-if là “nếu… thì ước tính”;
đổi promise là đổi định nghĩa trễ, không rút ngắn thời gian giao.

### Snapshot đánh giá hiện hành

- Fact có 20 cột theo DDL; raw eval ghi nhận 110.173 dòng cấp item.
- Sau lọc 1.390 đơn-tuyến có stage time âm, còn 95.591 đơn-tuyến trên
  95.082 đơn duy nhất.
- Tỷ lệ trễ: 8,1556% theo đơn-tuyến; 8,1950% theo đơn duy nhất.
- Backtest min_orders=30: 16/19 kỳ, weighted diff +8,2826 pp (tương quan
  hồi cứu, không phải hiệu quả can thiệp).
- V4 sign test vs through: 12 dương / 4 âm, n=16; p hai phía 0,07681.
- V2 route bootstrap: 500 lần, seed 42, q=0,50; transit đứng đầu cấp hệ thống
  500/500 lần. CI và attribution chi tiết ở `reports/dss_eval_raw.txt`.

> **⚠️ Nhãn cảnh báo giao diện:**
> - Tab **DSS** lấy số liệu từ `/api/dss/*` (routes, attribution, scenario, promise,
>   promise-policy, sellers, portfolio, brief, actions) và ghi nhận qua
>   `POST /api/dss/actions`; các số “tránh được” là mô phỏng theo luật DSS, không
>   phải tác động nhân quả. Giao diện gồm 6 khối theo luồng quyết định: Tuyến ưu
>   tiên → Giai đoạn nghẽn → Mức rút ngắn → Ngày cam kết → Người bán → Decision
>   Brief (hai khối giữa nằm trong phần “Phân tích hỗ trợ”).
> - Các tab **Dashboard**, **OLAP**, **Analytics** đã gọi API thật và phản ánh
>   dữ liệu Olist trong database.

---

## Cấu trúc thư mục

```
Brazillian/
├── .env                        # DATABASE_URL cho ETL (không commit)
├── .gitignore
├── requirements.txt            # Thư viện Python cho ETL + backend
├── README.md
├── Assignment.code-workspace   # Mở project bằng VS Code
│
├── data/
│   ├── raw/                    # 9 file CSV gốc Olist — KHÔNG sửa
│   └── processed/              # CSV sau ETL (sinh tự động, không commit)
│
├── etl/                        # Pipeline ETL + mô hình DSS
│   ├── config.py               # Đường dẫn + cấu hình kết nối DB
│   ├── main.py                 # Điểm chạy pipeline (Transform / --load)
│   ├── dim_time.py             # Sinh Dim_Time
│   ├── dim_location.py         # Sinh Dim_Location
│   ├── dim_product.py          # Sinh Dim_Product
│   ├── dim_seller.py           # Sinh Dim_Seller
│   ├── fact_delivery_sla.py    # Sinh Fact_Delivery_SLA
│   ├── load_data.py            # Nạp CSV vào PostgreSQL (1 transaction)
│   ├── dss_models.py           # Model Base DSS rule-based
│   └── dss_eval.py             # Backtest, bootstrap, threshold sensitivity
│
├── sql/
│   ├── create_tables.sql       # DDL 5 bảng DW + dss_action_log
│   ├── create_accounts.sql     # Bảng accounts cho auth
│   └── create_indexes.sql      # Index hiệu năng
│
├── backend/                    # Flask 3
│   ├── wsgi.py                 # Entry point (flask run / gunicorn / waitress)
│   ├── .env.example            # Mẫu cấu hình (copy thành .env)
│   ├── dss/                    # App factory, Blueprint, service, psycopg2
│   │   ├── app.py              # create_app(), CORS, error handlers
│   │   ├── api.py              # 9 route /api/dss/*
│   │   ├── bi_api.py           # /api/dashboard/*, /api/analytics/*
│   │   ├── olap_api.py         # /api/olap/*
│   │   ├── auth_api.py         # /api/auth/*
│   │   ├── bi_service.py       # Nghiệp vụ BI/OLAP
│   │   ├── bi_repo.py          # SQL cho BI/OLAP
│   │   ├── bi_validation.py    # Validate tham số
│   │   ├── auth_service.py     # Hash/verify mật khẩu
│   │   ├── api_errors.py       # JSON error handlers
│   │   ├── service.py          # Glue framework-free gọi etl/
│   │   ├── db.py               # psycopg2 (fetch/execute, action log)
│   │   ├── config.py           # Đọc biến môi trường
│   │   └── json_provider.py    # JSON tương thích JsonResponse
│   ├── logs/                   # Log theo ngày (untracked)
│   └── env/                    # Virtualenv Python của backend (không commit)
│
├── frontend/                   # React 19 + Vite 8
│   ├── src/
│   ├── public/
│   └── package.json
│
├── examples/                   # Trang demo HTML gọi API DSS
├── scripts/                    # check.ps1, clear_action_log.py, verify_report_numbers.py
└── tests/                      # pytest + golden parity
```

---

## Yêu cầu môi trường

- Python **3.13**
- PostgreSQL (đã tạo database và user)
- Node.js **20.19+** (Vite 8)

---

## Cài đặt

### 1. Tạo database

Ví dụ với user `brazillian_admin` (đổi thông tin cho khớp `.env` của bạn):

```powershell
psql -U postgres -c "CREATE USER brazillian_admin WITH PASSWORD '123456789';"
psql -U postgres -c "CREATE DATABASE ""Brazillian"" OWNER brazillian_admin;"

# Tạo 5 bảng DW + dss_action_log
psql -U brazillian_admin -d Brazillian -f sql\create_tables.sql

# Bảng accounts (auth) + index hiệu năng
psql -U brazillian_admin -d Brazillian -f sql\create_accounts.sql
psql -U brazillian_admin -d Brazillian -f sql\create_indexes.sql
```

> Nếu database/user đã tồn tại, bỏ qua bước `CREATE` tương ứng. `create_tables.sql`
> không dùng `IF NOT EXISTS`, nên nếu 5 bảng đã có thì cần drop trước khi tạo lại.

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

**ETL** đọc file `.env` ở thư mục gốc:

```env
DATABASE_URL="postgresql://brazillian_admin:123456789@localhost:5432/Brazillian?schema=public"
```

**Flask** đọc file `backend/.env` (xem mẫu `backend/.env.example`):

```env
SECRET_KEY=...
FLASK_DEBUG=true
BACKEND_HOST=localhost
BACKEND_PORT=8000
# DJANGO_ALLOWED_HOSTS vẫn được đọc nếu muốn giới hạn Host
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

POSTGRES_DB=Brazillian
POSTGRES_USER=brazillian_admin
POSTGRES_PASSWORD=123456789
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

CORS_ALLOW_ALL_ORIGINS=true
```

`SECRET_KEY` là bắt buộc khi chạy thật (chỉ được phép rỗng khi `TESTING`).

### 4. Backend Flask

```powershell
cd backend
.\env\Scripts\Activate.ps1
pip install -r ..\requirements.txt

$env:FLASK_APP = "wsgi"
flask run --host 127.0.0.1 --port 8000
```

Backend chạy tại `http://127.0.0.1:8000/` — một app duy nhất cho:
`/api/dss/*` (9 route, không có dấu `/` cuối, giống URLConf cũ),
`/api/olap/*`, `/api/dashboard/*`, `/api/analytics/*`, `/api/auth/*` và
`/api/health`. Không cần migration: bảng `dss_action_log` và `accounts` nằm
trong `sql/create_tables.sql` / `sql/create_accounts.sql`; `dss_action_log` phải
rỗng sau khi chạy test.

### 5. Frontend

Giao diện chính là React 19 + Vite 8 trong `frontend/`, gọi 5 API thật:
`GET /api/olap/metadata`, `POST /api/olap/query`,
`GET /api/dashboard/overview`, `GET /api/analytics/sla-breakdown`,
`GET /api/analytics/regions`. Tab DSS gọi thêm `GET /api/dss/routes`,
`GET /api/dss/attribution`, `GET /api/dss/scenario`, `GET /api/dss/promise`,
`GET /api/dss/promise-policy`, `GET /api/dss/sellers`, `GET /api/dss/portfolio`,
`GET /api/dss/brief`, `GET /api/dss/actions` và `POST /api/dss/actions`;
transport ở `frontend/src/data/api.js`, mapping response ở
`frontend/src/data/dssAdapter.js` và các thành phần dùng chung của 6 khối ở
`frontend/src/views/dssParts.jsx`. ETL Monitor vẫn là mock.

```powershell
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173/`. Vite proxy `/api` sang Flask `:8000`
(`frontend/vite.config.js`, đọc `BACKEND_HOST` / `BACKEND_PORT` trong `.env` ở
thư mục gốc, mặc định `localhost:8000`), nên trình duyệt chỉ thấy một origin và
không cần cấu hình CORS.

### 6. Kiểm thử

```powershell
cd Brazillian
.\backend\env\Scripts\Activate.ps1

pytest -q                                      # chạy toàn bộ test suite
python tests\golden_capture.py flask           # ghi tests/golden/flask.json
python tests\golden_compare.py                 # so với tests/golden/django.json
python -m scripts.verify_report_numbers        # số liệu phải khớp báo cáo
```

`tests/golden/django.json` là snapshot bất biến của backend cũ; không sửa file
này khi Flask lệch. Fixture test tự xoá `dss_action_log` trước và sau mỗi test.

### 7. Chạy production

```powershell
cd backend
$env:FLASK_DEBUG = "false"
pip install -r ..\requirements.txt

# Windows
waitress-serve --listen=0.0.0.0:8000 wsgi:application

# Linux/macOS
gunicorn wsgi:application --bind 0.0.0.0:8000 --workers 2
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
python etl\dim_seller.py
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
- `load_data.py` sẽ `TRUNCATE` cả 5 bảng DW rồi nạp lại toàn bộ, nên chạy lại
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
3. **Review (text mining)**: lấy review mới nhất theo `review_creation_date`;
   nếu hòa, lần lượt dùng `review_answer_timestamp` rồi `review_id`. Dò từ khoá
   logistics tiếng Bồ Đào Nha; đánh dấu `has_logistics_complaint` khi
   `review_score <= 2` **và** có từ khoá.
4. **Payment**: cộng `payment_value` theo loại thanh toán của mỗi đơn, chọn
   loại có tổng cao nhất; nếu hòa, chọn `payment_sequential` nhỏ nhất rồi
   `payment_type` theo thứ tự A→Z.
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
| `location_id` | VARCHAR(5) (PK) | Prefix mã bưu điện (5 ký tự) |
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
| `order_id` | VARCHAR(50) | Thành phần PK kết hợp |
| `order_item_id` | INT | Thành phần PK kết hợp |
| `product_id` | VARCHAR(50) | FK → `Dim_Product` |
| `seller_id` | VARCHAR(50) | FK → `Dim_Seller` |
| `customer_location_id` | VARCHAR(5) | FK → `Dim_Location` |
| `seller_location_id` | VARCHAR(5) | FK → `Dim_Location` |
| `time_id` | INT | FK → `Dim_Time` (ngày mua) |
| `payment_type` | VARCHAR(50) | Chiều suy biến (degenerate dimension) |
| `price`, `freight_value` | DOUBLE PRECISION | Giá sản phẩm / phí vận chuyển |
| `shipping_limit_date` | TIMESTAMP | Hạn giao cho đơn vị vận chuyển |
| `approval_time_days` | DOUBLE PRECISION | Số ngày từ mua đến duyệt đơn |
| `seller_prep_time_days` | DOUBLE PRECISION | Số ngày người bán chuẩn bị hàng |
| `carrier_transit_time_days` | DOUBLE PRECISION | Số ngày vận chuyển đến khách |
| `delay_days` | DOUBLE PRECISION | Chênh lệch ngày giao thực tế so với dự kiến |
| `total_lead_days` | DOUBLE PRECISION | Tổng thời gian từ mua đến giao |
| `promise_days` | DOUBLE PRECISION | Thời gian cam kết giao |
| `distance_km` | DOUBLE PRECISION | Khoảng cách người bán–khách hàng |
| `review_score` | INT | Điểm đánh giá 1–5 (NULL nếu chưa có) |
| `has_logistics_complaint` | BOOLEAN | Khiếu nại liên quan logistics |

**Quy ước `delay_days`:**

- `> 0`: giao **muộn** so với ngày dự kiến
- `= 0`: giao **đúng hạn**
- `< 0`: giao **sớm**

Cột `is_late` cũ đã được thay thế hoàn toàn bằng `delay_days`; nếu cần cờ nhị
phân, dùng điều kiện `delay_days > 0`.

---

## Ghi chú phát triển

- Bảng DW do `sql/create_tables.sql` quản lý; backend Flask không dùng ORM hay
  migration. `dss_action_log` nằm trong `sql/create_tables.sql`, `accounts` nằm
  trong `sql/create_accounts.sql`, index ở `sql/create_indexes.sql`.
- Công thức DSS nằm trong `etl/`; `backend/dss/service.py` chỉ là lớp glue
  framework-free. Không hardcode ngưỡng trong route: đọc từ hợp đồng
  `/brief.parameters` (`min_orders`, `seller_min_orders`, `low_sample_threshold`)
  và `base_rate` từ `/brief.config`.
- Khi thay đổi cấu trúc bảng, quy trình đúng là:
  1. Cập nhật `sql/create_tables.sql`
  2. Drop & tạo lại bảng (hoặc `ALTER TABLE`)
  3. Chạy lại ETL: `python etl\main.py --load`
