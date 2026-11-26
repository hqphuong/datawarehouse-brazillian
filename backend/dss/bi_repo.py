"""SQL access for the BI/OLAP/auth API (ported from the team's repo.py).

Uses the shared psycopg2 helpers in :mod:`dss.db`; there is no second database
connection or ORM.  All dynamic SQL fragments come from the whitelists below,
user values are always bound parameters.
"""

from __future__ import annotations

from . import db

# ============================================================================
# OLAP whitelists
# ============================================================================
# SECURITY: every SQL fragment that reaches the dynamic query engine is taken
# from these dictionaries. User supplied strings are only used as dictionary
# keys, never interpolated into SQL. Filter values are bound parameters.
# ============================================================================

# Dimensions that refer to the time axis. Their actual granularity is driven by
# the request's `time_mode`, so `Dim_Time.month` + time_mode="quarter" produces
# a quarter axis.
OLAP_TIME_DIMENSION_KEYS = (
    "Dim_Time.month",
    "Dim_Time.quarter",
    "Dim_Time.year",
)

OLAP_TIME_DIMENSIONS = {
    "month": {
        "expr": "to_char(t.full_date, 'YYYY-MM')",
        "alias": "month",
        "requires": {"time"},
    },
    "quarter": {
        "expr": "to_char(t.full_date, 'YYYY') || '-Q' || t.quarter::text",
        "alias": "quarter",
        "requires": {"time"},
    },
    "year": {
        "expr": "t.year::text",
        "alias": "year",
        "requires": {"time"},
    },
}

OLAP_DIMENSIONS = {
    "Dim_Time.day_of_week": {
        "expr": "t.day_of_week",
        "alias": "day_of_week",
        "requires": {"time"},
    },
    "Dim_Location.state": {
        "expr": "cust_loc.state",
        "alias": "customer_state",
        "requires": {"customer"},
    },
    "Dim_Location.city": {
        "expr": "cust_loc.city",
        "alias": "customer_city",
        "requires": {"customer"},
    },
    "Dim_Location.location_id": {
        "expr": "cust_loc.location_id",
        "alias": "customer_location_id",
        "requires": {"customer"},
    },
    "Dim_Seller.state": {
        "expr": "s.state",
        "alias": "seller_state",
        "requires": {"seller"},
    },
    "Dim_Seller.city": {
        "expr": "s.city",
        "alias": "seller_city",
        "requires": {"seller"},
    },
    "Dim_Seller.seller_id": {
        "expr": "s.seller_id",
        "alias": "seller_id",
        "requires": {"seller"},
    },
    "Dim_Product.category_name_english": {
        "expr": "p.category_name_english",
        "alias": "category_name_english",
        "requires": {"product"},
    },
    "Dim_Product.product_id": {
        "expr": "p.product_id",
        "alias": "product_id",
        "requires": {"product"},
    },
    "Dim_Product.weight_g": {
        "expr": "p.weight_g",
        "alias": "weight_g",
        "requires": {"product"},
    },
    "Dim_Product.volume_cm3": {
        "expr": "p.volume_cm3",
        "alias": "volume_cm3",
        "requires": {"product"},
    },
    "Fact_Delivery_SLA.payment_type": {
        "expr": "f.payment_type",
        "alias": "payment_type",
        "requires": set(),
    },
}

