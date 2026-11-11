# Backend Migration & Adaptation Report (Phase 2)
*(Adopt Backend Report 2: Execution & Verification)*

**Project:** OLIST Logistics Decision Support System (DSS)  
**Branch:** `backend-v2` (migrated from `backend` on top of `dss-v2` DW)  
**Date:** November 2026  
**Status:** Completed & Verified  

---

## 1. Executive Summary

This report documents the completion of the backend migration from branch `backend` to branch `backend-v2`. The codebase has been adapted to the modernized Data Warehouse (DW) structure created in `dss-v2`.

Key accomplishments:
1. **Dependency Synchronization:** Merged dependencies in `requirements.txt`. Where version conflicts occurred (`pandas`, `numpy`, `psycopg2-binary`), the bounds from `backend-v2` were strictly prioritized.
2. **Backend Code Migration:** Transferred and updated the Flask application (`backend/app.py`, `backend/schema.py`, `backend/routes.py`, `backend/service.py`, `backend/repo.py`, `backend/model.py`) into `backend-v2`.
3. **DW Schema Alignment:**
   - Replaced all obsolete `is_late` column usages with `delay_days > 0`.
   - Upgraded seller analytics in `repo.py` to join `Dim_Seller` and expose true seller UUIDs.
   - Replaced multi-stage summation with the precomputed `total_lead_days` metric.
   - Added filters to safeguard against anomalous negative stage durations.
4. **Coexistence & Dual-Backend Compatibility:** Both the Flask API (port 5000) and Django DSS engine (port 8000) can run concurrently without filename, routing, or environment collisions.
5. **Quality Assurance:** Added a 15-case test suite (`tests/test_flask_backend.py`). Full test suite passes completely (**93 passed** in pytest: 78 DSS tests + 15 Flask tests). Django system check reports **0 issues**.

---

## 2. Dependency Synchronization (`requirements.txt`)

### 2.1. Conflict Resolution Summary
Per user instructions, any version conflicts between `backend` (pinned versions) and `backend-v2` (minimum bounds) were resolved in favor of `backend-v2`:

| Package | Branch `backend` | Branch `backend-v2` | Final Synchronized Resolution | Rationale |
|---|---|---|---|---|
| `pandas` | `pandas==3.1.0` | `pandas>=2.0` | **`pandas>=2.0`** | Resolved per conflict rule; compatible with both ETL and DSS scripts |
| `numpy` | `numpy==2.5.4` | `numpy>=1.24` | **`numpy>=1.24`** | Resolved per conflict rule; supports NumPy 1.x & 2.x |
| `psycopg2-binary` | `psycopg2-binary==2.9.13` | `psycopg2-binary>=2.9` | **`psycopg2-binary>=2.9`** | Resolved per conflict rule |

### 2.2. Package Retentions
- **From `backend-v2`:** `django>=5.0`, `django-cors-headers>=4.0`, `pytest>=8.0`.
- **From `backend`:** `Flask==3.1.3`, `flask-smorest==0.47.0`, `Flask-SQLAlchemy==3.1.1`, `flask-marshmallow==1.5.0`, `marshmallow==4.3.1`, `SQLAlchemy==2.1.6`, `webargs==8.7.1`, `apispec==6.10.0`, `APIFlask==3.1.2`, `pydantic==2.14.2`, `python-dotenv==1.2.4`, etc.

The resulting `requirements.txt` was validated against the existing `.venv` environment without dependency errors.

---

## 3. Backend Migration & Code Changes

### 3.1. Architecture & Execution Strategy
The `backend/` directory now cleanly supports both backends:
- **Flask Backend (`backend/app.py`):** Powers the Operational & BI Dashboard (10 endpoints at `http://127.0.0.1:5000/` with interactive OpenAPI docs at `/swagger-ui`).
- **Django Backend (`backend/manage.py`):** Powers the Decision Support System engine (`/api/dss/` at `http://127.0.0.1:8000/`).

Both applications share the same PostgreSQL database (`brazillian`) and process data from the star schema.

---

### 3.2. Detailed Code Modifications

