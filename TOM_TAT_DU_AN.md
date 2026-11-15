# TÓM TẮT DỰ ÁN — Brazillian Olist Logistics DSS

> Cập nhật: 05/11/2026 · Branch `dss` · HEAD `bf1f2f9` · Tag `backup-co-ml`
>
> Tài liệu này tóm tắt toàn bộ dự án ở trạng thái hiện tại: mục tiêu, kiến trúc,
> dữ liệu, DSS luật, API, giao diện, kiểm thử, cách chạy và hạn chế.

---

## 1. Mục tiêu

Đồ án **Data Warehouse & Hệ hỗ trợ quyết định (DSS)** cho bài toán
**logistics / giao hàng đúng hạn**, xây dựng từ bộ dữ liệu
**Olist Brazilian E-commerce**.

Hệ thống hỗ trợ:
- Xếp hạng tuyến vận chuyển có tỷ lệ giao trễ cao.
- Phân tích nguyên nhân gốc theo 3 giai đoạn: duyệt thanh toán → người bán
  chuẩn bị hàng → vận chuyển.
- Mô phỏng What-if khi cắt giảm thời gian từng giai đoạn.
- Đề xuất cam kết giao hàng / mức cắt giảm cần thiết để đạt mục tiêu.
- Ghi nhận hành động thực tế của người dùng.

> **Phần ML dự báo đã được gỡ hoàn toàn.** Dự án hiện chỉ còn DSS dựa trên luật
> và mô phỏng.

---

## 2. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| ETL | Hoàn chỉnh, sinh 5 CSV trong `data/processed/` và nạp được PostgreSQL |
| Data Warehouse | 5 bảng đã tạo và nạp dữ liệu |
| Backend Flask | Một app Flask duy nhất (`backend/dss/`) phục vụ 9 API `/api/dss/*`, 12 API BI/OLAP và 3 API auth trên cổng 8000 |
| DSS rule-based | Có route priority, attribution/Shapley, promise, feasible cut, seller scorecard/portfolio, low-sample, threshold sensitivity và Decision Brief |
| Giao diện DSS | React 19 + Vite 8 trong `frontend/` — 5 endpoint thật (`/api/olap/*`, `/api/dashboard/*`, `/api/analytics/*`); tab DSS còn mock |
| Frontend | Dev qua Vite `:5173` proxy `/api` sang Flask `:8000` (cùng origin, không cần CORS) |
| ML | Đã gỡ: không còn `etl/dss_ml.py`, endpoint `at-risk`, `scikit-learn`, `joblib` |
| Kiểm thử gần nhất | **113 pytest**; golden parity DSS Django → Flask PASS |
| Git | Working tree sạch sau khi hợp nhất frontend + backend về một app Flask |

---

## 3. Kiến trúc tổng thể

```
Olist CSV gốc (9 file)
        │
        ▼
   ETL Python (pandas)
   - làm sạch
   - tính thời gian 3 giai đoạn
   - tính delay_days
        │
        ▼
 PostgreSQL — Star Schema
 Dim_Time / Dim_Location / Dim_Product / Dim_Seller / Fact_Delivery_SLA
        │
        ├──► Flask API (`backend/dss/`, psycopg2)
        │
        └──► DSS Model Base (etl/dss_models.py)
                    │
                    ▼
             Flask API /api/dss/*
                    │
                    ▼
      frontend/ (React 19 + Vite 8)
      (gọi API thật, dev qua proxy :5173 → :8000)
```

---

## 4. Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Data Warehouse | PostgreSQL, Star Schema |
| ETL | Python 3.13, pandas, numpy, psycopg2 |
| Backend | Flask 3 (app factory + Blueprint) |
| API | Flask views, JSON (`/api/dss/*`, `/api/olap/*`, `/api/dashboard/*`, `/api/analytics/*`, `/api/auth/*`) |
| Giao diện DSS | React 19 + Vite 8 + Tailwind (`frontend/`) |
| Truy cập DB | psycopg2, SQL thuần |
| Kiểm thử | pytest (+ golden parity JSON) |

