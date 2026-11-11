# API Implementation Report 2: OLAP Query Engine, Dashboard Overview & Login

**Project:** OLIST Logistics Decision Support System (DSS) Backend
**Component:** Flask API (`backend/app.py`, `backend/schema.py`, `backend/routes.py`, `backend/service.py`, `backend/repo.py`)
**Specification source:** `apiOLAP.md` (OLAP Query Builder + BI Dashboard specification)
**Date:** November 2026
**Status:** Implemented and verified against the live `brazillian` PostgreSQL database

---

## 1. Executive Summary

This report documents the second backend phase: adding the OLAP Query Builder APIs, the BI Dashboard overview API, and minimal login/logout endpoints requested by the assignment specification.

Delivered endpoints:

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| GET | `/api/olap/metadata` | Distinct filter values + available month range | Implemented |
| POST | `/api/olap/query` | Dynamic, whitelisted SQL aggregation on the star schema | Implemented |
| GET | `/api/dashboard/overview` | 6 KPI cards + late-rate trend in one response | Implemented |
| POST | `/api/auth/login` | Plain-text credential check + session creation | Implemented |
| POST | `/api/auth/logout` | Clear the login session | Implemented |
| GET | `/api/auth/me` | Inspect current session (small additive helper) | Implemented |

All 5 designated backend files were modified. Two new SQL support scripts were added outside `backend/`; the reason for each is documented in Section 3. No existing endpoint was removed or changed incompatibly.

Verification:
- `flask --app backend/app routes` lists all 16 routes (10 previous + 6 new).
- Existing test suite: **93 passed** (including all 15 Flask backend tests).
- Ad-hoc integration tests against the real database exercised every new endpoint, error case, CORS preflight, and the authentication session lifecycle.

---

## 2. Scope & File Changes

### 2.1 Modified files (allowed set)

| File | What changed |
|---|---|
| `backend/app.py` | Added `SECRET_KEY`/session configuration and manual CORS handling (no new dependency). |
| `backend/schema.py` | Added OLAP metadata/query schemas, overview schemas, login schemas, period parsing/validation helpers, and naming aliases. |
| `backend/routes.py` | Registered the 6 new routes with request/response schemas and Swagger metadata. |
| `backend/service.py` | Added OLAP resolution/formatting, dashboard overview composition, login wrapper; extended `get_late_trend()` with an optional `extend_to_data_range` flag and `late_count` output. |
| `backend/repo.py` | Added SQL whitelists (dimensions/measures/joins), the dynamic aggregation engine, metadata queries, and the `accounts` authentication query. |

### 2.2 New files added outside `backend/` (explicit justification)

| File | Reason |
|---|---|
| `sql/create_indexes.sql` | The specification (PHẦN 4, item 2) explicitly requires B-Tree indexes on `time_id`, `customer_location_id`, `seller_location_id`, and `product_id` of `Fact_Delivery_SLA`. The existing DDL had none. A separate idempotent script avoids editing the ETL-owned `sql/create_tables.sql` and can be re-run safely. |
| `sql/create_accounts.sql` | Task 2 assumes an `accounts` table, but the current `brazillian` database does not contain one. This script provisions the assumed table (`username` primary key, `password`) and one demo account (`admin` / `admin123`). Without it, `/api/auth/login` cannot be demonstrated on the current database. |

Both scripts were applied to the local development database during verification. They are idempotent and safe to re-run.

### 2.3 Files deliberately not modified

- `sql/create_tables.sql`, `etl/**`, DSS Django code (`backend/dss/**`, `backend/core/**`, `backend/config/**`), and the frontend were left untouched.
- The intended-but-unused Django scaffolding inside `backend/` was not used, matching the user's note that it is not part of this backend.

---

## 3. Implemented Endpoints

### 3.1 `GET /api/olap/metadata`

Returns the values needed to populate the frontend's multi-select filters.

**Response (actual, abbreviated):**

