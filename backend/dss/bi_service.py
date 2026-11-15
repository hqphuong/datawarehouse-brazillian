"""Business logic for the ported BI/OLAP/auth API.

Ported from the team's ``service.py`` with the framework removed: rows come from
``db.fetch_*`` as plain dictionaries, validation lives in ``bi_validation``.
Values, rounding and the intentional ``late_rate``/``delay_rate`` difference are
kept exactly as before.
"""

from __future__ import annotations

import datetime
import math

from . import bi_repo as repo
from .bi_validation import parse_period_bound


def generate_month_periods(
    start_year: int, start_month: int, end_year: int, end_month: int
):
    """Yield all (year, month) pairs chronologically, inclusive."""
    cur_year = start_year
    cur_month = start_month
    while (cur_year < end_year) or (cur_year == end_year and cur_month <= end_month):
        yield cur_year, cur_month
        cur_month += 1
        if cur_month > 12:
            cur_month = 1
            cur_year += 1


def generate_quarter_periods(
    start_year: int, start_quarter: int, end_year: int, end_quarter: int
):
    """Yield all (year, quarter) pairs chronologically, inclusive."""
    cur_year = start_year
    cur_quarter = start_quarter
    while (cur_year < end_year) or (
        cur_year == end_year and cur_quarter <= end_quarter
    ):
        yield cur_year, cur_quarter
        cur_quarter += 1
        if cur_quarter > 4:
            cur_quarter = 1
            cur_year += 1


def health_check() -> str:
    return "Server is running healthy. I love Kasane Teto"


def get_customer_states() -> dict:
    return {"states": repo.get_customer_states()}


def get_seller_states() -> dict:
    return {"states": repo.get_seller_states()}


def get_kpi(filters: dict | None = None) -> dict:
    raw_kpi = repo.get_kpi(filters)
    order_count = raw_kpi.get("order_count") or 0
    delay_count = raw_kpi.get("delay_count") or 0
    complaint_count = raw_kpi.get("complaint_count") or 0

    delay_rate = (delay_count / order_count) if order_count > 0 else 0.0
    complaint_rate = (complaint_count / order_count) if order_count > 0 else 0.0

    return {
        "order_count": order_count,
        "delay_rate": round(float(delay_rate), 4),
        "complaint_rate": round(float(complaint_rate), 4),
        "avg_delivery_time": round(float(raw_kpi.get("avg_delivery_time") or 0.0), 2),
        "avg_freight_cost": round(float(raw_kpi.get("avg_freight") or 0.0), 2),
        "avg_score": round(float(raw_kpi.get("avg_score") or 0.0), 2),
    }