---

## 5. Cấu trúc thư mục

```
Brazillian/
├── .env                      # DATABASE_URL cho ETL (không commit)
├── requirements.txt          # pandas, numpy, Flask, psycopg2, pytest
├── README.md                 # tổng quan, cài đặt, ETL, Star Schema
├── examples/                 # trang demo HTML gọi API DSS
│
├── data/
│   ├── raw/                  # 9 CSV Olist gốc (gitignore)
│   └── processed/            # 5 CSV sau ETL (gitignore)
│
├── etl/
│   ├── config.py             # đường dẫn + cấu hình PostgreSQL
│   ├── main.py               # chạy Transform hoặc Transform + Load
│   ├── dim_time.py
│   ├── dim_location.py
│   ├── dim_product.py
│   ├── fact_delivery_sla.py
│   ├── load_data.py
│   ├── stats_for_report.py
│   ├── dss_models.py         # Model Base DSS rule-based
│   └── dss_eval.py           # backtest, bootstrap, threshold sensitivity
│
├── sql/
│   ├── create_tables.sql     # DDL 5 bảng DW
│   ├── create_accounts.sql   # bảng accounts cho auth
│   └── create_indexes.sql    # index hiệu năng
│
├── backend/
│   ├── wsgi.py               # entry point (flask run / gunicorn / waitress)
│   ├── .env.example          # mẫu cấu hình (copy thành .env)
│   ├── dss/                  # app Flask: api, service, db, bi_*, olap_api, auth_*
│   ├── logs/                 # log theo ngày (untracked)
│   └── env/                  # virtualenv backend (không commit)
│
├── frontend/                 # React 19 + Vite 8 (5 endpoint thật)
├── examples/                 # trang demo HTML gọi API DSS
│
├── tests/
│   ├── conftest.py
│   ├── test_dss_api.py
│   ├── test_dss_models.py
│   ├── test_dss_eval.py
│   ├── test_models.py
│   └── golden/               # golden parity Django → Flask
│
└── reports/
    ├── api_dss.md
    ├── dss_formulas.md
    ├── dss_results.md
    ├── dss_eval_raw.txt
    └── dss_requirements.md
```

---

## 6. Dữ liệu & quy mô

**Nguồn:** 9 file CSV Olist trong `data/raw/` (customers, geolocation, orders,
order_items, payments, reviews, products, sellers, category translation).

**Đầu ra ETL trong `data/processed/`:**

| File | Số dòng | Nội dung |
|---|---:|---|
| `cleaned_dim_time.csv` | 612 | chiều thời gian |
| `cleaned_dim_location.csv` | 15.078 | địa điểm theo zip prefix |
| `cleaned_dim_product.csv` | 32.951 | sản phẩm, category, khối lượng, thể tích |
| `cleaned_fact_orders.csv` | 110.173 | fact ở hạt **order item** |

Fact có hạt **1 dòng = 1 item của đơn hàng**. Một đơn có thể xuất hiện ở nhiều
tuyến nếu người bán ở nhiều bang.

---

## 7. Mô hình dữ liệu — Star Schema

### `Dim_Time`
`time_id` (PK), `full_date`, `month`, `year`, `quarter`, `day_of_week`

### `Dim_Location`
`location_id` (PK), `zip_code_prefix`, `city`, `state`, `latitude`, `longitude`

### `Dim_Product`
`product_id` (PK), `category_name_english`, `weight_g`, `volume_cm3`

### `Fact_Delivery_SLA`
- Khóa chính: `(order_id, order_item_id)`
- Khóa ngoại: `product_id`, `customer_location_id`, `seller_location_id`, `time_id`
- Chiều suy biến: `payment_type`
- Measures:
  - `approval_time_days`
  - `seller_prep_time_days`
  - `carrier_transit_time_days`
  - `freight_value`
  - `review_score`
  - `delay_days`