#### 1. `backend/app.py`
- **Dynamic Path Resolution:** Automatically appends both `backend/` and `REPO_ROOT` to `sys.path`. This ensures commands run identically whether executed from the project root (`flask --app backend/app run --debug`) or from inside `backend/` (`python app.py`).
- **Dual Environment Loading:** Reads `backend/.env` first, falling back to root `.env`.
- **Flexible Connection String Fallback:** If `DATABASE_URL` is omitted, `app.py` automatically constructs the PostgreSQL connection URL from individual `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` variables, preventing configuration mismatches between Flask and Django.

#### 2. `backend/schema.py`
- Maintained all request schemas (`req_FilterSchema`, `req_LateTrendSchema`, `req_OrdersQuerySchema`, `req_SellerQuerySchema`, `req_AlertsQuerySchema`) with Marshmallow validation.
- Updated `res_SellerSchema.seller_id` field documentation to reflect that it now returns the genuine seller UUID rather than a zip code prefix proxy.
- Preserved `SafeDateField` to ensure ISO date string serialization compatibility.

#### 3. `backend/routes.py`
- Registered all 10 endpoints under Flask-Smorest Blueprint `api`:
  - `GET /api/health`
  - `GET /api/customer-states`
  - `GET /api/seller-states`
  - `GET /api/dashboard/kpis`
  - `GET /api/analytics/late-trend`
  - `GET /api/analytics/sla-breakdown`
  - `GET /api/orders`
  - `GET /api/analytics/regions`
  - `GET /api/analytics/sellers`
  - `GET /api/alerts`
- Maintained OpenAPI 3.0.2 schema generation at `/openapi.json` and Swagger UI at `/swagger-ui`.

#### 4. `backend/service.py`
- Preserved division-by-zero safeguards and period generation algorithms (`generate_month_periods`, `generate_quarter_periods`).
- Kept response formatting and rounding logic aligned with frontend expectations.

#### 5. `backend/repo.py` (Core Database Adaptations)
All SQL statements were revised to align with the new Data Warehouse schema:

| Function | Old SQL Logic (Old DW) | New SQL Logic (New DW) | Technical Reason |
|---|---|---|---|
| `get_kpi()` | `COUNT(CASE WHEN f.is_late = TRUE ...)` | `COUNT(CASE WHEN f.delay_days > 0 ...)` | `is_late` removed from DDL; `delay_days > 0` represents late delivery. |
| `get_kpi()` | `AVG(f.approval_time_days + f.seller_prep_time_days + f.carrier_transit_time_days)` | `AVG(f.total_lead_days)` | Uses precalculated measure, improving performance. |
| `get_late_trend()` | `COUNT(CASE WHEN f.is_late = TRUE ...)` | `COUNT(CASE WHEN f.delay_days > 0 ...)` | Adapted to continuous delay measure. |
| `get_sla_breakdown()` | Raw `AVG(f.seller_prep_time_days)` | `AVG(CASE WHEN f.seller_prep_time_days >= 0 ...)` | Excludes 1,361 anomalous rows with negative prep time. |
| `get_orders()` | `BOOL_OR(f.is_late) AS is_late` | `BOOL_OR(f.delay_days > 0) AS is_late` | Preserves boolean `is_late` field for API consumers. |
| `get_regions()` | `COUNT(CASE WHEN f.is_late = TRUE ...)` | `COUNT(CASE WHEN f.delay_days > 0 ...)` | Adapted to `delay_days > 0`. |
| `get_sellers()` | Grouped by `f.seller_location_id` (zip prefix) | `JOIN dim_seller s ON f.seller_id = s.seller_id` | Uses new `Dim_Seller` table to track real seller UUIDs. |
| `get_seller_states()` | Joined `dim_location` via `seller_location_id` | `JOIN dim_seller s ON f.seller_id = s.seller_id` | Queries seller states directly via `Dim_Seller`. |
| `get_alerts()` | `WHERE (has_complaint OR is_late)` | `WHERE (has_complaint OR delay_days > 0)` | Filters active alerts using `delay_days > 0`. |

---

## 4. Verification & Testing Results

### 4.1. Command Line Verification

1. **Flask Route Registration Check:**
   ```powershell
   flask --app backend/app routes
   ```
   *Result:* All 13 routes (10 API endpoints + Swagger UI + OpenAPI JSON + Static) registered and recognized.