```json
{
  "states": ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"],
  "categories": ["agro_industry_and_commerce", "air_conditioning", "art", "...", "watches_gifts"],
  "seller_states": ["AM", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RS", "SC", "SE", "SP"],
  "time_range": {
    "min_month": "2016-09",
    "max_month": "2018-08"
  }
}
```

Implementation details:
- `states` uses distinct customer states reachable from facts (not every row of `Dim_Location`).
- `categories` are distinct categories that actually appear in facts.
- `time_range` is computed from `MIN/MAX(Dim_Time.full_date)` joined to the fact table, so it reflects real data rather than `Dim_Time` rows that no order uses.
- `seller_states` is an additive extension. The specification's sample response does not list it, but the query payload contains a `seller_states` filter, so the frontend needs these values. It does not break clients that ignore unknown fields.

---

### 3.2 `POST /api/olap/query`

Accepts the frontend query configuration and returns a grouped table.

**Request (specification sample):**

```json
{
  "time_mode": "month",
  "from_time": "2017-01",
  "to_time": "2017-03",
  "dimensions": [
    "Dim_Time.month",
    "Dim_Location.state",
    "Dim_Product.category_name_english"
  ],
  "measures": [
    "total_orders",
    "late_rate",
    "avg_transit_days",
    "avg_freight_value"
  ],
  "filters": {
    "customer_states": ["SP", "RJ"],
    "seller_states": [],
    "categories": ["bed_bath_table"]
  }
}
```

**Response (actual):**

```json
{
  "columns": [
    "month",
    "customer_state",
    "category_name_english",
    "total_orders",
    "late_rate",
    "avg_transit_days",
    "avg_freight_value"
  ],
  "data": [
    {
      "month": "2017-01",
      "customer_state": "RJ",
      "category_name_english": "bed_bath_table",
      "total_orders": 11,
      "late_rate": 0.0,
      "avg_transit_days": 12.3,
      "avg_freight_value": 16.34
    },
    {
      "month": "2017-01",
      "customer_state": "SP",
      "category_name_english": "bed_bath_table",
      "total_orders": 16,
      "late_rate": 6.25,
      "avg_transit_days": 7.87,
      "avg_freight_value": 13.87
    }
  ]
}
```

The JSON key order inside each `data` object is alphabetical because Flask's default JSON provider sorts keys. `columns` always defines the intended presentation order; clients should render columns in that order.

#### 3.2.1 SQL-injection protection (specification PHẦN 4, item 1)

The dynamic query engine never interpolates user strings into SQL:

1. Every dimension and measure is a **whitelist key** in `backend/repo.py`:
   - `OLAP_DIMENSIONS`: maps e.g. `"Dim_Location.state"` to the trusted SQL fragment `cust_loc.state` and output alias `customer_state`.
   - `OLAP_TIME_DIMENSIONS`: maps `month` / `quarter` / `year` to trusted `to_char(...)` expressions.
   - `OLAP_MEASURES`: maps e.g. `"late_rate"` to a trusted aggregate expression.
2. Marshmallow field validators reject any key not present in those dictionaries with HTTP 422. Verified: sending `"Dim_Time.month; DROP TABLE x"` returns 422 and lists allowed values.
3. Filter values are **bound parameters** (`cust_loc.state = ANY(:customer_states)`, `p.category_name_english = ANY(:categories)`, date bounds, etc.), never concatenated.
4. `time_mode` is constrained by `validate.OneOf(["month", "quarter", "year"])`.
5. Only whitelisted, developer-written fragments are inserted into `SELECT`, `JOIN`, `GROUP BY`, and `ORDER BY`.

Consequently, the only user data reaching PostgreSQL is through bind parameters.

#### 3.2.2 Dimension whitelist

