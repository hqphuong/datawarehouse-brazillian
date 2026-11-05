# Hướng dẫn khởi động và chạy test

Repo: `Brazillian/`. Môi trường: Windows, Python 3.13, PostgreSQL đã cài sẵn.

---

## 1. Chuẩn bị lần đầu

### 1.1 Tạo virtualenv và cài thư viện (nếu chưa có)

```powershell
# Từ thư mục gốc Brazillian/
cd backend
python -m venv env
.\env\Scripts\Activate.ps1
pip install django psycopg2-binary python-dotenv djangorestframework django-cors-headers
```

> Nếu `backend\env\` đã tồn tại, bỏ qua bước tạo venv.

### 1.2 Cấu hình `.env` cho Django

Tạo hoặc kiểm tra `backend\.env` (xem mẫu `backend\.env.new`):

```env
SECRET_KEY=<chuỗi ngẫu nhiên dài>
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

POSTGRES_DB=Brazillian
POSTGRES_USER=brazillian_admin
POSTGRES_PASSWORD=123456789
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### 1.3 Tạo bảng hệ thống Django và bảng DSS

```powershell
cd backend
.\env\Scripts\Activate.ps1
python manage.py migrate
```

Lệnh này tạo các bảng nội bộ Django (auth, sessions, ...) **và** bảng `dss_action_log` (migration `dss/migrations/0001_initial.py`).  
Bốn bảng DW (`Dim_Time`, `Dim_Location`, `Dim_Product`, `Fact_Delivery_SLA`) đã được tạo bằng `sql/create_tables.sql` và dùng `managed = False` nên **không** bị migrate.

### 1.4 Sinh dữ liệu CSV (nếu `data/processed/` trống)

```powershell
cd ..                          # về Brazillian/
.\.venv\Scripts\Activate.ps1  # hoặc dùng backend\env
python etl\main.py             # chỉ transform, không load DB
```

Bốn file được sinh: `data/processed/cleaned_fact_orders.csv`, `cleaned_dim_time.csv`, `cleaned_dim_location.csv`, `cleaned_dim_product.csv`.

---

## 2. Khởi động Django (backend)

```powershell
cd backend
.\env\Scripts\Activate.ps1
python manage.py runserver 8000
```

Server chạy tại `http://127.0.0.1:8000/`. Khi thấy dòng:

```
Watching for file changes with StatReloader
```

là backend đã sẵn sàng. Lần đầu khởi động có thể mất 5–10 giây để nạp ~97 000 dòng CSV vào bộ nhớ.

> Chạy từ ngoài thư mục `backend/` cũng được nếu dùng đường dẫn tuyệt đối:
> ```powershell
> .\backend\env\Scripts\python.exe backend\manage.py runserver 8000
> ```

---

## 3. Mở giao diện DSS

Mở file `web\Olist_Logistics_DSS_v3.html` bằng trình duyệt (Chrome/Edge):

```powershell
Start-Process "web\Olist_Logistics_DSS_v3.html"
```

hoặc kéo thả file vào trình duyệt. Giao diện gọi `http://localhost:8000/api/dss` — cần Django đang chạy (bước 2).

> **⚠️ Nhãn cảnh báo giao diện (quan trọng khi trình bày):**
> - Tab **Dashboard**, **OLAP**, **ETL Monitor** hiển thị **dữ liệu mẫu** (mock
>   data, do thành viên khác phát triển bằng Flask, chưa nối Django thật). Số
>   liệu trên các tab này **không phản ánh dữ liệu Olist thực tế**.

---

## 4. Chạy kiểm thử

### 4.1 pytest (unit test + eval test, không cần DB)

```powershell
# Từ thư mục gốc Brazillian/
.\backend\env\Scripts\python.exe -m pytest -q
```

Kết quả kỳ vọng: **26 passed** (~5–7 giây).

Chạy verbose hơn:

```powershell
.\backend\env\Scripts\python.exe -m pytest -v
```

Danh sách test:
- `tests/test_dss_models.py` — 19 test kiểm tra hợp đồng dữ liệu các hàm mô hình
- `tests/test_dss_eval.py` — 7 test kiểm tra backtest, threshold sensitivity, top routes, negative time

### 4.2 Django test (`manage.py test dss`) — cần PostgreSQL

```powershell
cd backend
.\env\Scripts\python.exe manage.py test dss
```

hoặc với output chi tiết:

```powershell
.\env\Scripts\python.exe manage.py test dss -v 2
```

Kết quả kỳ vọng: **16 tests OK** (~10–30 giây do phải tạo/xóa test database).

> Django test tạo một database tạm (`test_Brazillian`) trên PostgreSQL, chạy xong tự xóa. Cần PostgreSQL đang chạy và user có quyền `CREATEDB`.

---

## 5. Lỗi thường gặp

### "No module named 'etl'"

pytest không tìm thấy package `etl`. Kiểm tra file `tests/conftest.py` đã thêm thư mục gốc vào `sys.path`. Chạy pytest từ thư mục gốc `Brazillian/`, không phải từ `tests/`.

```powershell
# Sai — chạy từ trong tests/
cd tests; python -m pytest

# Đúng
cd Brazillian; .\backend\env\Scripts\python.exe -m pytest -q
```

### "FileNotFoundError: cleaned_fact_orders.csv"

`data/processed/` trống. Sinh lại CSV:

```powershell
.\backend\env\Scripts\python.exe etl\main.py
```

### "django.db.utils.OperationalError: could not connect to server"

PostgreSQL chưa chạy, hoặc thông tin kết nối trong `backend\.env` sai. Kiểm tra:

```powershell
psql -U brazillian_admin -d Brazillian -c "SELECT 1;"
```

### "manage.py test dss." (có dấu chấm ở cuối)

Lỗi thường gặp khi gõ nhầm:

```powershell
# Sai — dấu chấm ở cuối khiến Django tìm app "dss." (không tồn tại)
python manage.py test dss.

# Đúng
python manage.py test dss
```

### "table dss_action_log does not exist"

Chưa chạy migrate. Chạy:

```powershell
cd backend
python manage.py migrate
```

### "Permission denied to create database" khi chạy `manage.py test`

Django cần quyền `CREATEDB` để tạo test database. Cấp quyền:

```powershell
psql -U postgres -c "ALTER USER brazillian_admin CREATEDB;"
```

### CORS error khi mở `web/*.html` bằng file://

Đã được cấu hình `CORS_ALLOW_ALL_ORIGINS = True` trong `backend/core/settings.py`. Nếu vẫn lỗi, kiểm tra Django đang chạy đúng port 8000.

---

## 6. Thứ tự khởi động đầy đủ (tóm tắt)

```powershell
# 1. Đảm bảo PostgreSQL đang chạy

# 2. Sinh CSV (nếu cần)
.\backend\env\Scripts\python.exe etl\main.py

# 3. Migrate (lần đầu hoặc sau khi thêm migration)
cd backend
.\env\Scripts\python.exe manage.py migrate

# 4. Khởi động server
.\env\Scripts\python.exe manage.py runserver 8000

# 5. Mở giao diện (tab mới trong terminal)
Start-Process "..\web\Olist_Logistics_DSS_v3.html"

# 6. Chạy kiểm thử (terminal riêng, từ Brazillian/)
.\backend\env\Scripts\python.exe -m pytest -q
cd backend; .\env\Scripts\python.exe manage.py test dss
```