2. **Flask Health Check:**
   ```powershell
   GET /api/health -> Status 200: {"message": "I love Kasane Teto"}
   ```

3. **OpenAPI Specification Check:**
   ```powershell
   GET /openapi.json -> Status 200: Title "Olist Logistics DSS API", 10 paths documented.
   ```

4. **Django System Integrity Check:**
   ```powershell
   python backend/manage.py check
   ```
   *Result:* `System check identified no issues (0 silenced).`

5. **Unit & Integration Test Suite (`pytest`):**
   ```powershell
   python -m pytest -q
   ```
   *Result:* **93 passed in 27.22s** (78 DSS model/eval tests + 15 Flask backend tests).

---

## 5. Execution Commands Quick Reference

### 5.1. Starting the Flask Backend (Dashboard & Analytics)
From project root:
```powershell
flask --app backend/app run --debug --port 5000
```
Or from `backend/`:
```powershell
cd backend
python app.py
```
- API Base URL: `http://localhost:5000/api`
- Swagger UI Documentation: `http://localhost:5000/swagger-ui`
- OpenAPI JSON Spec: `http://localhost:5000/openapi.json`

### 5.2. Starting the Django Backend (DSS Engine)
From `backend/`:
```powershell
cd backend
python manage.py runserver 8000
```
- DSS API Base URL: `http://localhost:8000/api/dss`

---

## 6. Items Requiring Clarification (What Might Need Discussion with Your Teammate)

To ensure smooth collaboration and prevent future misunderstandings, the following 4 points should be clarified with your teammate:

### 1. Long-Term Architectural Vision: Dual Microservices vs. Single Unified Framework
- **Current State:** The repository now successfully operates as a **dual-service architecture**:
  - Flask (port 5000) handles general BI dashboarding, order drill-through, SLA stages, and operational alerts.
  - Django (port 8000) handles the prescriptive DSS algorithms (`/brief`, `/attribution`, `/scenario`, `/promise-policy`).
- **Question to discuss:** Does your teammate want to keep this separation (e.g. Flask for Dashboard, Django for DSS), or is the goal to eventually port the Flask routes into Django views (for instance, inside `backend/analytics/`) so that only one server needs to run on port 8000?

### 2. Frontend API Targeting in `web/Olist_Logistics_DSS_v3.html`
- **Current State:** In `web/Olist_Logistics_DSS_v3.html`, the code sets:
  ```javascript
  const DSS_API = 'http://localhost:8000/api/dss';
  ```
  The DSS tab calls Django directly, but the Dashboard, OLAP, and ETL Monitor tabs currently render mock data.
- **Question to discuss:** How should the frontend connect to the Dashboard endpoints? Should the HTML file make direct requests to `http://localhost:5000/api/` for the Dashboard tabs, or will there be a reverse proxy / unified gateway?

### 3. Grain Definition Consistency in Dashboard KPIs
- **Current State:** In `Fact_Delivery_SLA`, each row represents one item in an order (`order_id, order_item_id`).
  - In Flask `repo.py`, `get_kpi()` uses `COUNT(*)` (item count: 110,173 items).
  - In Django DSS (`dss_models.py`), the model aggregates items into `(order_id, route)` pairs (95,591 order-routes over 95,082 unique delivered orders).
- **Question to discuss:** Should the Dashboard KPI cards display item-level order counts and delay rates, or distinct order counts (`COUNT(DISTINCT order_id)`)? Aligning this ensures no discrepancy between the numbers shown on the Dashboard and those cited in the DSS report.

### 4. Database Credentials & Environment Variables
- **Current State:**
  - `backend/app.py` (Flask) checks `DATABASE_URL` with automatic fallback to `POSTGRES_*` variables.
  - Django's `backend/config/env.py` expects individual `POSTGRES_*` variables.
  - Root `.env` currently uses `POSTGRES_USER=brazillian_admin` and `POSTGRES_PASSWORD=123456789`, while some local developer environments use `postgres:admin`.
- **Recommendation:** Ensure both members use consistent credentials in `.env` before running defense demos or submissions.