def get_late_trend(query_args: dict | None = None, extend_to_data_range: bool = True):
    """Build a continuous late-delivery trend timeline."""
    args = query_args or {}
    granularity = args.get("granularity", "month")
    rows = repo.get_late_trend(granularity=granularity, filters=args)

    data_by_period = {}
    for row in rows:
        if row["year"] is None:
            continue
        order_count = row["order_count"] or 0
        late_count = row["late_count"] or 0
        delay_rate = (late_count / order_count) if order_count > 0 else 0.0
        avg_delivery_time = round(float(row["avg_delivery_time"] or 0.0), 2)

        year = int(row["year"])
        month = int(row["month"]) if row["month"] is not None else None
        quarter = int(row["quarter"]) if row["quarter"] is not None else None

        if granularity == "quarter":
            key = (year, quarter)
        elif granularity == "year":
            key = (year,)
        else:
            key = (year, month)

        data_by_period[key] = {
            "avg_delivery_time": avg_delivery_time,
            "delay_rate": round(float(delay_rate), 4),
            "late_count": late_count,
            "month": month,
            "order_count": order_count,
            "quarter": quarter,
            "year": year,
        }

    start_date = args.get("start_date")
    end_date = args.get("end_date")

    if isinstance(start_date, str):
        try:
            start_date = datetime.date.fromisoformat(start_date[:10])
        except Exception:
            start_date = None

    if isinstance(end_date, str):
        try:
            end_date = datetime.date.fromisoformat(end_date[:10])
        except Exception:
            end_date = None

    # If no data and no date bounds specified, return empty list
    if not data_by_period and not (start_date and end_date):
        return []

    trend_list = []

    if granularity == "quarter":
        if start_date:
            start_year = start_date.year
            start_q = (start_date.month - 1) // 3 + 1
        else:
            start_year, start_q = min(data_by_period.keys())

        if end_date:
            end_year = end_date.year
            end_q = (end_date.month - 1) // 3 + 1
        else:
            end_year, end_q = max(data_by_period.keys())

        if extend_to_data_range and data_by_period:
            data_min_y, data_min_q = min(data_by_period.keys())
            if (data_min_y, data_min_q) < (start_year, start_q):
                start_year, start_q = data_min_y, data_min_q
            data_max_y, data_max_q = max(data_by_period.keys())
            if (data_max_y, data_max_q) > (end_year, end_q):
                end_year, end_q = data_max_y, data_max_q

        for y, q in generate_quarter_periods(start_year, start_q, end_year, end_q):
            if (y, q) in data_by_period:
                trend_list.append(data_by_period[(y, q)])
            else:
                trend_list.append(
                    {
                        "avg_delivery_time": 0.0,
                        "delay_rate": 0.0,
                        "late_count": 0,
                        "month": None,
                        "order_count": 0,
                        "quarter": q,
                        "year": y,
                    }
                )

    elif granularity == "year":
        start_year = start_date.year if start_date else min(data_by_period.keys())[0]
        end_year = end_date.year if end_date else max(data_by_period.keys())[0]

        if extend_to_data_range and data_by_period:
            data_min_y = min(data_by_period.keys())[0]
            if data_min_y < start_year:
                start_year = data_min_y
            data_max_y = max(data_by_period.keys())[0]
            if data_max_y > end_year:
                end_year = data_max_y

        for y in range(start_year, end_year + 1):
            if (y,) in data_by_period:
                trend_list.append(data_by_period[(y,)])
            else:
                trend_list.append(
                    {
                        "avg_delivery_time": 0.0,
                        "delay_rate": 0.0,
                        "late_count": 0,
                        "month": None,
                        "order_count": 0,
                        "quarter": None,
                        "year": y,
                    }
                )

    else:  # granularity == "month"
        if start_date:
            start_year, start_m = start_date.year, start_date.month
        else:
            start_year, start_m = min(data_by_period.keys())

        if end_date:
            end_year, end_m = end_date.year, end_date.month
        else:
            end_year, end_m = max(data_by_period.keys())

        if extend_to_data_range and data_by_period:
            data_min_y, data_min_m = min(data_by_period.keys())
            if (data_min_y, data_min_m) < (start_year, start_m):
                start_year, start_m = data_min_y, data_min_m
            data_max_y, data_max_m = max(data_by_period.keys())
            if (data_max_y, data_max_m) > (end_year, end_m):
                end_year, end_m = data_max_y, data_max_m

        for y, m in generate_month_periods(start_year, start_m, end_year, end_m):
            if (y, m) in data_by_period:
                trend_list.append(data_by_period[(y, m)])
            else:
                trend_list.append(
                    {
                        "avg_delivery_time": 0.0,
                        "delay_rate": 0.0,
                        "late_count": 0,
                        "month": m,
                        "order_count": 0,
                        "quarter": None,
                        "year": y,
                    }
                )

    return trend_list


def get_sla_breakdown(filters: dict | None = None) -> dict:
    raw_sla = repo.get_sla_breakdown(filters)
    return {
        "avg_approval_time": round(float(raw_sla.get("avg_approval_time") or 0.0), 2),
        "avg_prep_time": round(float(raw_sla.get("avg_prep_time") or 0.0), 2),
        "avg_transit_time": round(float(raw_sla.get("avg_transit_time") or 0.0), 2),
        "avg_delivery_time": round(float(raw_sla.get("avg_delivery_time") or 0.0), 2),
    }