OLAP_MEASURES = {
    "total_orders": {
        "expr": "COUNT(f.order_id)",
        "alias": "total_orders",
        "decimals": 0,
    },
    "total_items": {
        "expr": "COUNT(*)",
        "alias": "total_items",
        "decimals": 0,
    },
    "late_count": {
        "expr": "COUNT(CASE WHEN f.delay_days > 0 THEN 1 END)",
        "alias": "late_count",
        "decimals": 0,
    },
    "late_rate": {
        # Percentage (0-100), not a ratio.
        "expr": (
            "(100.0 * COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) "
            "/ NULLIF(COUNT(*), 0))::double precision"
        ),
        "alias": "late_rate",
        "decimals": 2,
    },
    "complaint_rate": {
        "expr": (
            "(100.0 * COUNT(CASE WHEN f.has_logistics_complaint = TRUE THEN 1 END) "
            "/ NULLIF(COUNT(*), 0))::double precision"
        ),
        "alias": "complaint_rate",
        "decimals": 2,
    },
    "avg_transit_days": {
        # Negative transit durations are anomalous (see backend migration report).
        "expr": (
            "AVG(CASE WHEN f.carrier_transit_time_days >= 0 "
            "THEN f.carrier_transit_time_days END)"
        ),
        "alias": "avg_transit_days",
        "decimals": 2,
    },
    "avg_freight_value": {
        "expr": "AVG(f.freight_value)",
        "alias": "avg_freight_value",
        "decimals": 2,
    },
    "total_freight": {
        "expr": "SUM(f.freight_value)",
        "alias": "total_freight",
        "decimals": 2,
    },
    "avg_delivery_days": {
        "expr": "AVG(f.total_lead_days)",
        "alias": "avg_delivery_days",
        "decimals": 2,
    },
    "avg_approval_days": {
        "expr": "AVG(f.approval_time_days)",
        "alias": "avg_approval_days",
        "decimals": 2,
    },
    "avg_prep_days": {
        "expr": (
            "AVG(CASE WHEN f.seller_prep_time_days >= 0 "
            "THEN f.seller_prep_time_days END)"
        ),
        "alias": "avg_prep_days",
        "decimals": 2,
    },
    "avg_review_score": {
        "expr": "AVG(f.review_score)::double precision",
        "alias": "avg_review_score",
        "decimals": 2,
    },
}

OLAP_JOINS = {
    "time": "LEFT JOIN dim_time t ON f.time_id = t.time_id",
    "customer": "LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id",
    "seller": "LEFT JOIN dim_seller s ON f.seller_id = s.seller_id",
    "product": "LEFT JOIN dim_product p ON f.product_id = p.product_id",
}


def run_olap_query(
    dimensions, measures, filters: dict | None = None, date_from=None, date_to=None
):
    """Execute a whitelisted dynamic aggregation query."""
    filters = filters or {}
    conditions = []
    params = {}
    required_joins = set()

    for dimension in dimensions:
        required_joins |= set(dimension.get("requires", set()))

    customer_states = [
        str(value).strip()
        for value in (filters.get("customer_states") or [])
        if str(value).strip()
    ]
    if customer_states:
        required_joins.add("customer")
        conditions.append("cust_loc.state = ANY(%(customer_states)s)")
        params["customer_states"] = customer_states

    seller_states = [
        str(value).strip()
        for value in (filters.get("seller_states") or [])
        if str(value).strip()
    ]
    if seller_states:
        required_joins.add("seller")
        conditions.append("s.state = ANY(%(seller_states)s)")
        params["seller_states"] = seller_states

    categories = [
        str(value).strip()
        for value in (filters.get("categories") or [])
        if str(value).strip()
    ]
    if categories:
        required_joins.add("product")
        conditions.append("p.category_name_english = ANY(%(categories)s)")
        params["categories"] = categories

    if date_from is not None:
        required_joins.add("time")
        conditions.append("t.full_date >= %(date_from)s")
        params["date_from"] = date_from

    if date_to is not None:
        required_joins.add("time")
        conditions.append("t.full_date <= %(date_to)s")
        params["date_to"] = date_to

    join_sql = "\n        ".join(
        OLAP_JOINS[name]
        for name in ("time", "customer", "seller", "product")
        if name in required_joins
    )
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    select_parts = [f"{d['expr']} AS {d['alias']}" for d in dimensions]
    select_parts += [f"{m['expr']} AS {m['alias']}" for m in measures]

    group_sql = ""
    order_sql = ""
    if dimensions:
        group_sql = "GROUP BY " + ", ".join(d["expr"] for d in dimensions)
        order_sql = "ORDER BY " + ", ".join(d["alias"] for d in dimensions)

    sql = f"""
        SELECT
            {", ".join(select_parts)}
        FROM fact_delivery_sla f
        {join_sql}
        {where_sql}
        {group_sql}
        {order_sql};
    """
    return db.fetch_all(sql, params)