- Flag: `has_logistics_complaint`

**Tuyến (route)** được suy ra từ `seller_location.state → customer_location.state`,
ví dụ `SP→RJ`.

---

## 8. ETL pipeline

```powershell
# Chỉ transform, sinh CSV
python -m etl.main

# Transform + nạp PostgreSQL
python -m etl.main --load
```

Luồng xử lý:
1. Đọc 9 CSV gốc.
2. Làm sạch và chuẩn hóa thời gian.
3. Tính 3 giai đoạn:
   - `approval_time_days`: từ lúc đặt hàng đến khi duyệt thanh toán.
   - `seller_prep_time_days`: từ duyệt đến khi bàn giao carrier.
   - `carrier_transit_time_days`: từ carrier nhận đến khi giao.
4. Tính `delay_days` so với ngày giao cam kết.
5. Sinh 5 bảng Dim/Fact.
6. `load_data.py` nạp vào PostgreSQL.

---

## 9. DSS rule-based

### 9.1 Model Base — `etl/dss_models.py`

| Hàm | Vai trò |
|---|---|
| `load_orders()` | Đọc Fact + 4 Dim, trả về bảng 1 dòng = 1 đơn-tuyến |
| `wilson_interval(k, n)` | Khoảng tin cậy Wilson 95% cho tỷ lệ trễ; giả định các đơn độc lập, không hiệu chỉnh clustering |
| `route_priority(...)` | Khối 1: xếp hạng tuyến đỏ/vàng |
| `root_cause(o, route)` | Khối 2: tìm giai đoạn nghẽn |
| `scenario(o, route, cut)` | Khối 3: mô phỏng What-if |
| `sensitivity(...)` | Khối 3: độ nhạy khi cắt từng ngày |
| `goal_seek_promise(...)` | Khối 4: số ngày cần kéo dài cam kết |
| `goal_seek_cut(...)` | Khối 4: mức cắt tối thiểu để đạt target |

Hằng số:
- `STAGES = ["approval", "prep", "transit"]`
- `OWNER`: giai đoạn → bộ phận chịu trách nhiệm.
- `RULES`: gợi ý hành động theo giai đoạn.

### 9.2 Bốn khối DSS

**Khối 1 — Route Priority**
- Tính tỷ lệ trễ chung toàn hệ thống `overall`.
- Tuyến **đỏ** nếu `late_rate ≥ 2.0 × overall`.
- Tuyến **vàng** nếu `late_rate ≥ 1.5 × overall`.
- Chỉ xét tuyến có tối thiểu `min_orders = 100`.
- Sắp xếp **red-first**: trả hết tuyến đỏ trước, rồi vàng cho đủ `top`.
- Cờ `low_sample`: mẫu nhỏ.
- Cờ `uncertain`: cận dưới Wilson CI nằm dưới ngưỡng phân loại → nhãn chưa
  được CI xác nhận.

**Khối 2 — Root Cause**
- Tính thời gian trung bình từng giai đoạn toàn hệ thống.
- Tính `excess_s(r) = mean_s(r) − mean_s(all)`.
- Giai đoạn nghẽn là giai đoạn có excess tuyệt đối lớn nhất.
- `has_bottleneck = max(excess) > 0`.
- `excess_ratio` chỉ để tham khảo, **không đổi logic** stage.

**Khối 3 — Scenario / What-if**
- Người dùng chọn mức cắt `approval`, `prep`, `transit`.
- Giả định cắt 1 ngày ở giai đoạn nào thì ngày giao sớm hơn 1 ngày.
- Tính lại `delay_days` và tỷ lệ trễ dự báo.
- Trả về số đơn trễ tránh được và chuỗi độ nhạy 0..5 ngày.

