# Báo cáo Phân tích & Đề xuất Thích ứng Backend với Kho Dữ liệu Mới
*(Adopt Backend Report for Olist Logistics DSS)*

**Dự án:** OLIST Logistics Decision Support System (DSS)  
**Nhánh nguồn:** `backend` (Flask Backend & API cũ)  
**Nhánh đích:** `dss-v2` / `backend-v2` (Data Warehouse cải tiến & Django DSS Engine)  
**Ngày lập:** Tháng 11/2026  
**Người thực hiện:** Antigravity AI Assistant  

---

## Tóm tắt Tổng quan (Executive Summary)

Dự án hiện tại tồn tại hai luồng phát triển song song:
1. **Nhánh `backend`:** Đã triển khai hoàn chỉnh một Backend RESTful API bằng **Flask + Flask-Smorest + Marshmallow + SQLAlchemy** phục vụ 10 endpoints cho các màn hình Dashboard KPI, Phân tích trễ hẹn (Late Trend), Phân rã SLA (SLA Breakdown), Tra cứu đơn hàng (Order Drill-through), Tuyến vận chuyển vùng (Regions), Hiệu suất người bán (Sellers) và Cảnh báo vận hành (Alerts). Toàn bộ mã nguồn dựa trên cấu trúc Data Warehouse (DW) ban đầu (4 bảng: `Dim_Time`, `Dim_Location`, `Dim_Product`, `Fact_Delivery_SLA`).
2. **Nhánh `dss-v2`:** Bạn của bạn đã tối ưu hóa toàn diện cấu trúc Data Warehouse theo Star Schema chuẩn (thêm bảng chiều `Dim_Seller`, chuẩn hóa khóa `location_id` 5 ký tự, loại bỏ cột cờ `is_late`, bổ sung các độ đo liên tục như `delay_days`, `total_lead_days`, `promise_days`, `price`, `distance_km`), đồng thời xây dựng bộ mô hình phân tích DSS và giao diện mô phỏng (`web/Olist_Logistics_DSS_v3.html`) trên nền Django (`backend/dss/`).

Bạn đã tạo nhánh mới **`backend-v2`** từ **`dss-v2`** nhằm tích hợp mã nguồn Backend vào hệ thống kho dữ liệu mới. Báo cáo này giải quyết trọn vẹn 3 nhiệm vụ:
- **Nhiệm vụ 1:** Liệt kê toàn bộ các thay đổi trong cấu trúc DW (DDL, ETL, dữ liệu, logic nghiệp vụ).
- **Nhiệm vụ 2:** Đề xuất chi tiết những gì cần thay đổi trong database và backend để giữ nguyên các tính năng hiện tại, kèm giải thích **LÝ DO (WHY)**.
- **Nhiệm vụ 3:** Dự báo các rủi ro, lỗi tiềm ẩn có thể phát sinh và giải thích căn nguyên **TẠI SAO (WHY)** kèm biện pháp xử lý.

---

## 1. Chi tiết các thay đổi trong cấu trúc Data Warehouse (DW Structure Changes)

So sánh giữa nhánh `backend` (schema cũ) và nhánh `dss-v2` (schema mới) cho thấy những thay đổi mang tính cốt lõi từ tầng DDL, ETL pipeline đến quy tắc biến đổi dữ liệu.

### 1.1. Thay đổi về Lược đồ Cơ sở Dữ liệu & DDL (`sql/create_tables.sql`)