def get_olap_time_range():
    """Return the earliest and latest month (YYYY-MM) present in the fact table."""
    sql = """
        SELECT
            to_char(MIN(t.full_date), 'YYYY-MM') AS min_month,
            to_char(MAX(t.full_date), 'YYYY-MM') AS max_month
        FROM fact_delivery_sla f
        JOIN dim_time t ON f.time_id = t.time_id;
    """
    row = db.fetch_one(sql) or {}
    return {
        "min_month": row.get("min_month"),
        "max_month": row.get("max_month"),
    }


def get_olap_categories():
    """Return sorted distinct product categories that actually appear in facts."""
    sql = """
        SELECT DISTINCT p.category_name_english
        FROM dim_product p
        JOIN fact_delivery_sla f ON f.product_id = p.product_id
        WHERE p.category_name_english IS NOT NULL
        ORDER BY p.category_name_english;
    """
    rows = db.fetch_all(sql)
    return [row["category_name_english"] for row in rows if row["category_name_english"]]


def get_customer_states():
    """Get sorted list of unique customer states."""
    sql = """
        SELECT DISTINCT loc.state
        FROM dim_location loc
        JOIN fact_delivery_sla f ON f.customer_location_id = loc.location_id
        WHERE loc.state IS NOT NULL
        ORDER BY loc.state;
    """
    rows = db.fetch_all(sql)
    return [row["state"] for row in rows if row["state"]]


def get_seller_states():
    """Get sorted list of unique seller states."""
    sql = """
        SELECT DISTINCT s.state
        FROM dim_seller s
        JOIN fact_delivery_sla f ON f.seller_id = s.seller_id
        WHERE s.state IS NOT NULL
        ORDER BY s.state;
    """
    rows = db.fetch_all(sql)
    return [row["state"] for row in rows if row["state"]]


def build_filter_conditions(filters: dict | None):
    """Common WHERE clauses for the global filters.

    Assumes the standard aliases: ``cust_loc``, ``sell_loc`` and ``t``.
    """
    conditions = []
    params = {}
    if not filters:
        return conditions, params

    customer_state = filters.get("customer_state")
    if customer_state:
        conditions.append("cust_loc.state = %(customer_state)s")
        params["customer_state"] = customer_state.strip()

    seller_state = filters.get("seller_state")
    if seller_state:
        conditions.append("sell_loc.state = %(seller_state)s")
        params["seller_state"] = seller_state.strip()

    start_date = filters.get("start_date")
    if start_date:
        conditions.append("t.full_date >= %(start_date)s")
        params["start_date"] = start_date

    end_date = filters.get("end_date")
    if end_date:
        conditions.append("t.full_date <= %(end_date)s")
        params["end_date"] = end_date

    return conditions, params