**Khối 4 — Recommendation & Action**
- Goal seek cam kết: kéo dài promise bao nhiêu ngày để tỷ lệ trễ ≤ target
  (mặc định 5%).
- Goal seek cắt giảm: cắt bao nhiêu ngày ở giai đoạn nghẽn để đạt target.
- Nút **Apply** ghi hành động vào `ActionLog`.
- GET trả 50 hành động gần nhất.

### 9.3 Tham số mặc định

| Hàm | Tham số | Mặc định |
|---|---|---|
| `route_priority` | `red` | 2.0 |
| `route_priority` | `amber` | 1.5 |
| `route_priority` | `min_orders` | 100 |
| `route_priority` | `top` | 10 |
| `route_priority` | `ensure_red` | `True` |
| `goal_seek_promise` | `target` | 0.05 |
| `goal_seek_cut` | `target` | 0.05 |
| `goal_seek_cut` | `step` | 0.5 ngày |
| `goal_seek_cut` | `max_days` | 10 |
| `sensitivity` | `max_days` | 5 |
| `backtest` | `min_orders` | 30 (chỉ đánh giá) |
| `backtest` | `min_period_orders` | 500 |
| `backtest` | `start_year` | 2017 |

---

## 10. Kết quả đã kiểm chứng

### Số liệu chính
- Tỷ lệ trễ: **8,1556% theo đơn-tuyến** và **8,1950% theo đơn duy nhất** trên
  95.082 đơn duy nhất.
- Raw eval ghi nhận 110.173 dòng cấp item; 96.981 đơn-tuyến trước lọc và
  95.591 sau khi loại 1.390 đơn-tuyến có thời gian âm.
- Tại `min_orders=100`, `red=2,0`, `amber=1,5`: **14 tuyến** gắn cờ (6 đỏ,
  8 vàng). Đây là một cấu hình vận hành, không phải con số bất biến.
- Fact `Fact_Delivery_SLA` có 21 cột theo DDL; DW có 5 bảng và ETL sinh 5 CSV.

### Backtest
- Chạy theo kỳ, `min_orders = 30`; **16/19 kỳ** nhóm gắn cờ có tỷ lệ trễ kỳ
  sau cao hơn nhóm còn lại.
- `weighted_diff`: **+8,2826 pp**; `mean_diff`: **+7,2403 pp**;
  `weighted_diff_flagged`: **+10,4624 pp**.
- Đây là tương quan hồi cứu, không chứng minh tác động của can thiệp.

### Bootstrap CI
- So với 0: **[+3,77; +12,55] pp**.
- So với baseline `prior`: **[+0,52; +5,92] pp**.
- So với baseline `through`: **[−0,50; +2,52] pp**, chứa 0 nên **chưa đủ bằng
  chứng** DSS tốt hơn through.

### Threshold sensitivity
Ở `min_orders=100`, năm cặp ngưỡng quanh mặc định làm số tuyến gắn cờ dao động
10–21; bộ 100/2,5/2,0 giữ lõi 6 tuyến. Toàn lưới cho kết quả 4–30. Xem
`reports/dss_eval_raw.txt` để biết từng cấu hình.

---

## 11. API DSS — 9 endpoint

Base URL: `http://127.0.0.1:8000/api/dss/`

| Method | Endpoint | Tham số chính | Trả về |
|---|---|---|---|
| GET | `/routes` | `year`, `top` | danh sách tuyến đỏ/vàng + root cause |
| GET | `/scenario` | `route`, `year`, `approval`, `prep`, `transit` | tỷ lệ trễ dự báo, bottleneck, chuỗi sensitivity |
| GET | `/promise` | `route`, `year`, `target` | số ngày cần kéo dài cam kết |
| GET/POST | `/actions` | POST: `action`, `route`, `level`, `detail` | ghi log / trả 50 hành động gần nhất |
| GET | `/brief` | tham số lọc theo API | Decision Brief gồm nhóm hành động và GMV |
| GET | `/attribution` | `q=0.25` hoặc `q=0.5` | Phân rã Shapley theo peer benchmark; q=0.75 trả 400 |
| GET | `/promise-policy` | mức phục vụ 85/90/95% | Bảng calibration, không phải khuyến nghị đặt promise |
| GET | `/sellers` | tham số lọc seller | Seller scorecard |
| GET | `/portfolio` | `k` | Portfolio seller; `k=102` bao phủ 50,10% đơn trễ |