| Request key | Resulting column | SQL source |
|---|---|---|
| `Dim_Time.month` | `month` | `to_char(t.full_date, 'YYYY-MM')` (granularity controlled by `time_mode`) |
| `Dim_Time.quarter` | `quarter` | `to_char(t.full_date, 'YYYY') || '-Q' || t.quarter` (granularity controlled by `time_mode`) |
| `Dim_Time.year` | `year` | `t.year::text` (granularity controlled by `time_mode`) |
| `Dim_Time.day_of_week` | `day_of_week` | `t.day_of_week` |
| `Dim_Location.state` | `customer_state` | `cust_loc.state` |
| `Dim_Location.city` | `customer_city` | `cust_loc.city` |
| `Dim_Location.location_id` | `customer_location_id` | `cust_loc.location_id` |
| `Dim_Seller.state` | `seller_state` | `s.state` |
| `Dim_Seller.city` | `seller_city` | `s.city` |
| `Dim_Seller.seller_id` | `seller_id` | `s.seller_id` |
| `Dim_Product.category_name_english` | `category_name_english` | `p.category_name_english` |
| `Dim_Product.product_id` | `product_id` | `p.product_id` |
| `Dim_Product.weight_g` | `weight_g` | `p.weight_g` |
| `Dim_Product.volume_cm3` | `volume_cm3` | `p.volume_cm3` |
| `Fact_Delivery_SLA.payment_type` | `payment_type` | `f.payment_type` |

`Dim_Location.*` is treated as the **customer** location because the specification comment says `Dim_Location.state // Bang khách hàng (customer_location_id)`. Seller geography is exposed explicitly through `Dim_Seller.*`.

#### 3.2.3 Measure whitelist

| Request key | Definition | Output |
|---|---|---|
| `total_orders` | `COUNT(f.order_id)` | integer |
| `total_items` | `COUNT(*)` | integer |
| `late_count` | count of rows with `delay_days > 0` | integer |
| `late_rate` | `100 * late_count / total_items` | percentage, 2 decimals |
| `complaint_rate` | `100 * complaint_count / total_items` | percentage, 2 decimals |
| `avg_transit_days` | `AVG(carrier_transit_time_days)` for non-negative values | days, 2 decimals |
| `avg_freight_value` | `AVG(freight_value)` | currency, 2 decimals |
| `total_freight` | `SUM(freight_value)` | currency, 2 decimals |
| `avg_delivery_days` | `AVG(total_lead_days)` | days, 2 decimals |
| `avg_approval_days` | `AVG(approval_time_days)` | days, 2 decimals |
| `avg_prep_days` | `AVG(seller_prep_time_days)` for non-negative values | days, 2 decimals |
| `avg_review_score` | `AVG(review_score)` | score, 2 decimals |

The first four are the specification measures. The rest are additive, cost-free whitelist entries that match metrics already exposed by the older dashboard endpoints and the frontend's OLAP mock.

#### 3.2.4 Time semantics

The specification contains both a top-level `time_mode` (`month`/`quarter`/`year`) and time dimension keys (`Dim_Time.month`). To avoid contradictory requests, the implementation uses this rule:

- Any of `Dim_Time.month`, `Dim_Time.quarter`, or `Dim_Time.year` in `dimensions` means "include the time axis".
- The axis granularity is **authoritative from `time_mode`**.
- Duplicate time keys collapse into a single column.
- `Dim_Time.day_of_week` is an independent dimension and is not affected by `time_mode`.

Examples verified:
- `time_mode="quarter"` + `Dim_Time.quarter` -> `quarter` values such as `"2017-Q1"`.
- `time_mode="year"` + `Dim_Time.month` -> a single `year` column with values such as `"2017"`.
- `time_mode="month"` + all three time keys -> one `month` column only.

Time labels are returned as strings for all three granularities (`"2017-01"`, `"2017-Q1"`, `"2017"`). This keeps the time axis type-stable and matches the specification's sample value `"2017-11"`.

`from_time` / `to_time` accept `YYYY-MM` (as in the specification) and also `YYYY-MM-DD` for convenience. Month-only bounds are inclusive: `from_time="2017-09"` starts at `2017-09-01`, and `to_time="2018-05"` ends at `2018-05-31`.

---

### 3.3 `GET /api/dashboard/overview`

**Query parameters:**