| Bảng / Đối tượng | Trạng thái | Chi tiết thay đổi | Ý nghĩa cấu trúc |
|---|---|---|---|
| **`Dim_Seller`** | **MỚI (Thêm mới)** | `seller_id VARCHAR(50) PRIMARY KEY`, `location_id VARCHAR(5)`, `city VARCHAR(100)`, `state VARCHAR(5)`. Có FK liên kết tới `Dim_Location(location_id)`. | Chuẩn hóa chiều người bán thành một Dimension độc lập thay vì bị gộp chung hoặc làm mờ vào vị trí địa lý. |
| **`Dim_Location`** | **SỬA ĐỔI** | Cột `location_id` đổi kiểu từ `VARCHAR(50)` sang `VARCHAR(5)`. | Khóa địa điểm được chuẩn hóa về đúng độ dài 5 chữ số của mã bưu điện Brazil (CEP prefix). |
| **`Fact_Delivery_SLA`** | **SỬA ĐỔI KHÓA** | - Thêm khóa ngoại: `seller_id VARCHAR(50)` tham chiếu tới `Dim_Seller(seller_id)`.<br>- Sửa khóa ngoại: `customer_location_id` và `seller_location_id` đổi từ `VARCHAR(50)` sang `VARCHAR(5)`. | Khôi phục mối liên kết trực tiếp giữa đơn hàng/mặt hàng với người bán cụ thể (`seller_id`). |
| **`Fact_Delivery_SLA`** | **BỊ XÓA** | Cột cờ **`is_late BOOLEAN`** đã bị **XÓA BỎ HOÀN TOÀN** khỏi bảng Fact. | Đây là **thay đổi phá vỡ (breaking change)** lớn nhất đối với các truy vấn SQL của backend cũ. |
| **`Fact_Delivery_SLA`** | **THÊM ĐỘ ĐO MỚI** | Thêm 7 cột độ đo mới:<br>1. `price DOUBLE PRECISION`<br>2. `shipping_limit_date TIMESTAMP`<br>3. `delay_days DOUBLE PRECISION`<br>4. `total_lead_days DOUBLE PRECISION`<br>5. `promise_days DOUBLE PRECISION`<br>6. `handoff_slack_days DOUBLE PRECISION`<br>7. `distance_km DOUBLE PRECISION` | Chuyển đổi từ đo lường nhị phân (trễ/không trễ) sang đo lường liên tục, bổ sung thông tin tài chính (GMV) và khoảng cách địa lý. |

#### Chi tiết các độ đo mới trong `Fact_Delivery_SLA`:
- **`price`**: Giá bán mặt hàng (từ `order_items`), cho phép tính toán tổng giá trị hàng hóa (GMV) và doanh thu bị ảnh hưởng do trễ hạn.
- **`shipping_limit_date`**: Hạn chót người bán phải bàn giao hàng cho bưu tá/đơn vị vận chuyển.
- **`delay_days`**: Độ lệch ngày giữa ngày giao thực tế và ngày cam kết (`order_delivered_customer_date - order_estimated_delivery_date`).
  - `delay_days > 0`: Giao trễ so với cam kết (thay thế cho `is_late = TRUE`).
  - `delay_days < 0`: Giao sớm hơn cam kết.
  - `delay_days = 0`: Giao đúng hạn.
- **`total_lead_days`**: Tổng thời gian hoàn tất đơn hàng tính bằng ngày (`order_delivered_customer_date - order_purchase_timestamp`).
- **`promise_days`**: Thời gian cam kết giao hàng (`total_lead_days - delay_days`, đúng bằng `order_estimated_delivery_date - order_purchase_timestamp`).
- **`handoff_slack_days`**: Độ trễ bàn giao của người bán cho carrier (`order_delivered_carrier_date - shipping_limit_date`).
- **`distance_km`**: Khoảng cách địa lý đường chim bay (công thức Haversine) giữa tâm vị trí người bán và tâm vị trí khách hàng tính theo tọa độ GPS.

---

### 1.2. Thay đổi trong Quy trình & Logic Biến đổi ETL (`etl/`)

1. **Cấu trúc thư mục & Cách thức thực thi:**
   - Mã ETL được chuyển từ thư mục `src/` sang thư mục chuẩn `etl/`.
   - Lệnh thực thi được chuẩn hóa thành dạng Python module:
     - Chế độ chỉ Transform (sinh CSV): `python -m etl.main`
     - Chế độ Transform + Load DB: `python -m etl.main --load`
2. **Cơ chế nạp dữ liệu nguyên tử (Atomic Load via Single Transaction - `etl/load_data.py`):**
   - *ETL cũ:* Thực hiện `TRUNCATE` và `conn.commit()` sau từng bảng riêng rẽ. Nếu bảng thứ 4 hoặc 5 bị lỗi, các bảng trước đó đã bị xóa hoặc nạp dở dang, khiến database rơi vào trạng thái hỏng (corrupted/inconsistent state).
   - *ETL mới:* Toàn bộ thao tác `TRUNCATE` và `COPY` cho cả 5 bảng (`Dim_Time`, `Dim_Location`, `Dim_Product`, `Dim_Seller`, `Fact_Delivery_SLA`) được bọc trong **một Transaction duy nhất**. Nếu bất kỳ bảng nào gặp lỗi, toàn bộ transaction được `ROLLBACK`, kho dữ liệu giữ nguyên vẹn trạng thái trước khi nạp.