Đặc điểm kỹ thuật:
- Mỗi request mở connection psycopg2 riêng, đóng ngay sau khi trả kết quả.
- `year` rỗng hoặc `all` = toàn bộ dữ liệu.
- NaN/Infinity được chuyển thành `null` để JSON hợp lệ.
- `/actions` không yêu cầu CSRF (session auth dùng cookie `HttpOnly`).
- Lỗi tham số trả JSON `{"error": "..."}` với HTTP 400.

---

## 12. Giao diện

Giao diện chính: `frontend/` (React 19 + Vite 8 + Tailwind).

| Tab / vùng | Trạng thái dữ liệu |
|---|---|
| **Dashboard (BI)** | **Gọi API thật** `GET /api/dashboard/overview` |
| **OLAP** | **Gọi API thật** `GET /api/olap/metadata`, `POST /api/olap/query` |
| **Analytics** | **Gọi API thật** `GET /api/analytics/sla-breakdown`, `GET /api/analytics/regions` |
| **DSS Action Center** | Dữ liệu mẫu (mock) — 4 khối Route Priority, Root Cause, Scenario / What-if, Recommendation & Action |

Tab DSS hiện chưa nối `/api/dss/*`; các endpoint đó vẫn chạy và có golden parity
với bản Django cũ.

Dev: Vite chạy `:5173` và proxy `/api` sang Flask `:8000`
(`frontend/vite.config.js`), nên trình duyệt chỉ thấy một origin, không cần CORS.

---

## 13. Kiểm thử

| Bộ test | Số lượng | Lệnh |
|---|---:|---|
| pytest toàn repo | **113 passed** | `python -m pytest -q` |
| Golden parity DSS | **PASS** (Django → Flask) | `python tests/golden_compare.py` |
| Regen eval | **pass** | `.\scripts\check.ps1` |

File test:
- `tests/test_dss_models.py` — test Model Base, ngưỡng, Wilson, uncertain,
  scenario, goal seek.
- `tests/test_dss_eval.py` — test backtest, bootstrap, threshold sensitivity.
- `tests/test_models.py` — test model DW.
- `tests/test_dss_api.py` — 9 endpoint DSS.
- `tests/test_bi_api.py`, `tests/test_olap_api.py`, `tests/test_auth_api.py` —
  BI/OLAP/auth (port từ backend Flask cũ).
- `tests/golden/` — snapshot parity DSS.

---

## 14. Cách chạy

### 1) Tạo database và bảng DW

```powershell
psql -U postgres -c "CREATE USER brazillian_admin WITH PASSWORD '...';"
psql -U postgres -c "CREATE DATABASE ""Brazillian"" OWNER brazillian_admin;"
psql -U brazillian_admin -d Brazillian -f sql\create_tables.sql
```

### 2) Cài Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Có thể dùng chung `backend\env`.

### 3) Cấu hình

- `.env` ở thư mục gốc: `DATABASE_URL` cho ETL.
- `backend\.env`: copy từ `backend\.env.example`, điền `SECRET_KEY` và thông tin PostgreSQL.

Không commit các file này.

### 4) Chạy ETL

```powershell
python -m etl.main          # chỉ transform
python -m etl.main --load   # transform + nạp DB
```

### 5) Chạy backend

```powershell
cd backend
$env:FLASK_APP = "wsgi"
flask run --host 127.0.0.1 --port 8000
```