def get_kpi(filters: dict | None = None):
    """Six global KPI statistics with optional filters."""
    conditions, params = build_filter_conditions(filters)
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT
            COUNT(*) AS order_count,
            AVG(f.total_lead_days) AS avg_delivery_time,
            AVG(f.review_score) AS avg_score,
            AVG(f.freight_value) AS avg_freight,
            COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS delay_count,
            COUNT(CASE WHEN f.has_logistics_complaint = TRUE THEN 1 END) AS complaint_count
        FROM fact_delivery_sla AS f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql};
    """
    row = db.fetch_one(sql, params)

    if not row or row["order_count"] is None or row["order_count"] == 0:
        return {
            "order_count": 0,
            "delay_count": 0,
            "complaint_count": 0,
            "avg_delivery_time": 0.0,
            "avg_freight": 0.0,
            "avg_score": 0.0,
        }

    return {
        "order_count": row["order_count"],
        "delay_count": row["delay_count"],
        "complaint_count": row["complaint_count"],
        "avg_delivery_time": row["avg_delivery_time"],
        "avg_freight": row["avg_freight"],
        "avg_score": row["avg_score"],
    }


def _order_route_cte(filters: dict | None = None) -> tuple[str, dict]:
    """CTE dùng chung: 1 dòng = 1 (đơn hàng, tuyến), cùng grain với KPI DSS.

    Fact có hạt item; gộp theo order_id + bang người bán/khách rồi loại các
    order-route có giai đoạn âm (quy ước của DSS). Không đổi công thức DSS.
    """
    conditions, params = build_filter_conditions(filters)
    conditions.extend(
        ["sell_loc.state IS NOT NULL", "cust_loc.state IS NOT NULL"]
    )
    where_sql = "WHERE " + " AND ".join(conditions)

    sql = f"""
        WITH order_routes AS (
            SELECT DISTINCT ON (f.order_id, sell_loc.state, cust_loc.state)
                f.order_id,
                sell_loc.state AS seller_state,
                cust_loc.state AS customer_state,
                t.year,
                t.month,
                t.quarter,
                f.approval_time_days AS approval,
                f.seller_prep_time_days AS prep,
                f.carrier_transit_time_days AS transit,
                f.delay_days AS delay_days,
                f.total_lead_days AS total_lead_days
            FROM fact_delivery_sla f
            LEFT JOIN dim_time t ON f.time_id = t.time_id
            LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
            LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
            {where_sql}
            ORDER BY f.order_id, sell_loc.state, cust_loc.state, f.order_item_id
        ),
        valid_routes AS (
            SELECT * FROM order_routes
            WHERE approval >= 0 AND prep >= 0 AND transit >= 0
        )
    """
    return sql, params


def get_late_trend(granularity: str = "month", filters: dict | None = None):
    """Late delivery trend by period, on the order-route grain."""
    cte_sql, params = _order_route_cte(filters)

    if granularity == "quarter":
        group_cols = "year, quarter"
        order_cols = "year, quarter"
        select_cols = "year, quarter, NULL AS month"
    elif granularity == "year":
        group_cols = "year"
        order_cols = "year"
        select_cols = "year, NULL AS quarter, NULL AS month"
    else:  # month
        group_cols = "year, month"
        order_cols = "year, month"
        select_cols = "year, NULL AS quarter, month"

    sql = cte_sql + f"""
        SELECT
            {select_cols},
            COUNT(*) AS order_count,
            COUNT(CASE WHEN delay_days > 0 THEN 1 END) AS late_count,
            AVG(total_lead_days) AS avg_delivery_time
        FROM valid_routes
        WHERE year IS NOT NULL
        GROUP BY {group_cols}
        ORDER BY {order_cols};
    """
    return db.fetch_all(sql, params)


def get_sla_breakdown(filters: dict | None = None):
    """Stage-by-stage SLA breakdown times on the order-route grain."""
    cte_sql, params = _order_route_cte(filters)

    sql = cte_sql + """
        SELECT
            COUNT(*) AS order_count,
            AVG(approval) AS avg_approval_time,
            AVG(prep) AS avg_prep_time,
            AVG(transit) AS avg_transit_time,
            AVG(total_lead_days) AS avg_delivery_time
        FROM valid_routes;
    """
    row = db.fetch_one(sql, params)

    if not row or row["order_count"] is None or row["order_count"] == 0:
        return {
            "avg_approval_time": 0.0,
            "avg_prep_time": 0.0,
            "avg_transit_time": 0.0,
            "avg_delivery_time": 0.0,
        }

    return {
        "avg_approval_time": row["avg_approval_time"],
        "avg_prep_time": row["avg_prep_time"],
        "avg_transit_time": row["avg_transit_time"],
        "avg_delivery_time": row["avg_delivery_time"],
    }


def get_orders(
    filters: dict | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """Paginated order list with search and filters; returns (total, rows)."""
    conditions, params = build_filter_conditions(filters)

    if search:
        conditions.append("f.order_id ILIKE %(search)s")
        params["search"] = f"%{search.strip()}%"

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_sql = f"""
        SELECT COUNT(DISTINCT f.order_id)
        FROM fact_delivery_sla f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql};
    """
    total_row = db.fetch_one(count_sql, params) or {}
    total = int(total_row.get("count") or 0)

    params["limit"] = limit
    params["offset"] = offset

    data_sql = f"""
        SELECT
            f.order_id,
            MAX(t.full_date) AS order_date,
            MAX(cust_loc.state) AS customer_state,
            MAX(sell_loc.state) AS seller_state,
            AVG(f.approval_time_days) AS approval_time_days,
            AVG(f.seller_prep_time_days) AS seller_prep_time_days,
            AVG(f.carrier_transit_time_days) AS carrier_transit_time_days,
            AVG(f.total_lead_days) AS total_delivery_time_days,
            ROUND(AVG(f.review_score))::int AS review_score,
            BOOL_OR(f.delay_days > 0) AS is_late
        FROM fact_delivery_sla f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql}
        GROUP BY f.order_id
        ORDER BY MAX(t.full_date) DESC NULLS LAST, f.order_id
        LIMIT %(limit)s OFFSET %(offset)s;
    """
    rows = db.fetch_all(data_sql, params)
    return total, rows


def get_regions(filters: dict | None = None):
    """Regional routes grouped by seller/customer state, order-route grain."""
    cte_sql, params = _order_route_cte(filters)

    sql = cte_sql + """
        SELECT
            seller_state,
            customer_state,
            COUNT(*) AS order_count,
            COUNT(CASE WHEN delay_days > 0 THEN 1 END) AS late_count,
            AVG(total_lead_days) AS avg_delivery_time
        FROM valid_routes
        GROUP BY seller_state, customer_state
        ORDER BY order_count DESC, avg_delivery_time DESC;
    """
    return db.fetch_all(sql, params)


def get_sellers(
    limit: int = 50, sort_by: str = "total_orders", filters: dict | None = None
):
    """Seller metrics grouped by seller_id joining Dim_Seller."""
    conditions, params = build_filter_conditions(filters)
    conditions.append("f.seller_id IS NOT NULL")
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    order_by_col = "total_orders DESC"
    if sort_by == "avg_prep_time":
        order_by_col = "avg_prep_time DESC"
    elif sort_by == "avg_score":
        order_by_col = "avg_score DESC"

    params["limit"] = limit

    sql = f"""
        SELECT
            f.seller_id,
            MAX(s.city) AS seller_city,
            MAX(s.state) AS seller_state,
            COUNT(DISTINCT f.order_id) AS total_orders,
            AVG(f.seller_prep_time_days) AS avg_prep_time,
            AVG(f.review_score) AS avg_score
        FROM fact_delivery_sla f
        JOIN dim_seller s ON f.seller_id = s.seller_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        {where_sql}
        GROUP BY f.seller_id
        ORDER BY {order_by_col}
        LIMIT %(limit)s;
    """
    return db.fetch_all(sql, params)


def get_alerts(limit: int = 50, filters: dict | None = None):
    """Operational alerts from critical orders (complaints or late deliveries)."""
    conditions, params = build_filter_conditions(filters)
    conditions.append("(f.has_logistics_complaint = TRUE OR f.delay_days > 0)")
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    params["limit"] = limit

    sql = f"""
        SELECT
            f.order_id,
            t.full_date AS order_date,
            cust_loc.state AS customer_state,
            sell_loc.state AS seller_state,
            f.carrier_transit_time_days,
            f.seller_prep_time_days,
            f.review_score,
            (f.delay_days > 0) AS is_late,
            f.has_logistics_complaint
        FROM fact_delivery_sla f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql}
        ORDER BY t.full_date DESC NULLS LAST, (f.delay_days > 0) DESC
        LIMIT %(limit)s;
    """
    return db.fetch_all(sql, params)


# ===========================================================================
# Authentication
# ===========================================================================
def get_account(username: str):
    """Return the stored credential row for ``username`` (or None)."""
    sql = """
        SELECT username, password
        FROM accounts
        WHERE username = %(username)s
        LIMIT 1;
    """
    return db.fetch_one(sql, {"username": username})


def update_account_password(username: str, password_hash: str) -> None:
    """Persist an upgraded (hashed) password for ``username``."""
    sql = """
        UPDATE accounts
        SET password = %(password)s
        WHERE username = %(username)s;
    """
    db.execute(sql, {"password": password_hash, "username": username})