3. **Quy tắc khử trùng lặp tất định (Deterministic Transformation Rules - `etl/transform_rules.py`):**
   - *Phương thức thanh toán (`payment_type`):*
     - *Cũ:* `df_payments.sort_values("payment_value", ascending=False).drop_duplicates("order_id", keep="first")` -> Nếu có nhiều dòng thanh toán bằng giá trị, kết quả phụ thuộc ngẫu nhiên vào thứ tự dòng.
     - *Mới:* Sử dụng hàm `select_payment_type()`. Gom nhóm theo `(order_id, payment_type)`, tính tổng `payment_value`, sau đó ưu tiên theo: (1) Tổng giá trị lớn nhất -> (2) Số thứ tự `payment_sequential` nhỏ nhất -> (3) Tên loại thanh toán theo alphabet.
   - *Đánh giá của khách hàng (`reviews`):*
     - *Cũ:* Sắp xếp theo `review_creation_date` rồi lấy dòng cuối.
     - *Mới:* Sử dụng `select_latest_reviews()`. Sắp xếp có tie-break chặt chẽ: `order_id -> review_creation_date -> review_answer_timestamp -> review_id` (ID lớn hơn = mới hơn).
4. **Chuẩn hóa khóa địa lý (`location_id`):**
   - Mã bưu điện Brazil gồm 5 chữ số. Trước đây, nhiều mã có chữ số 0 ở đầu (ví dụ `01001`) bị đọc thành số nguyên `1001` (4 ký tự).
   - ETL mới áp dụng `.astype(str).str.zfill(5)` xuyên suốt `Dim_Location`, `Dim_Seller` và `Fact_Delivery_SLA`, đồng thời kích hoạt kiểm tra nghiêm ngặt `assert` độ dài phải đúng bằng 5, ngăn chặn triệt để hiện tượng mất liên kết Foreign Key (orphan keys).
5. **Xử lý tọa độ Geolocation khuyết thiếu:**
   - Khoảng 162 vị trí không có tọa độ GPS. ETL mới để trống dạng `NaN` (nạp vào PostgreSQL thành `NULL`) thay vì tự ý điền `0.0`, tránh làm méo mó phép tính khoảng cách địa lý `distance_km`.

---

### 1.3. Bảng Đối chiếu Chi tiết Schema Cũ vs Schema Mới

```mermaid
erDiagram
    Dim_Time {
        int time_id PK
        date full_date
        int month
        int year
        int quarter
        varchar day_of_week
    }
    Dim_Location {
        varchar location_id PK "VARCHAR(5) [Cũ: VARCHAR(50)]"
        varchar zip_code_prefix "5 ký tự"
        varchar city
        varchar state
        double latitude
        double longitude
    }
    Dim_Product {
        varchar product_id PK
        varchar category_name_english
        double weight_g
        double volume_cm3
    }
    Dim_Seller {
        varchar seller_id PK "BẢNG MỚI THÊM"
        varchar location_id FK
        varchar city
        varchar state
    }
    Fact_Delivery_SLA {
        varchar order_id PK
        int order_item_id PK
        varchar product_id FK
        varchar seller_id FK "FK MỚI THÊM"
        varchar customer_location_id FK "VARCHAR(5)"
        varchar seller_location_id FK "VARCHAR(5)"
        int time_id FK
        varchar payment_type
        double price "MỚI THÊM (GMV)"
        double freight_value
        timestamp shipping_limit_date "MỚI THÊM"
        double approval_time_days
        double seller_prep_time_days
        double carrier_transit_time_days
        double delay_days "MỚI THÊM (Thay thế is_late)"
        double total_lead_days "MỚI THÊM"
        double promise_days "MỚI THÊM"
        double handoff_slack_days "MỚI THÊM"
        double distance_km "MỚI THÊM"
        int review_score
        boolean has_logistics_complaint
    }

    Dim_Location ||--o{ Dim_Seller : "places"
    Dim_Location ||--o{ Fact_Delivery_SLA : "delivers_to (cust)"
    Dim_Location ||--o{ Fact_Delivery_SLA : "ships_from (seller_loc)"
    Dim_Seller ||--o{ Fact_Delivery_SLA : "fulfills"
    Dim_Product ||--o{ Fact_Delivery_SLA : "contains"
    Dim_Time ||--o{ Fact_Delivery_SLA : "occurs_at"
```

---

## 2. Đề xuất Thay đổi trong Cơ sở Dữ liệu & Backend và LÝ DO (WHY)

