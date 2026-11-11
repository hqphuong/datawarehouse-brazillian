# API Implementation Report: OLIST Logistics DSS Backend

**Project:** OLIST Logistics Decision Support System (DSS) Backend  
**Tech Stack:** Python 3, Flask, flask_smorest, Marshmallow, SQLAlchemy, PostgreSQL  
**Date:** November 2026  

---

## 1. Executive Summary

This report documents the design, implementation, and verification of the backend RESTful API endpoints for the OLIST Logistics Decision Support System (DSS).

All requested API endpoints from STT 1 to STT 7 (along with full enhancement of the existing KPI endpoint) have been implemented adhering strictly to the project architecture, separation of concerns across the 5 designated files in `./backend`, Marshmallow validation, and OpenAPI 3.0.2 Swagger auto-generation.

---

## 2. Scope & File Constraints

As requested, **only the 5 designated backend files were modified**:
1. [`backend/app.py`](file:///e:/Study/HK261/Data_warehouse/Assignment/datawarehouse-brazillian/backend/app.py): Global application configuration, database connection, logger initialization, and Swagger UI / OpenAPI setup.
2. [`backend/schema.py`](file:///e:/Study/HK261/Data_warehouse/Assignment/datawarehouse-brazillian/backend/schema.py): Input (request) and output (response) schemas with validation and Swagger documentation.
3. [`backend/routes.py`](file:///e:/Study/HK261/Data_warehouse/Assignment/datawarehouse-brazillian/backend/routes.py): Flask-smorest Blueprint route definitions, decorators (`@blp.arguments`, `@blp.response`, `@blp.alt_response`), and request dispatching.
4. [`backend/service.py`](file:///e:/Study/HK261/Data_warehouse/Assignment/datawarehouse-brazillian/backend/service.py): Business logic layer handling data transformation, zero-division safeguards, aggregation calculations, and period formatting.
5. [`backend/repo.py`](file:///e:/Study/HK261/Data_warehouse/Assignment/datawarehouse-brazillian/backend/repo.py): Database access layer with SQL queries using SQLAlchemy `text()`, parameterized execution, and a reusable global filter component.

No external files outside `backend/` were altered.

---

## 3. Implemented API Endpoints Summary

| STT | Method | Endpoint | Description | Request Schema | Response Schema | Status Codes |
|---|---|---|---|---|---|---|
| - | GET | `/api/health` | Service health check | None | `res_HealthSchema` | 200 |
| - | GET | `/api/dashboard/kpis` | Core operational KPIs | `req_FilterSchema` | `res_KpiSchema` | 200, 422, 500 |
| 1a | GET | `/api/customer-states` | Distinct customer states | None | `res_StatesSchema` | 200, 500 |
| 1b | GET | `/api/seller-states` | Distinct seller states | None | `res_StatesSchema` | 200, 500 |
| 2 | GET | `/api/analytics/late-trend` | Delivery delay trends over time | `req_LateTrendSchema` | `res_LateTrendSchema` (`many=True`) | 200, 422, 500 |
| 3 | GET | `/api/analytics/sla-breakdown` | Stage-by-stage SLA time breakdown | `req_FilterSchema` | `res_SlaBreakdownSchema` | 200, 422, 500 |
| 4 | GET | `/api/orders` | Drill-through order list with search & pagination | `req_OrdersQuerySchema` | `res_OrdersSchema` | 200, 422, 500 |
| 5 | GET | `/api/analytics/regions` | Seller-to-customer state route pair metrics | `req_FilterSchema` | `res_RegionSchema` (`many=True`) | 200, 422, 500 |
| 6 | GET | `/api/analytics/sellers` | Seller logistics performance metrics | `req_SellerQuerySchema` | `res_SellerSchema` (`many=True`) | 200, 422, 500 |
| 7 | GET | `/api/alerts` | Operational alerts on delays and complaints | `req_AlertsQuerySchema` | `res_AlertSchema` (`many=True`) | 200, 422, 500 |

---

## 4. Architectural Details & Endpoint Specifications

### 4.1. Global Filter Mechanism
A centralized query schema `req_FilterSchema` and repository helper `build_filter_conditions()` were implemented:
- **Query Parameters:**
  - `customer_state` (string, optional): 2-letter customer state (e.g., `SP`, `RJ`).
  - `seller_state` (string, optional): 2-letter seller state (e.g., `SP`, `PR`).
  - `start_date` (ISO date `YYYY-MM-DD`, optional): Filters order purchase date `>= start_date`.
  - `end_date` (ISO date `YYYY-MM-DD`, optional): Filters order purchase date `<= end_date`.
- **Validation:**
  - Validates ISO-8601 date formatting.
  - Implements a schema-level validator ensuring `start_date <= end_date` (raises HTTP 422 if inverted).
- **Application:** Applied uniformly across `/api/dashboard/kpis`, `/api/analytics/late-trend`, `/api/analytics/sla-breakdown`, `/api/orders`, `/api/analytics/regions`, `/api/analytics/sellers`, and `/api/alerts`.

### 4.2. Schema Naming Convention
To align with the author's existing conventions (`res_HealthSchema`, `res_KpiSchema`) while respecting the instruction regarding `req_` and `res_`:
- Input schemas are prefixed with `req_` (e.g., `req_FilterSchema`, `req_LateTrendSchema`, `req_OrdersQuerySchema`).
- Output schemas are prefixed with `res_` (e.g., `res_StatesSchema`, `res_LateTrendSchema`, `res_OrdersSchema`).
- Backward-compatible aliases using `_req_` and `_res_` (e.g., `Filter_req_Schema`, `Orders_res_Schema`) were defined in `backend/schema.py` to prevent any import breakage regardless of client naming expectations.

### 4.3. Detailed Endpoint Breakdown

#### 1. `GET /api/customer-states` & `GET /api/seller-states`
- **Purpose:** Return distinct 2-letter state codes populated in the data warehouse.
- **Response Structure:**
  ```json
  {
    "states": ["AC", "AL", "AM", "BA", "CE", "DF", "ES", "GO", "MG", "SP", "..."]
  }
  ```
- **Rationale for object wrapper:** `flask_smorest` requires a Marshmallow `Schema` class rather than a naked `fields.List` to generate valid Swagger schemas and prevent `AttributeError: 'List' object has no attribute 'dump'`.

#### 2. `GET /api/analytics/late-trend`
- **Parameters:** Global filters + `granularity` (`month`, `quarter`, or `year`; default: `month`).
- **Response:** Array of trend objects:
  ```json
  [
    {
      "avg_delivery_time": 19.58,
      "delay_rate": 0.0096,
      "month": 10,
      "order_count": 313,
      "quarter": null,
      "year": 2016
    },
    {
      "avg_delivery_time": 0.0,
      "delay_rate": 0.0,
      "month": 11,
      "order_count": 0,
      "quarter": null,
      "year": 2016
    },
    {
      "avg_delivery_time": 4.69,
      "delay_rate": 0.0,
      "month": 12,
      "order_count": 1,
      "quarter": null,
      "year": 2016
    }
  ]
  ```
- **Business Logic & Continuous Timeline:**
  - Aggregates by `(year, month)`, `(year, quarter)`, or `(year)` in PostgreSQL.
  - Generates a continuous chronological sequence of periods (months, quarters, or years) spanning the full time range (between `start_date` and `end_date`, or between min and max periods in the dataset).
  - Automatically fills periods having no orders with `order_count: 0`, `delay_rate: 0.0`, and `avg_delivery_time: 0.0`.
  - Removed redundant `period` string field in favor of `year`, `month`, and `quarter`.

#### 3. `GET /api/analytics/sla-breakdown`
- **Parameters:** Global filters.
- **Response:**
  ```json
  {
    "avg_approval_time": 0.52,
    "avg_prep_time": 2.14,
    "avg_transit_time": 8.79,
    "avg_delivery_time": 11.45
  }
  ```
- **Business Logic:** Calculates the average approval duration, seller preparation duration, and carrier transit duration in days from `Fact_Delivery_SLA`.

#### 4. `GET /api/orders` (Order Drill-Through)
- **Parameters:** Global filters + `search` (order ID substring), `page` (min: 1, default: 1), `page_size` (min: 1, max: 100, default: 20).
- **Response:**
  ```json
  {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "orders": [
      {
        "order_id": "e481f51cbdc54678b7cc49136f2d6af7",
        "order_date": "2017-10-02",
        "customer_state": "SP",
        "seller_state": "SP",
        "approval_time_days": 0.01,
        "seller_prep_time_days": 2.37,
        "carrier_transit_time_days": 6.06,
        "total_delivery_time_days": 8.44,
        "review_score": 4,
        "is_late": false,
        "sla_status": "on_time"
      }
    ]
  }
  ```
- **Business Logic:** Groups items by `order_id` to provide unique order-level records, paginates via SQL `LIMIT` / `OFFSET`, and computes the total count. Includes `SafeDateField` to serialize dates safely.

#### 5. `GET /api/analytics/regions`
- **Parameters:** Global filters.
- **Response:** Array of region route pairs:
  ```json
  [
    {
      "seller_state": "SP",
      "customer_state": "RJ",
      "route": "SP -> RJ",
      "order_count": 4200,
      "late_count": 315,
      "late_rate": 0.075,
      "avg_delivery_time": 8.24
    }
  ]
  ```
- **Business Logic:** Groups by `(sell_loc.state, cust_loc.state)` where states are non-null, ordered by order volume and delivery duration.

#### 6. `GET /api/analytics/sellers`
- **Parameters:** Global filters + `limit` (default: 50, max: 500) + `sort_by` (`total_orders`, `avg_prep_time`, `avg_score`).
- **Response:**
  ```json
  [
    {
      "seller_id": "01037",
      "seller_city": "sao paulo",
      "seller_state": "SP",
      "total_orders": 240,
      "avg_prep_time": 1.82,
      "avg_score": 4.31
    }
  ]
  ```
- **Special Implementation Note:** See Section 6 for how `seller_location_id` was mapped as the seller identifier proxy.

#### 7. `GET /api/alerts`
- **Parameters:** Global filters + `limit` (default: 50) + `severity` (`ALL`, `CRITICAL`, `WARNING`, `INFO`).
- **Response:**
  ```json
  [
    {
      "id": "alert-e481f51c",
      "type": "LOGISTICS_COMPLAINT",
      "severity": "CRITICAL",
      "title": "Logistics Complaint: Order e481f51c",
      "message": "Customer lodged a logistics complaint for order e481f51c. Review score: 1.",
      "order_id": "e481f51cbdc54678b7cc49136f2d6af7",
      "order_date": "2017-10-02",
      "customer_state": "SP",
      "seller_state": "RJ",
      "metric_value": 1.0
    }
  ]
  ```

---

## 5. What Was Done vs. What Was Not Done

### 5.1. What Was Done
1. **Implemented All 7 Core APIs:**
   - Implemented `GET /api/customer-states` and `GET /api/seller-states`.
   - Implemented `GET /api/analytics/late-trend` with month/quarter/year granularity.
   - Implemented `GET /api/analytics/sla-breakdown`.
   - Implemented `GET /api/orders` with pagination and order ID search.
   - Implemented `GET /api/analytics/regions` with route pair metrics.
   - Implemented `GET /api/analytics/sellers` with order volume, prep time, and score.
   - Implemented `GET /api/alerts` for operational logistics decision support.
2. **Enhanced Existing KPI Endpoint:** Added query parameter filter support (`req_FilterSchema`) to `GET /api/dashboard/kpis` while retaining backward compatibility for parameterless requests.
3. **Robust Input/Output Validation:**
   - Schema validation via Marshmallow for all query arguments.
   - Reusable `SafeDateField` handling `datetime.date`, `datetime.datetime`, and ISO strings.
   - Safe division logic preventing `ZeroDivisionError` when filters yield 0 orders.
4. **OpenAPI / Swagger Documentation:** Verified that all routes and schemas appear properly at `/openapi.json` and `/swagger-ui`.
5. **Automated Testing Suite:** Created and passed a 29-case unit test suite verifying schemas, services, route integration, and repository parameter binding.

### 5.2. What Was Not Done & Rationale
1. **Did Not Modify Database Schema (`sql/create_tables.sql`):**
   - *Reason:* The project instructions requested restricting changes to the 5 backend files (`app.py`, `schema.py`, `routes.py`, `service.py`, `repo.py`). Modifying DDL or creating new database tables would require re-running migrations or database recreation.
2. **Did Not Add `Dim_Seller` or alter `Fact_Delivery_SLA` columns:**
   - *Reason:* The fact table in the DW schema stores `seller_location_id` (the seller's zip prefix) but dropped `seller_id` during the ETL stage. Therefore, seller analytics were built by grouping on `seller_location_id` as a location proxy.
3. **Did Not Modify Frontend Files:**
   - *Reason:* The frontend in `./frontend` is a baseline Vite starter project; frontend integration was outside the backend task scope.

---

## 6. Technical Observations & Potential Pitfalls

### 6.1. Lack of `seller_id` in Data Warehouse Schema
- **Issue:** In `sql/create_tables.sql` and `etl/fact_delivery_sla.py`:
  ```python
  fact_df = fact_df.merge(df_sellers[["seller_id", "seller_zip_code_prefix"]], on="seller_id", how="left")
  fact_df = fact_df.rename(columns={"seller_zip_code_prefix": "seller_location_id"})
  # seller_id was NOT retained in fact_cols
  ```
  The table `Fact_Delivery_SLA` only has `seller_location_id` (foreign key to `Dim_Location`), not individual seller UUIDs.
- **Solution implemented:** In `/api/analytics/sellers`, the query groups by `f.seller_location_id` and surfaces it as `seller_id`, accompanied by the seller city and state.
- **Recommendation for future iterations:** If the enterprise requires tracking individual sellers by UUID, add a `Dim_Seller` dimension table or include `seller_id VARCHAR(50)` directly in `Fact_Delivery_SLA` and update `etl/fact_delivery_sla.py`.

### 6.2. Underspecified `/api/alerts` Specification
- **Issue:** The API list included STT 7 `GET /api/alerts`, but no detailed specification was provided in the "API details" section of the prompt.
- **Solution implemented:** Designed an intelligent operational alert generator based on existing fact table metrics (`is_late`, `has_logistics_complaint`, `carrier_transit_time_days`, `review_score`). It surfaces high-priority delivery anomalies (logistics complaints, severe carrier transit delays) prioritized by severity (`CRITICAL`, `WARNING`, `INFO`).

### 6.3. Marshmallow `fields.Date` Serialization with String Values
- **Issue:** Marshmallow's default `fields.Date` expects a `datetime.date` object on serialization (`dump()`). If a database driver or mock passes a pre-formatted string (e.g. `'2017-10-02'`), it raises `TypeError: descriptor 'isoformat' for 'datetime.date' objects doesn't apply to a 'str' object`.
- **Solution implemented:** Created `SafeDateField`, which safely accepts both `datetime.date`/`datetime.datetime` and string representations.

### 6.4. Division-by-Zero Protection
- **Issue:** When specific global filter combinations (such as an uncommon state pair or tight date window) return 0 matching rows, calculating rates (`delay_count / order_count`) would cause `ZeroDivisionError` and `avg` functions return `None`.
- **Solution implemented:** Guard clauses in `service.py` return `0.0` whenever `order_count == 0` or metrics are `None`.

---

## 7. Verification Results

All endpoints were tested via `unittest` and Flask test client:
- **Test execution command:** `python scratch/test_endpoints.py`
- **Total tests run:** 29
- **Passing tests:** 29 (100% pass rate)
- **OpenAPI Schema Check:** Verified with `GET /openapi.json` (Status 200, valid OpenAPI 3.0.2 document containing all 10 endpoint paths).