def get_orders(query_args: dict | None = None) -> dict:
    args = query_args or {}
    page = int(args.get("page", 1))
    page_size = int(args.get("page_size", 20))
    search = args.get("search")
    offset = (page - 1) * page_size

    total, rows = repo.get_orders(
        filters=args, search=search, limit=page_size, offset=offset
    )

    orders_list = []
    for row in rows:
        is_late = bool(row["is_late"])
        orders_list.append(
            {
                "order_id": str(row["order_id"]),
                "order_date": row["order_date"],
                "customer_state": row["customer_state"],
                "seller_state": row["seller_state"],
                "approval_time_days": round(float(row["approval_time_days"]), 2)
                if row["approval_time_days"] is not None
                else None,
                "seller_prep_time_days": round(float(row["seller_prep_time_days"]), 2)
                if row["seller_prep_time_days"] is not None
                else None,
                "carrier_transit_time_days": round(
                    float(row["carrier_transit_time_days"]), 2
                )
                if row["carrier_transit_time_days"] is not None
                else None,
                "total_delivery_time_days": round(
                    float(row["total_delivery_time_days"]), 2
                )
                if row["total_delivery_time_days"] is not None
                else None,
                "review_score": int(row["review_score"])
                if row["review_score"] is not None
                else None,
                "is_late": is_late,
                "sla_status": "late" if is_late else "on_time",
            }
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "orders": orders_list,
    }


def get_regions(filters: dict | None = None) -> list:
    rows = repo.get_regions(filters)
    result = []
    for row in rows:
        order_count = row["order_count"] or 0
        late_count = row["late_count"] or 0
        late_rate = (late_count / order_count) if order_count > 0 else 0.0

        seller_state = row["seller_state"] or "Unknown"
        customer_state = row["customer_state"] or "Unknown"

        result.append(
            {
                "seller_state": seller_state,
                "customer_state": customer_state,
                "order_count": order_count,
                "late_count": late_count,
                "late_rate": round(float(late_rate), 4),
                "avg_delivery_time": round(float(row["avg_delivery_time"] or 0.0), 2),
            }
        )

    return result


def get_sellers(query_args: dict | None = None) -> list:
    args = query_args or {}
    limit = int(args.get("limit", 50))
    sort_by = args.get("sort_by", "total_orders")

    rows = repo.get_sellers(limit=limit, sort_by=sort_by, filters=args)
    result = []
    for row in rows:
        result.append(
            {
                "seller_id": str(row["seller_id"]),
                "seller_city": row["seller_city"] or "Unknown",
                "seller_state": row["seller_state"] or "Unknown",
                "total_orders": row["total_orders"] or 0,
                "avg_prep_time": round(float(row["avg_prep_time"] or 0.0), 2),
                "avg_score": round(float(row["avg_score"] or 0.0), 2),
            }
        )

    return result


def get_alerts(query_args: dict | None = None) -> list:
    args = query_args or {}
    limit = int(args.get("limit", 50))
    severity_filter = args.get("severity")

    rows = repo.get_alerts(limit=limit, filters=args)
    alerts = []

    for row in rows:
        order_id = str(row["order_id"])
        has_complaint = bool(row["has_logistics_complaint"])
        is_late = bool(row["is_late"])
        transit_days = float(row["carrier_transit_time_days"] or 0.0)
        review_score = (
            int(row["review_score"]) if row["review_score"] is not None else None
        )

        # Determine alert classification and severity
        if has_complaint:
            alert_type = "LOGISTICS_COMPLAINT"
            severity = (
                "CRITICAL" if (review_score is not None and review_score <= 1) else "WARNING"
            )
            title = f"Logistics Complaint: Order {order_id[:8]}"
            message = (
                f"Customer lodged a logistics complaint for order {order_id}. "
                f"Review score: {review_score if review_score is not None else 'N/A'}."
            )
            metric_val = float(review_score) if review_score is not None else None
        elif is_late:
            alert_type = "LATE_DELIVERY"
            severity = "CRITICAL" if transit_days > 15.0 else "WARNING"
            title = f"Late Delivery: Order {order_id[:8]}"
            message = (
                f"Order {order_id} was delivered late. "
                f"Carrier transit time reached {round(transit_days, 1)} days."
            )
            metric_val = round(transit_days, 2)
        else:
            alert_type = "OPERATIONAL_WARNING"
            severity = "INFO"
            title = f"Notice: Order {order_id[:8]}"
            message = f"Order {order_id} flagged for logistics review."
            metric_val = None

        if severity_filter and severity_filter != "ALL" and severity != severity_filter:
            continue

        alerts.append(
            {
                "id": f"alert-{order_id}",
                "type": alert_type,
                "severity": severity,
                "title": title,
                "message": message,
                "order_id": order_id,
                "order_date": row["order_date"],
                "customer_state": row["customer_state"],
                "seller_state": row["seller_state"],
                "metric_value": metric_val,
            }
        )

    return alerts