| Name | Required | Description |
|---|---|---|
| `time_mode` | no | `month` (default), `quarter`, or `year` |
| `from` | no | Inclusive lower bound, `YYYY-MM` or `YYYY-MM-DD` |
| `to` | no | Inclusive upper bound, `YYYY-MM` or `YYYY-MM-DD` |
| `customer_state` | no | 2-letter customer state code |
| `seller_state` | no | 2-letter seller state code (additive; the specification only shows `customer_state`) |

The OpenAPI document exposes the parameters exactly as `from` and `to`, using Marshmallow `data_key` while the internal Python field names remain `from_time` / `to_time`.

**Response (actual):**

```json
{
  "time_mode": "month",
  "from_time": "2017-01",
  "to_time": "2017-03",
  "customer_state": "SP",
  "seller_state": null,
  "kpis": {
    "order_count": 2107,
    "delay_rate": 0.0308,
    "complaint_rate": 0.0237,
    "avg_delivery_time": 9.86,
    "avg_freight_cost": 14.99,
    "avg_score": 4.2
  },
  "late_trend": [
    {
      "year": 2017,
      "month": 1,
      "quarter": null,
      "order_count": 351,
      "late_count": 8,
      "delay_rate": 0.0228,
      "avg_delivery_time": 10.33
    }
  ]
}
```

Reasoning:
- The specification only says "return data for 6 KPI cards and a bar-chart trend", without an exact JSON contract. The response is therefore a composition of the two existing, already-tested calculations: `service.get_kpi()` and `service.get_late_trend()`.
- `kpis` contains the same 6 fields as `GET /api/dashboard/kpis`.
- `late_trend` contains one entry per period with continuous gap filling, so the frontend can render a bar chart without post-processing.
- `delay_rate` in both the KPI block and trend uses the **existing project convention** (ratio `0.0308` = 3.08%), matching `GET /api/dashboard/kpis` and `GET /api/analytics/late-trend`. The OLAP endpoint intentionally uses percentages because the specification's `late_rate` sample (`12.5`) is a percentage. This discrepancy is flagged in Section 5.
- `late_count` was added as an additive field to the trend point. It is useful for tooltips and does not break existing consumers.
- When `from`/`to` are provided, the overview trend is clamped to that window. The old `/api/analytics/late-trend` behavior (expanding to the full data range) is preserved by default through the new `extend_to_data_range` argument.

---

### 3.4 Authentication endpoints

The assignment explicitly says authentication does not need to be secure, and assumes an `accounts` table with `username` as primary key and `password`, both strings.

#### `POST /api/auth/login`

Request:

```json
{ "username": "admin", "password": "admin123" }
```

Success (`200`):

```json
{ "message": "Login successful", "username": "admin" }
```

Failure (`401`):

```json
{ "code": 401, "message": "Invalid username or password", "status": "Unauthorized" }
```

Implementation:
- SQL: `SELECT username FROM accounts WHERE username = :username AND password = :password LIMIT 1` (parameterized).
- On success, the username is stored in a Flask session cookie.
- Passwords are compared in plain text on purpose, per the assignment statement.

#### `POST /api/auth/logout`

Always returns `200`:

```json
{ "message": "Logged out" }
```

It removes the username from the session.

#### `GET /api/auth/me` (additive helper)

```json
{ "authenticated": true, "username": "admin" }
```

This is not required by the specification but makes the login/logout lifecycle testable and lets the frontend restore UI state after a page refresh.

#### Session and CORS notes

- `app.py` now sets `SECRET_KEY` from the environment (with a local-development fallback). Flask sessions cannot work without it.
- `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = "Lax"`.
- Manual CORS was implemented in `app.py` without adding `flask-cors` to the dependency list:
  - `OPTIONS` requests return `204` with CORS headers.
  - Responses reflect the request `Origin` and set `Access-Control-Allow-Credentials: true`, so the session cookie works from another localhost port.
  - Allowed methods and headers are declared.