Để giữ nguyên và nâng cấp toàn bộ tính năng hiện tại của backend (10 endpoints phục vụ Dashboard, Analytics, Orders, Alerts) trên nền kho dữ liệu mới, dưới đây là các đề xuất cụ thể:

### 2.1. Thay đổi Cơ sở Dữ liệu (Database Operations)

1. **Re-create Lược đồ và Nạp lại dữ liệu vào PostgreSQL:**
   - **Thực hiện:**
     ```powershell
     # 1. Chạy lại DDL tạo cấu trúc 5 bảng mới
     psql -U postgres -d brazillian -f sql/create_tables.sql
     # 2. Chạy pipeline ETL để làm sạch và nạp 5 bảng vào PostgreSQL
     python -m etl.main --load
     ```
   - **LÝ DO (WHY):** Cơ sở dữ liệu hiện tại trên máy bạn được nạp từ branch `backend` cũ (chỉ có 4 bảng, thiếu bảng `Dim_Seller`, bảng Fact vẫn mang cột `is_late` nhưng thiếu 7 độ đo mới). Nếu không nạp lại database, schema trên đĩa và schema trong database sẽ bất đồng bộ, gây lỗi `relation does not exist` hoặc `column does not exist`.

2. **Chạy Migration nội bộ cho Django (nếu tích hợp cùng Django):**
   - **Thực hiện:** `python backend/manage.py migrate`
   - **LÝ DO (WHY):** Bảng `dss_action_log` và các bảng auth của Django được quản lý qua Django ORM migration. Riêng 5 bảng DW có cờ `managed = False` nên migration không can thiệp vào cấu trúc bảng kho.

---

### 2.2. Chiến lược Tích hợp Mã nguồn Backend (Architecture Strategy)

Hiện tại trên nhánh `backend-v2` (rẽ từ `dss-v2`):
- Mã nguồn Flask cũ (`app.py`, `repo.py`, `service.py`, `routes.py`, `schema.py`) đang ở nhánh `backend`.
- Nhánh `dss-v2` đang có Django backend phục vụ các API DSS (`/api/dss/*`) cho file giao diện HTML `web/Olist_Logistics_DSS_v3.html`.
- Trong file `reports/run_guide.md`, tài liệu nhóm đã ghi chú rõ:
  > *Tab Dashboard, OLAP, ETL Monitor hiển thị dữ liệu mẫu (mock data, do thành viên khác phát triển bằng Flask, chưa nối Django thật).*

**Đề xuất chiến lược:**
- **Giải pháp tối ưu (Bảo toàn & Độc lập):** Mang toàn bộ 5 file Flask từ nhánh `backend` sang nhánh `backend-v2`, tiến hành chỉnh sửa các câu lệnh truy vấn SQL trong `backend/repo.py` để thích ứng với schema mới.
- Flask app chạy ở cổng `5000` phục vụ OpenAPI/Swagger UI (`/swagger-ui`) và các API Dashboard/Analytics/Orders.
- Django app chạy ở cổng `8000` phục vụ Decision Support System API (`/api/dss/*`).
- Cách tiếp cận này giúp bạn giữ vững quyền tự chủ module của mình, không làm xáo trộn cấu trúc Django phức tạp của bạn mình, đồng thời hoàn thành đúng cam kết kỹ thuật ban đầu.

---

### 2.3. Chi tiết các Sửa đổi Cụ thể trong Mã nguồn Backend (Flask Codebase)

Toàn bộ các thay đổi tập trung chủ yếu vào tầng Truy cập dữ liệu (`backend/repo.py`), tầng Logic (`backend/service.py`) và tầng Lược đồ (`backend/schema.py`).

#### Sửa đổi 1: Thay thế toàn bộ logic `is_late = TRUE` thành `delay_days > 0`
- **Tập tin bị ảnh hưởng:** `backend/repo.py` (tại các hàm `get_kpi()`, `get_late_trend()`, `get_orders()`, `get_regions()`, `get_alerts()`).
- **Thay đổi chi tiết:**
  - Trong `get_kpi()`:
    ```sql
    -- CŨ:
    COUNT(CASE WHEN f.is_late = TRUE THEN 1 END) AS delay_count
    -- MỚI:
    COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS delay_count
    ```
  - Trong `get_late_trend()`:
    ```sql
    -- CŨ:
    COUNT(CASE WHEN f.is_late = TRUE THEN 1 END) AS late_count
    -- MỚI:
    COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS late_count
    ```
  - Trong `get_orders()`:
    ```sql
    -- CŨ:
    BOOL_OR(f.is_late) AS is_late
    -- MỚI:
    BOOL_OR(f.delay_days > 0) AS is_late
    ```
  - Trong `get_regions()`:
    ```sql
    -- CŨ:
    COUNT(CASE WHEN f.is_late = TRUE THEN 1 END) AS late_count
    -- MỚI:
    COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS late_count
    ```
  - Trong `get_alerts()`:
    ```sql
    -- CŨ:
    WHERE (f.has_logistics_complaint = TRUE OR f.is_late = TRUE)
    ORDER BY t.full_date DESC NULLS LAST, f.is_late DESC
    -- MỚI:
    WHERE (f.has_logistics_complaint = TRUE OR f.delay_days > 0)
    ORDER BY t.full_date DESC NULLS LAST, (f.delay_days > 0) DESC
    ```