# ===========================================================================
# OLAP Query Builder
# ===========================================================================
def _resolve_olap_dimensions(dimension_keys: list, time_mode: str) -> list:
    """Translate whitelisted dimension keys into SQL definitions."""
    resolved = []
    seen_aliases = set()
    time_added = False

    for key in dimension_keys:
        if key in repo.OLAP_TIME_DIMENSION_KEYS:
            if time_added:
                continue
            definition = repo.OLAP_TIME_DIMENSIONS.get(time_mode)
            time_added = True
        else:
            definition = repo.OLAP_DIMENSIONS.get(key)

        if not definition:
            continue
        if definition["alias"] in seen_aliases:
            continue

        seen_aliases.add(definition["alias"])
        resolved.append(definition)

    return resolved


def _resolve_olap_measures(measure_keys: list) -> list:
    """Translate whitelisted measure keys into SQL definitions."""
    resolved = []
    seen_aliases = set()
    for key in measure_keys:
        definition = repo.OLAP_MEASURES.get(key)
        if not definition:
            continue
        if definition["alias"] in seen_aliases:
            continue
        seen_aliases.add(definition["alias"])
        resolved.append(definition)
    return resolved


def _format_measure_value(value, decimals: int):
    """Normalize an aggregate value: NULL -> 0, integers stay integers."""
    if value is None:
        return 0 if decimals == 0 else 0.0
    if decimals == 0:
        return int(value)
    return round(float(value), decimals)


def get_olap_metadata() -> dict:
    """Return distinct filter values and the available month range."""
    return {
        "states": repo.get_customer_states(),
        "categories": repo.get_olap_categories(),
        "seller_states": repo.get_seller_states(),
        "time_range": repo.get_olap_time_range(),
    }


def get_olap_query(payload: dict | None = None) -> dict:
    """Execute a dynamic OLAP aggregation and return columns + rows."""
    payload = payload or {}
    time_mode = payload.get("time_mode") or "month"

    dimensions = _resolve_olap_dimensions(payload.get("dimensions") or [], time_mode)
    measures = _resolve_olap_measures(payload.get("measures") or [])
    filters = payload.get("filters") or {}

    date_from = parse_period_bound(payload.get("from_time"), end=False)
    date_to = parse_period_bound(payload.get("to_time"), end=True)

    rows = repo.run_olap_query(
        dimensions=dimensions,
        measures=measures,
        filters=filters,
        date_from=date_from,
        date_to=date_to,
    )

    columns = [dimension["alias"] for dimension in dimensions]
    columns += [measure["alias"] for measure in measures]

    data = []
    for row in rows:
        record = {}
        for dimension in dimensions:
            record[dimension["alias"]] = row[dimension["alias"]]
        for measure in measures:
            record[measure["alias"]] = _format_measure_value(
                row[measure["alias"]],
                measure.get("decimals", 2),
            )
        data.append(record)

    return {"columns": columns, "data": data}


# ===========================================================================
# BI Dashboard overview
# ===========================================================================
def get_overview(args: dict | None = None) -> dict:
    """Aggregate the six dashboard KPIs and a late-rate trend for one request."""
    args = args or {}
    time_mode = args.get("time_mode") or "month"

    filters = {}
    if args.get("customer_state"):
        filters["customer_state"] = args["customer_state"]
    if args.get("seller_state"):
        filters["seller_state"] = args["seller_state"]

    date_from = parse_period_bound(args.get("from_time"), end=False)
    date_to = parse_period_bound(args.get("to_time"), end=True)
    if date_from is not None:
        filters["start_date"] = date_from
    if date_to is not None:
        filters["end_date"] = date_to

    trend_args = dict(filters)
    trend_args["granularity"] = time_mode

    return {
        "time_mode": time_mode,
        "from_time": args.get("from_time"),
        "to_time": args.get("to_time"),
        "customer_state": args.get("customer_state"),
        "seller_state": args.get("seller_state"),
        "kpis": get_kpi(filters),
        "late_trend": get_late_trend(
            trend_args,
            extend_to_data_range=False,
        ),
    }