- `file://` pages (origin `null`) cannot reliably persist cookies; serving the frontend over `http://localhost:...` is recommended for the login demo.

---

## 4. Database Support

### 4.1 Indexes

`sql/create_indexes.sql` creates:

- `idx_fact_sla_time_id` on `fact_delivery_sla(time_id)`
- `idx_fact_sla_customer_location_id` on `fact_delivery_sla(customer_location_id)`
- `idx_fact_sla_seller_location_id` on `fact_delivery_sla(seller_location_id)`
- `idx_fact_sla_product_id` on `fact_delivery_sla(product_id)`
- `idx_fact_sla_seller_id` on `fact_delivery_sla(seller_id)` (used by seller joins)
- `idx_dim_location_state`, `idx_dim_seller_state`, `idx_dim_product_category` (filter columns)

All statements use `CREATE INDEX IF NOT EXISTS`, so re-running is safe. The script was applied to the local database and the indexes were confirmed in `pg_indexes`.

### 4.2 Accounts table

`sql/create_accounts.sql` creates:

```sql
CREATE TABLE IF NOT EXISTS accounts (
    username VARCHAR(100) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
);

INSERT INTO accounts (username, password)
VALUES ('admin', 'admin123')
ON CONFLICT (username) DO NOTHING;
```

The demo credential is documented here so the assignment can be demonstrated; it must be changed or removed for any real deployment.

---

## 5. Conflicts, Ambiguities and Decisions

This section lists everything that was unclear or internally inconsistent in the specification, plus the chosen resolution. Items 1-3 are the most important for the teammate/frontend developer.

1. **`total_orders` grain conflicts with the fact-table grain.**
   - The specification defines `total_orders` as `COUNT(order_id)`. `Fact_Delivery_SLA` has grain `(order_id, order_item_id)`, so this counts **order items**, not distinct orders.
   - Decision: followed the specification literally (`COUNT(f.order_id)`), which also matches the existing `/api/dashboard/kpis` convention (`COUNT(*)` item rows).
   - Consequence: a multi-item order contributes multiple rows to `total_orders`. If the frontend wants distinct orders, the measure should be changed to `COUNT(DISTINCT f.order_id)`. This should be agreed with the teammate before the defence.
   - `late_rate` and `complaint_rate` are therefore also item-level rates, consistent with `total_orders`.

2. **`late_rate` unit differs between the OLAP specification and the existing dashboard.**
   - OLAP sample: `"late_rate": 12.5` -> percent (0-100).
   - Existing `/api/dashboard/kpis` and `/api/analytics/late-trend`: `delay_rate` -> ratio (0-1).
   - Decision: OLAP returns percentages as specified; the dashboard overview keeps the existing ratio convention. The field names also differ (`late_rate` vs `delay_rate`) to make the unit difference explicit.
   - Frontend must multiply dashboard rates by 100 if it displays percentages.

3. **`time_mode` vs `Dim_Time.*` is redundant/ambiguous.**
   - The payload contains both a global `time_mode` and explicit time dimensions.
   - Decision: time keys request the time axis; `time_mode` decides its granularity. This prevents contradictory output (e.g. asking for quarter grouping while the dimension says month) and matches the specification sample where both agree.
   - If the teammate intended the explicit dimension to override `time_mode`, this rule must be revisited.

4. **Metadata sample values do not match the database.**
   - Specification sample `time_range` is `2017-09` to `2018-05`, but the actual warehouse contains `2016-09` to `2018-08`.
   - Specification sample lists only 9 states and 5 categories; the database has 27 customer states and 72 categories.
   - Decision: return real data. The sample is clearly illustrative/truncated. The frontend should never hardcode those values.

5. **`GET /api/dashboard/overview` response contract is underspecified.**
   - The specification only describes its purpose. A composite `{ kpis, late_trend }` shape was designed, reusing already-tested services.
   - If the frontend expects a different shape (e.g. flat KPI fields or a `period` label string), the response can be adjusted.