- **LÝ DO (WHY):** Cột `is_late` đã bị xóa hoàn toàn khỏi bảng `Fact_Delivery_SLA`. Nếu giữ nguyên, PostgreSQL sẽ báo lỗi `psycopg2.errors.UndefinedColumn: column f.is_late does not exist` và làm sập (500 Internal Server Error) 5 trên 8 endpoints chính. Định nghĩa nghiệp vụ trong DW mới quy định: `delay_days` là khoảng thời gian chênh lệch giữa ngày nhận thực tế và ngày hẹn; giá trị `> 0` chính là đơn giao trễ.

---

#### Sửa đổi 2: Tái cấu trúc API Seller Analytics (`/api/analytics/sellers`) sử dụng `Dim_Seller`
- **Tập tin bị ảnh hưởng:** `backend/repo.py` (`get_sellers()`), `backend/schema.py` (`res_SellerSchema`).
- **Hiện trạng cũ:** Trước đây, do Fact table không lưu `seller_id` mà chỉ có `seller_location_id`, bạn buộc phải dùng mã bưu điện (zip prefix) làm "đại diện" (proxy) cho người bán và ghi chú đây là hạn chế trong `api_implement_report.md`.
- **Thay đổi chi tiết:**
  - Trong `backend/repo.py`:
    ```sql
    -- CŨ:
    SELECT 
        f.seller_location_id AS seller_id,
        MAX(sell_loc.city) AS seller_city,
        MAX(sell_loc.state) AS seller_state,
        COUNT(DISTINCT f.order_id) AS total_orders,
        AVG(f.seller_prep_time_days) AS avg_prep_time,
        AVG(f.review_score) AS avg_score
    FROM fact_delivery_sla f
    LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
    GROUP BY f.seller_location_id

    -- MỚI (Tối ưu chuẩn DW):
    SELECT 
        s.seller_id,
        s.city AS seller_city,
        s.state AS seller_state,
        COUNT(DISTINCT f.order_id) AS total_orders,
        AVG(f.seller_prep_time_days) AS avg_prep_time,
        AVG(f.review_score) AS avg_score
    FROM fact_delivery_sla f
    JOIN dim_seller s ON f.seller_id = s.seller_id
    LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
    LEFT JOIN dim_time t ON f.time_id = t.time_id
    {where_sql}
    GROUP BY s.seller_id, s.city, s.state
    ORDER BY {order_by_col}
    LIMIT :limit;
    ```
  - Trong `backend/repo.py` (`get_seller_states()`):
    ```sql
    -- Có thể query trực tiếp từ Dim_Seller:
    SELECT DISTINCT state FROM dim_seller WHERE state IS NOT NULL ORDER BY state;
    ```
  - Trong `backend/schema.py`: Cập nhật mô tả trường `seller_id` trong `res_SellerSchema` thành *"Unique seller identifier (UUID)"* thay vì *"Seller location identifier (zip code prefix)"*.
- **LÝ DO (WHY):** Bảng `Dim_Seller` mới cung cấp danh mục 3.095 người bán định danh chính xác bằng UUID. Việc tận dụng bảng này giúp trả về đúng thực thể người bán thương mại điện tử, khắc phục triệt để hạn chế kỹ thuật lớn nhất của phiên bản trước.

---

