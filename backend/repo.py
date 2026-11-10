from app import db
from sqlalchemy import text


def build_filter_conditions(filters: dict | None):
    """
    Common helper to extract SQL WHERE conditions and parameters
    for global filters: customer_state, seller_state, start_date, end_date.
    Assumes standard table aliases:
      - cust_loc: Dim_Location for customer
      - sell_loc: Dim_Location for seller
      - t: Dim_Time for order date
    """
    conditions = []
    params = {}
    if not filters:
        return conditions, params

    customer_state = filters.get("customer_state")
    if customer_state:
        conditions.append("cust_loc.state = :customer_state")
        params["customer_state"] = customer_state.strip()

    seller_state = filters.get("seller_state")
    if seller_state:
        conditions.append("sell_loc.state = :seller_state")
        params["seller_state"] = seller_state.strip()

    start_date = filters.get("start_date")
    if start_date:
        conditions.append("t.full_date >= :start_date")
        params["start_date"] = start_date

    end_date = filters.get("end_date")
    if end_date:
        conditions.append("t.full_date <= :end_date")
        params["end_date"] = end_date

    return conditions, params


def get_customer_states():
    """Get sorted list of unique customer states."""
    sql = text("""
        SELECT DISTINCT loc.state
        FROM dim_location loc
        JOIN fact_delivery_sla f ON f.customer_location_id = loc.location_id
        WHERE loc.state IS NOT NULL
        ORDER BY loc.state;
    """)
    result = db.session.execute(sql)
    return [row.state for row in result if row.state]


def get_seller_states():
    """Get sorted list of unique seller states."""
    sql = text("""
        SELECT DISTINCT s.state
        FROM dim_seller s
        JOIN fact_delivery_sla f ON f.seller_id = s.seller_id
        WHERE s.state IS NOT NULL
        ORDER BY s.state;
    """)
    result = db.session.execute(sql)
    return [row.state for row in result if row.state]


def get_kpi(filters: dict | None = None):
    """
    Get 6 global KPI statistics with optional filters:
    - Total order count (item rows)
    - Delay count (computed from delay_days > 0)
    - Complaint count (has_logistics_complaint = TRUE)
    - Avg delivery time (total_lead_days)
    - Avg freight cost
    - Avg review score
    """
    conditions, params = build_filter_conditions(filters)
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = text(f"""
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
    """)
    result = db.session.execute(sql, params)
    row = result.first()

    if not row or row.order_count is None or row.order_count == 0:
        return {
            "order_count": 0,
            "delay_count": 0,
            "complaint_count": 0,
            "avg_delivery_time": 0.0,
            "avg_freight": 0.0,
            "avg_score": 0.0
        }

    return {
        "order_count": row.order_count,
        "delay_count": row.delay_count,
        "complaint_count": row.complaint_count,
        "avg_delivery_time": row.avg_delivery_time,
        "avg_freight": row.avg_freight,
        "avg_score": row.avg_score
    }


def get_late_trend(granularity: str = "month", filters: dict | None = None):
    """
    Get late delivery trend aggregated by period (month, quarter, or year).
    Uses delay_days > 0 to identify late deliveries and total_lead_days for average delivery time.
    """
    conditions, params = build_filter_conditions(filters)
    conditions.append("t.year IS NOT NULL")

    if granularity == "quarter":
        group_cols = "t.year, t.quarter"
        order_cols = "t.year, t.quarter"
        select_cols = "t.year, t.quarter, NULL AS month"
    elif granularity == "year":
        group_cols = "t.year"
        order_cols = "t.year"
        select_cols = "t.year, NULL AS quarter, NULL AS month"
    else:  # month
        group_cols = "t.year, t.month"
        order_cols = "t.year, t.month"
        select_cols = "t.year, NULL AS quarter, t.month"

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = text(f"""
        SELECT 
            {select_cols},
            COUNT(*) AS order_count,
            COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS late_count,
            AVG(f.total_lead_days) AS avg_delivery_time
        FROM fact_delivery_sla f
        JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql}
        GROUP BY {group_cols}
        ORDER BY {order_cols};
    """)
    result = db.session.execute(sql, params)
    return result.fetchall()