6. **`accounts` table does not exist in the current database.**
   - The task says to "imagine" it exists, but the live database only contains the five warehouse tables.
   - Decision: provision it through `sql/create_accounts.sql` and apply it locally, so login is demonstrable. The repository code assumes the table exists as instructed.

7. **Seller-state source inconsistency (pre-existing data issue).**
   - Existing analytics filter seller state through `Dim_Location` (`seller_location_id`), while seller analytics join `Dim_Seller`.
   - The new OLAP engine uses `Dim_Seller.state` for `Dim_Seller.*` dimensions and `seller_states` filters.
   - There are **633 fact rows** where `Dim_Seller.state` differs from the seller location's state (35 sellers affected). Therefore seller-state-filtered OLAP numbers can differ slightly from seller-state-filtered legacy endpoints. This is a data-quality issue, not an API bug. The teammate should decide which source is canonical.

8. **Negative stage durations.**
   - The migration report documents anomalous negative prep/transit durations.
   - The specification says plain `AVG(carrier_transit_time_days)`. The implementation excludes negative transit and prep values for `avg_transit_days` / `avg_prep_days`, matching the migrated `/api/analytics/sla-breakdown` behavior. `avg_approval_days` is left as a plain average.
   - If raw averages are required, remove the `CASE WHEN >= 0` guard in `repo.OLAP_MEASURES`.

9. **Time axis values are strings.**
   - `month` -> `"2017-11"`, `quarter` -> `"2017-Q4"`, `year` -> `"2017"`.
   - This is consistent with the specification's `"month": "2017-11"` sample. If charts require numeric years/quarters, the frontend must parse them or the SQL expressions must be changed.

10. **`seller_states` was added to `/api/olap/metadata`.**
    - Reason: the OLAP payload supports a `seller_states` filter, so the values must come from somewhere. This is an additive field; strict clients are unaffected.

11. **`avg_*` measures return `0.0` for empty groups.**
    - PostgreSQL returns `NULL` when a group has no non-null values (`AVG`). The service converts `NULL` to `0` / `0.0` to keep the response type-stable, consistent with the existing division-by-zero safeguards.

12. **Indexes are not created automatically at application start.**
    - Decision: keep schema changes explicit in SQL scripts rather than running DDL at import time. The scripts must be executed once per environment (already done locally).

13. **"Dynamic pivot" vs flat grouped rows.**
    - The specification text calls the result a matrix/pivot table, but its request payload has a single `dimensions` list and its sample response is a flat array of rows. There is no `rows` vs `columns` split in the API contract.
    - Decision: return a flat grouped table exactly like the sample. The `columns` array plus the order of `dimensions` gives the frontend everything needed to render a pivot client-side.
    - If the teammate's OLAP component expects the server to split dimensions into row and column axes, the payload must be extended (e.g. `row_dimensions` / `column_dimensions`) and this endpoint revisited.

14. **New endpoints use different parameter names than the legacy endpoints.**
    - New: `time_mode`, `from_time` / `to_time` (OLAP); `from` / `to` (overview).
    - Legacy: `granularity`, `start_date` / `end_date`.
    - Decision: follow the new specification exactly, while reusing the same underlying services. The frontend must not reuse the legacy parameter names for the new endpoints.

15. **Port collision between the two backends (pre-existing).**
    - `backend/.env` sets `BACKEND_PORT=8000`, and the Django DSS backend also defaults to `8000`.
    - The Flask app will therefore collide with Django if both are started with their current defaults. Run them on different ports (e.g. Flask `5000`, Django `8000`) or change `BACKEND_PORT` before the defence.

---

## 6. Verification

### 6.1 Route registration

```powershell
.venv\Scripts\python.exe -m flask --app backend/app routes
```

Result: 16 routes registered, including:

```
api.get_olap_metadata        GET   /api/olap/metadata
api.run_olap_query           POST  /api/olap/query
api.get_dashboard_overview   GET   /api/dashboard/overview
api.login                    POST  /api/auth/login
api.logout                   POST  /api/auth/logout
api.current_user             GET   /api/auth/me
```