#### Sửa đổi 3: Tối ưu tính toán Thời gian Giao hàng bằng `total_lead_days`
- **Tập tin bị ảnh hưởng:** `backend/repo.py` (`get_kpi()`, `get_late_trend()`, `get_orders()`, `get_regions()`, `get_sla_breakdown()`).
- **Thay đổi chi tiết:**
  ```sql
  -- CŨ: Phải cộng dồn 3 stage thủ công
  AVG(f.approval_time_days + f.seller_prep_time_days + f.carrier_transit_time_days) AS avg_delivery_time

  -- MỚI: Tận dụng cột đã được tiền tính toán (precomputed)
  AVG(f.total_lead_days) AS avg_delivery_time
  ```
- **LÝ DO (WHY):** Trong DW mới, `total_lead_days` đã được tính sẵn ngay trong bước ETL (`order_delivered_customer_date - order_purchase_timestamp`). Việc sử dụng trực tiếp cột này giúp câu lệnh SQL ngắn gọn hơn, tận dụng tối đa chỉ mục và giảm thiểu chi phí tính toán số thực (floating point arithmetic) khi quét qua hơn 110.000 dòng.

---

#### Sửa đổi 4: Cập nhật Môi trường và Phụ thuộc (`requirements.txt`)
- **Tập tin bị ảnh hưởng:** `requirements.txt`.
- **Hiện trạng:** Nhánh `dss-v2` đã loại bỏ các package của Flask và chỉ giữ lại thư viện cho ETL/Django (`pandas`, `numpy`, `psycopg2-binary`, `django`, `django-cors-headers`, `pytest`).
- **Đề xuất:** Bổ sung lại các package phục vụ Flask backend vào môi trường ảo, đảm bảo phiên bản tương thích:
  ```text
  flask>=3.0.0
  flask-smorest>=0.45.0
  flask-sqlalchemy>=3.1.0
  marshmallow>=3.20.0
  python-dotenv>=1.0.0
  ```
- **LÝ DO (WHY):** Để chạy được song song cả ứng dụng Flask (API của bạn) và pipeline kiểm thử của nhánh mới mà không xảy ra xung đột `ModuleNotFoundError`.

---

## 3. Dự báo các rủi ro, lỗi tiềm ẩn và LÝ DO (What might go wrong & WHY)

Trong quá trình đưa backend lên nền kho dữ liệu mới, có nhiều rủi ro tiềm ẩn xuất phát từ sự khác biệt ngữ nghĩa dữ liệu, cấu hình hạ tầng và cách thức phối hợp nhánh. Dưới đây là phân tích chi tiết:

### 3.1. Lỗi Thực thi SQL và Lược đồ Database (Database & SQL Execution Failures)

1. **Lỗi `UndefinedColumn: column f.is_late does not exist`:**
   - **TẠI SAO (WHY):** Do thói quen query trực tiếp tên cột cũ. Cột `is_late` đã bị xóa hoàn toàn ở tầng DDL. Chỉ cần sót lại một vị trí trong mệnh đề `SELECT`, `WHERE`, hoặc `ORDER BY` của `repo.py`, toàn bộ endpoint tương ứng sẽ trả về mã lỗi 500.
2. **Lỗi `UndefinedTable: relation dim_seller does not exist`:**
   - **TẠI SAO (WHY):** Nếu bạn khởi chạy backend ngay sau khi checkout code mà quên chưa chạy lệnh tạo lại bảng trên PostgreSQL (`psql ... create_tables.sql` và `etl.main --load`), database thực tế vẫn là schema cũ.
3. **Lỗi tràn ký tự hoặc ép kiểu `VARCHAR(5)`:**
   - **TẠI SAO (WHY):** Các trường `location_id`, `customer_location_id`, `seller_location_id` hiện tại là `VARCHAR(5)`. Nếu người dùng truyền vào chuỗi lọc hoặc dữ liệu đầu vào vượt quá 5 ký tự (ví dụ: gửi cả mã zip mở rộng 8 số dạng `01001-000`), PostgreSQL sẽ ném lỗi `string data right truncation` (`22001`).

---

### 3.2. Sai lệch Ngữ nghĩa Số liệu giữa Dashboard và DSS (Data Grain & Metric Semantic Discrepancy)

Đây là rủi ro **rất nguy hiểm về mặt logic nghiệp vụ** khi bảo vệ đồ án trước giảng viên:

1. **Độ lệch hạt dữ liệu (Grain Mismatch: Order Items vs Distinct Orders):**
   - **TẠI SAO (WHY):**
     - Bảng `Fact_Delivery_SLA` có khóa chính là `(order_id, order_item_id)` (hạt ở cấp chi tiết mặt hàng - tổng cộng 110.173 dòng).
     - Trong Backend cũ của bạn: Câu lệnh KPI tính `COUNT(*)` và `COUNT(CASE WHEN ...)` trực tiếp trên bảng Fact. Nghĩa là bạn đang đếm **số lượng mặt hàng (order items)**. Một đơn hàng có 3 món đồ trễ sẽ được cộng 3 lần vào tử số và 3 lần vào mẫu số.
     - Trong DSS Engine (`etl/dss_models.py` của bạn bạn): Mô hình DSS chủ động gộp các dòng theo cặp `(order_id, route)` trước khi phân tích, ra tỷ lệ trễ cấp tuyến là **8,1556%**, và cấp đơn hàng duy nhất (`unique order_id`) là **8,1950%** trên 95.082 đơn hợp lệ.
     - **Hệ quả:** Tỷ lệ trễ (`delay_rate`) hiển thị trên tab Dashboard sẽ lệch một biên độ nhỏ so với tỷ lệ trễ hiển thị trên tab DSS. Nếu không đồng nhất công thức hoặc ghi rõ chú thích grain (Item-level vs Order-level), người dùng/giảng viên sẽ đánh giá hệ thống thiếu nhất quán dữ liệu.
2. **Ảnh hưởng từ dữ liệu thời gian âm (Negative Stage Durations):**
   - **TẠI SAO (WHY):**
     - Trong dữ liệu gốc của Olist, có **1.361 dòng** bị lỗi `seller_prep_time_days < 0` (do thời điểm đơn vị vận chuyển quét nhận hàng được ghi nhận trước cả thời điểm đơn được duyệt thanh toán!) và **29 dòng** có `carrier_transit_time_days < 0`.
     - Trong mô hình DSS, bạn của bạn chủ động **loại bỏ 1.390 dòng bất thường này** (`dropna` và lọc stage âm).
     - Tuy nhiên, trong bảng `Fact_Delivery_SLA` của PostgreSQL, 1.390 dòng này **vẫn được nạp vào** để bảo toàn số lượng đơn hàng đã giao (96.455 đơn).
     - **Hệ quả:** Nếu câu lệnh SQL của bạn tính `AVG(f.seller_prep_time_days)` mà không lọc điều kiện `>= 0`, các giá trị âm ngoại lai sẽ kéo giảm thời gian chuẩn bị trung bình xuống thấp hơn con số thống kê chính thức trong các báo cáo `reports/dss_results.md`.
3. **Biến động nhỏ ở số liệu phân rã (Tie-breaking Fluctuation):**
   - **TẠI SAO (WHY):** Do quy tắc ETL mới chuẩn hóa việc chọn `payment_type` và `review_score` theo giải thuật tất định, khoảng vài nghìn đơn hàng có nhiều hình thức thanh toán hoặc nhiều lượt đánh giá sẽ được gán giá trị chính xác hơn bản nạp cũ. Điều này khiến một số chỉ số theo kênh thanh toán hoặc điểm review có sự xê dịch nhỏ so với số liệu lưu trong `api_implement_report.md` cũ.

---

### 3.3. Xung đột Môi trường và Cấu hình Hạ tầng (Environment & Infrastructure Conflicts)