Backend: `http://127.0.0.1:8000/`; kiểm tra `GET /api/health`.

### 6) Chạy giao diện

```powershell
cd frontend
npm install
npm run dev
```

`http://localhost:5173/` — Vite proxy `/api` sang Flask `:8000`
(không cần CORS).

### 7) Chạy test

```powershell
python -m pytest -q
python tests/golden_compare.py
```

---

## 15. Tài liệu trong dự án

| File | Nội dung |
|---|---|
| `README.md` | Tổng quan, cài đặt, ETL, Star Schema, chạy Flask + Vite |
| `reports/dss_formulas.md` | Công thức và giả định toàn bộ hàm DSS |
| `reports/dss_results.md` | Kết quả test, backtest, threshold, 14 tuyến, bootstrap, hạn chế |
| `reports/api_dss.md` | Tài liệu chi tiết 9 endpoint DSS |
| `reports/dss_eval_raw.txt` | Output thô của đánh giá |

---

## 16. Git & thay đổi gần nhất

- Branch theo phạm vi công việc: `dss-v2`.
- Các thay đổi Phase 1/2 được kiểm tra bằng `reports/CHECK_OUTPUT.txt`; không
  tạo commit trong lượt cập nhật tài liệu này.

Các thay đổi chưa commit sau khi gỡ ML:

```
 M DSS_HUONG_DAN.md
 M PROMPT_AI_TIEP_TUC.md
 M README.md
 M STATE.md
 M backend/dss/tests.py
 M backend/dss/urls.py
 M backend/dss/views.py
 D data/models/late_risk.joblib
 D data/models/late_risk_metrics.json
 D etl/dss_ml.py
 M reports/dss_formulas.md
 M reports/dss_results.md
 M reports/run_guide.md
 M requirements.txt
 D tests/test_dss_ml.py
 M tests/test_dss_models.py
 M web/Olist_Logistics_DSS_v3.html
?? backend/logs/2026-11-05/
```

`backend/logs/2026-11-05/` là thư mục log có sẵn, không thuộc tác vụ gỡ ML.

Kiểm tra không còn dấu vết ML:

```powershell
git grep -n -i -E "at-risk|at_risk|risk_score|dss_ml|late_risk|joblib|sklearn|scikit"
```

Kết quả: **0 dòng khớp**.

---

## 17. Hạn chế & việc còn lại

### Hạn chế mô hình
- DSS dựa trên **luật và tương quan**, không phải suy luận nhân quả.
- Giả định cắt giảm thời gian **1:1** sang ngày giao — thực tế có thể không
  tuyến tính.
- `uncertain` và `low_sample` chỉ là cờ cảnh báo, không đổi nhãn hay thứ hạng.
- `excess_ratio` chỉ tham khảo; stage vẫn theo excess tuyệt đối.
- Backtest là đánh giá hồi cứu theo tháng, không phải thử nghiệm can thiệp.
- Bootstrap so với baseline `through` có CI chứa 0 → **chưa chứng minh được cải
  thiện** so với baseline này.

### Việc còn lại
- Tab DSS trong `frontend/` vẫn dùng dữ liệu mẫu; 9 endpoint `/api/dss/*` đã
  chạy nhưng chưa nối vào UI.
- Các tab đang gọi API thật: Dashboard, OLAP, Analytics (5 endpoint).

---

## Tóm tắt một câu

Đây là đồ án **Data Warehouse + DSS logistics** ở tầng dữ liệu, ETL, backend API
và mô hình ra quyết định dựa trên luật; backend đã hợp nhất về **một app Flask
duy nhất (cổng 8000)**, frontend React 19 + Vite 8 gọi 5 API thật, riêng tab DSS
còn mock. Toàn bộ phần ML đã được gỡ; check gần nhất có **113 pytest** và golden
parity DSS Django → Flask **PASS**.