def get_sla_breakdown(filters: dict | None = None):
    """
    Get stage-by-stage SLA breakdown times:
    - approval time
    - seller prep time
    - carrier transit time
    - total delivery time (total_lead_days)
    """
    conditions, params = build_filter_conditions(filters)
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = text(f"""
        SELECT 
            COUNT(*) AS order_count,
            AVG(f.approval_time_days) AS avg_approval_time,
            AVG(CASE WHEN f.seller_prep_time_days >= 0 THEN f.seller_prep_time_days END) AS avg_prep_time,
            AVG(CASE WHEN f.carrier_transit_time_days >= 0 THEN f.carrier_transit_time_days END) AS avg_transit_time,
            AVG(f.total_lead_days) AS avg_delivery_time
        FROM fact_delivery_sla f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql};
    """)
    result = db.session.execute(sql, params)
    row = result.first()

    if not row or row.order_count is None or row.order_count == 0:
        return {
            "avg_approval_time": 0.0,
            "avg_prep_time": 0.0,
            "avg_transit_time": 0.0,
            "avg_delivery_time": 0.0
        }

    return {
        "avg_approval_time": row.avg_approval_time,
        "avg_prep_time": row.avg_prep_time,
        "avg_transit_time": row.avg_transit_time,
        "avg_delivery_time": row.avg_delivery_time
    }


def get_orders(filters: dict | None = None, search: str | None = None, limit: int = 20, offset: int = 0):
    """
    Get paginated order list with search and filters.
    Returns (total_distinct_orders, rows).
    """
    conditions, params = build_filter_conditions(filters)

    if search:
        conditions.append("f.order_id ILIKE :search")
        params["search"] = f"%{search.strip()}%"

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    count_sql = text(f"""
        SELECT COUNT(DISTINCT f.order_id)
        FROM fact_delivery_sla f
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        LEFT JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        LEFT JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        {where_sql};
    """)
    total = db.session.execute(count_sql, params).scalar() or 0

    params["limit"] = limit
    params["offset"] = offset

    data_sql = text(f"""
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
        LIMIT :limit OFFSET :offset;
    """)
    rows = db.session.execute(data_sql, params).fetchall()
    return total, rows


def get_regions(filters: dict | None = None):
    """
    Get regional routes grouped by seller_state and customer_state.
    """
    conditions, params = build_filter_conditions(filters)
    conditions.append("cust_loc.state IS NOT NULL")
    conditions.append("sell_loc.state IS NOT NULL")
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = text(f"""
        SELECT 
            sell_loc.state AS seller_state,
            cust_loc.state AS customer_state,
            COUNT(*) AS order_count,
            COUNT(CASE WHEN f.delay_days > 0 THEN 1 END) AS late_count,
            AVG(f.total_lead_days) AS avg_delivery_time
        FROM fact_delivery_sla f
        JOIN dim_location cust_loc ON f.customer_location_id = cust_loc.location_id
        JOIN dim_location sell_loc ON f.seller_location_id = sell_loc.location_id
        LEFT JOIN dim_time t ON f.time_id = t.time_id
        {where_sql}
        GROUP BY sell_loc.state, cust_loc.state
        ORDER BY order_count DESC, avg_delivery_time DESC;
    """)
    result = db.session.execute(sql, params)
    return result.fetchall()


def get_sellers(limit: int = 50, sort_by: str = "total_orders", filters: dict | None = None):
    """
    Get seller metrics grouped by seller_id joining Dim_Seller.
    """
    conditions, params = build_filter_conditions(filters)
    conditions.append("f.seller_id IS NOT NULL")
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    order_by_col = "total_orders DESC"
    if sort_by == "avg_prep_time":
        order_by_col = "avg_prep_time DESC"
    elif sort_by == "avg_score":
        order_by_col = "avg_score DESC"

    params["limit"] = limit

    sql = text(f"""
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
        LIMIT :limit;
    """)
    result = db.session.execute(sql, params)
    return result.fetchall()


def get_alerts(limit: int = 50, filters: dict | None = None):
    """
    Get operational alerts from critical orders (logistics complaints or late deliveries).
    """
    conditions, params = build_filter_conditions(filters)
    conditions.append("(f.has_logistics_complaint = TRUE OR f.delay_days > 0)")
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    params["limit"] = limit

    sql = text(f"""
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
        LIMIT :limit;
    """)
    result = db.session.execute(sql, params)
    return result.fetchall()