1. **Bất đồng bộ cấu hình biến môi trường Database giữa Flask và Django:**
   - **TẠI SAO (WHY):**
     - Ứng dụng Flask đọc cấu hình database qua một biến duy nhất: `DATABASE_URL` (ví dụ: `postgresql://postgres:admin@localhost:5432/brazillian`).
     - Ứng dụng Django (`backend/config/env.py`) phân tách thành 5 biến độc lập: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`. Đáng chú ý, giá trị mặc định của `POSTGRES_DB` trong code Django đang là `"tam_soat_dot_quy"`.
     - **Hệ quả:** Nếu bạn chỉ cập nhật `DATABASE_URL` mà không khai báo `POSTGRES_DB=brazillian`, Django backend sẽ cố kết nối vào database `tam_soat_dot_quy` và báo lỗi không tìm thấy cơ sở dữ liệu (`OperationalError`).
2. **Xung đột cổng chạy ứng dụng (Port Collision):**
   - **TẠI SAO (WHY):** Nếu một thành viên vô tình cấu hình cho cả Flask và Django cùng khởi chạy ở cổng `8000` hoặc `5000`, hệ điều hành sẽ báo lỗi `OSError: [Errno 98/10048] Address already in use`. Cần quy ước rõ: Flask chạy cổng `5000`, Django chạy cổng `8000`.

---

### 3.4. Rủi ro Thao tác Git khi Tích hợp (Git Integration Risks)

1. **Mất file hoặc xung đột xóa file khi merge:**
   - **TẠI SAO (WHY):** Nhánh `backend-v2` được tạo từ `dss-v2`. Trên nhánh `dss-v2`, các file Flask (`app.py`, `repo.py`, `service.py`, `routes.py`, `schema.py`) hoàn toàn không tồn tại trong lịch sử commit.
   - Nếu bạn thực hiện `git merge backend` trực tiếp vào `backend-v2`, Git có thể rơi vào trạng thái xung đột thư mục hoặc ghi đè không mong muốn đối với các file cùng tên trong `backend/` (như `manage.py`, `core/`, `analytics/`).
   - **Biện pháp:** Không nên merge cả nhánh mù quáng, mà nên dùng lệnh trích xuất có chủ đích:
     ```powershell
     git checkout backend -- backend/app.py backend/repo.py backend/service.py backend/routes.py backend/schema.py
     ```

---

## 4. Kế hoạch Hành động Từng bước (Action Roadmap)

Dưới đây là quy trình từng bước được đề xuất để bạn thực hiện khi bắt tay vào triển khai:

```mermaid
flowchart TD
    Step1["1. Chuẩn bị Cơ sở Dữ liệu<br>- Chạy lại sql/create_tables.sql<br>- Nạp dữ liệu bằng python -m etl.main --load"]
    Step2["2. Đồng bộ Môi trường .env<br>- Khai báo đồng thời DATABASE_URL<br>và các biến POSTGRES_* trong backend/.env"]
    Step3["3. Đưa mã nguồn Flask vào backend-v2<br>- Checkout 5 file từ branch backend<br>- Cài đặt bổ sung thư viện Flask vào venv"]
    Step4["4. Refactor backend/repo.py<br>- Đổi is_late thành delay_days > 0<br>- Join Dim_Seller lấy seller_id thật<br>- Sử dụng total_lead_days"]
    Step5["5. Kiểm thử & Xác nhận<br>- Chạy test suite của Flask<br>- Chạy test suite dss của Django<br>- Kiểm tra Swagger UI tại /swagger-ui"]

    Step1 --> Step2 --> Step3 --> Step4 --> Step5
```

1. **Bước 1: Nạp lại Kho Dữ liệu Chuẩn:**
   - Đảm bảo service PostgreSQL đang hoạt động.
   - Chạy lệnh khởi tạo DDL 5 bảng: `psql -U postgres -d brazillian -f sql/create_tables.sql`.
   - Chạy nạp dữ liệu nguyên tử: `python -m etl.main --load`.
2. **Bước 2: Hoàn thiện File `.env`:**
   - Cập nhật cả `DATABASE_URL` và nhóm `POSTGRES_*` trong `backend/.env` để cả SQLAlchemy và Django ORM cùng trỏ chính xác về database `brazillian`.
3. **Bước 3: Tải mã nguồn Flask sang `backend-v2`:**
   - Lấy 5 file cốt lõi từ nhánh `backend`: `app.py`, `repo.py`, `service.py`, `routes.py`, `schema.py`.
   - Cài đặt lại các thư viện Flask vào virtual environment.
4. **Bước 4: Cập nhật Truy vấn SQL trong `backend/repo.py`:**
   - Thay thế triệt để các vị trí gọi `f.is_late` bằng `f.delay_days > 0`.
   - Nâng cấp câu truy vấn `get_sellers()` bằng liên kết `JOIN dim_seller`.
   - Thay thế phép cộng ba công đoạn bằng `f.total_lead_days`.
   - Thêm bộ lọc `f.seller_prep_time_days >= 0` để loại trừ các đơn hàng có thời gian âm dị biệt.
5. **Bước 5: Kiểm tra và Khởi chạy Song song:**
   - Chạy kiểm thử tự động của Flask (test client) để xác nhận 10 endpoints trả về HTTP 200.
   - Chạy server Flask (`python backend/app.py`) tại cổng 5000, kiểm tra giao diện tài liệu OpenAPI tại `http://localhost:5000/swagger-ui`.
   - Chạy server Django (`python backend/manage.py runserver 8000`) tại cổng 8000, kiểm tra các tab DSS trên giao diện HTML.

---
*Báo cáo được hoàn thành và ghi nhận tại `docs/adopt-backend-report.md`. Đề xuất không thực hiện chỉnh sửa mã nguồn cho đến khi có xác nhận tiếp theo từ bạn.*