### 6.2 Existing regression suite

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Result: **93 passed** in 27.53s (no regressions).

### 6.3 Ad-hoc integration matrix (real database)

| Test | Result |
|---|---|
| `GET /openapi.json` | 200, all 16 paths documented, overview exposes `from`/`to` |
| `GET /api/olap/metadata` | 200, 27 states, 72 categories, range `2016-09`..`2018-08` |
| `POST /api/olap/query` with specification sample shape | 200, correct columns and grouped rows |
| `time_mode=quarter` | 200, `quarter` column `"2017-Q1"` |
| `time_mode=year` + `Dim_Time.month` | 200, single `year` column |
| Duplicate time dimensions | 200, collapsed to one time column |
| All 12 whitelisted measures at once | 200, all columns present |
| All 15 whitelisted dimension keys at once | 200, all columns present |
| SQL injection attempt in `dimensions` | 422, rejected before SQL execution |
| Unknown filter key (`bogus`) | 422 |
| Inverted time range | 422 |
| Invalid month/day (`2017-13`, `2017-02-30`) | 422 |
| `GET /api/dashboard/overview?...` | 200, 6 KPIs + trend |
| Overview without parameters | 200, 24 monthly trend points |
| `POST /api/auth/login` correct credentials | 200, session set |
| `POST /api/auth/login` wrong password | 401 |
| `GET /api/auth/me` after login / logout | `authenticated: true` / `false` |
| CORS preflight (`OPTIONS`, Origin `http://localhost:5500`) | 204 with `Access-Control-Allow-Origin` reflected and credentials allowed |
| CORS on normal response | `Access-Control-Allow-Origin` and `Access-Control-Allow-Credentials: true` present |

### 6.4 Database checks

- `accounts` table created; demo row present.
- Fact indexes confirmed in `pg_indexes`:
  `idx_fact_sla_time_id`, `idx_fact_sla_customer_location_id`, `idx_fact_sla_seller_location_id`, `idx_fact_sla_product_id`, `idx_fact_sla_seller_id`.

---

## 7. How to Run

From the repository root:

```powershell
# 1. One-time: provision the assumed accounts table and performance indexes
.venv\Scripts\python.exe -c "import psycopg2; c=psycopg2.connect('postgresql://postgres:admin@localhost:5432/brazillian'); c.autocommit=True; cur=c.cursor(); cur.execute(open('sql/create_accounts.sql', encoding='utf-8').read()); cur.execute(open('sql/create_indexes.sql', encoding='utf-8').read())"

# 2. Start the Flask API (port from backend/.env, currently 8000)
.venv\Scripts\python.exe -m flask --app backend/app run --debug
```

- API base: `http://127.0.0.1:8000/api`
- Swagger UI: `http://127.0.0.1:8000/swagger-ui`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Demo login: `admin` / `admin123`

Example requests (PowerShell):

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/olap/metadata"
Invoke-RestMethod "http://127.0.0.1:8000/api/dashboard/overview?time_mode=month&from=2017-01&to=2017-03&customer_state=SP"

$body = @{
  time_mode = "month"
  from_time = "2017-01"
  to_time = "2017-03"
  dimensions = @("Dim_Time.month", "Dim_Location.state")
  measures = @("total_orders", "late_rate", "avg_transit_days", "avg_freight_value")
  filters = @{ customer_states = @("SP"); seller_states = @(); categories = @() }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/olap/query" `
  -ContentType "application/json" -Body $body

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/auth/login" `
  -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'
```

---

## 8. Summary of Additive Behaviour on Existing Code

- `service.get_late_trend()` now accepts `extend_to_data_range: bool = True`. Default behavior is unchanged; the overview passes `False` so explicit `from`/`to` bounds are respected.
- `res_LateTrendSchema` / trend points now include `late_count` (additive; existing clients unaffected).
- `app.py` now always adds CORS headers and handles `OPTIONS` preflight.
- No existing route, field, or response field was removed or renamed.
