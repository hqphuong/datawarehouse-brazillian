"""Hand-written validation for the ported BI/OLAP/auth endpoints.

Replaces the marshmallow schemas of the original Flask API while keeping the
same accepted values, defaults and limits.  Every failure raises ``ApiError``
so the blueprints render ``{"message": "<string>"}`` with status 400.
"""

from __future__ import annotations

import calendar
import datetime
import re

from . import bi_repo as repo
from .api_errors import ApiError

_PERIOD_PATTERN = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")

TIME_MODES = ("month", "quarter", "year")


# ---------------------------------------------------------------------------
# Period helpers (behaviour copied from the former schema.py)
# ---------------------------------------------------------------------------
def parse_period_bound(value, end: bool = False) -> datetime.date | None:
    """Parse ``YYYY-MM`` / ``YYYY-MM-DD`` into an inclusive date."""
    if value in (None, ""):
        return None

    match = _PERIOD_PATTERN.match(str(value).strip())
    if not match:
        raise ApiError("Time values must use the format YYYY-MM or YYYY-MM-DD")

    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        raise ApiError("Month must be between 01 and 12")

    if match.group(3):
        day = int(match.group(3))
    else:
        day = calendar.monthrange(year, month)[1] if end else 1

    try:
        return datetime.date(year, month, day)
    except ValueError:
        raise ApiError("Invalid calendar date in time value")


def _validate_period_range(from_value, to_value) -> None:
    start = parse_period_bound(from_value, end=False) if from_value else None
    end = parse_period_bound(to_value, end=True) if to_value else None
    if start and end and start > end:
        raise ApiError(
            "The lower time bound must be before or equal to the upper time bound"
        )


# ---------------------------------------------------------------------------
# Scalar argument helpers
# ---------------------------------------------------------------------------
def _optional_str(args, name: str) -> str | None:
    value = args.get(name)
    if value in (None, ""):
        return None
    return value


def _int_arg(args, name: str, default: int, minimum=None, maximum=None) -> int:
    raw = args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ApiError(f"{name} must be greater than or equal to {minimum}")
    if maximum is not None and value > maximum:
        raise ApiError(f"{name} must be less than or equal to {maximum}")
    return value


def _choice_arg(args, name: str, default, allowed) -> str:
    raw = args.get(name)
    if raw in (None, ""):
        return default
    if raw not in allowed:
        raise ApiError(f"{name} must be one of: {', '.join(allowed)}")
    return raw


def _date_arg(args, name: str) -> datetime.date | None:
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        return datetime.date.fromisoformat(str(raw).strip())
    except ValueError:
        raise ApiError(f"{name} must be a valid date in YYYY-MM-DD format")


def filter_args(args) -> dict:
    """Global filters shared by analytics/order endpoints."""
    filters = {
        "customer_state": _optional_str(args, "customer_state"),
        "seller_state": _optional_str(args, "seller_state"),
        "start_date": _date_arg(args, "start_date"),
        "end_date": _date_arg(args, "end_date"),
    }
    if (
        filters["start_date"]
        and filters["end_date"]
        and filters["start_date"] > filters["end_date"]
    ):
        raise ApiError("start_date must be before or equal to end_date")
    return filters


# ---------------------------------------------------------------------------
# Query argument bundles
# ---------------------------------------------------------------------------
def late_trend_query(args) -> dict:
    query = filter_args(args)
    query["granularity"] = _choice_arg(args, "granularity", "month", TIME_MODES)
    return query


def orders_query(args) -> dict:
    query = filter_args(args)
    query["search"] = _optional_str(args, "search")
    query["page"] = _int_arg(args, "page", 1, minimum=1)
    query["page_size"] = _int_arg(args, "page_size", 20, minimum=1, maximum=100)
    return query


def seller_query(args) -> dict:
    query = filter_args(args)
    query["limit"] = _int_arg(args, "limit", 50, minimum=1, maximum=500)
    query["sort_by"] = _choice_arg(
        args, "sort_by", "total_orders", ("total_orders", "avg_prep_time", "avg_score")
    )
    return query


def alerts_query(args) -> dict:
    query = filter_args(args)
    query["limit"] = _int_arg(args, "limit", 50, minimum=1, maximum=200)
    query["severity"] = _choice_arg(
        args, "severity", None, ("ALL", "CRITICAL", "WARNING", "INFO")
    )
    return query


def overview_query(args) -> dict:
    """Dashboard overview query: ``from``/``to`` map to from_time/to_time."""
    query = {
        "time_mode": _choice_arg(args, "time_mode", "month", TIME_MODES),
        "from_time": _optional_str(args, "from"),
        "to_time": _optional_str(args, "to"),
        "customer_state": _optional_str(args, "customer_state"),
        "seller_state": _optional_str(args, "seller_state"),
    }
    _validate_period_range(query["from_time"], query["to_time"])
    return query


# ---------------------------------------------------------------------------
# OLAP payload
# ---------------------------------------------------------------------------
def _string_list(payload: dict, key: str, *, required: bool) -> list[str]:
    raw = payload.get(key)
    if raw is None:
        if required:
            raise ApiError(f"{key} is required")
        return []
    if not isinstance(raw, list):
        raise ApiError(f"{key} must be a list of strings")
    values = []
    for item in raw:
        if not isinstance(item, str):
            raise ApiError(f"{key} must be a list of strings")
        values.append(item)
    if required and not values:
        raise ApiError(f"{key} must contain at least one item")
    return values


def _allowed_dimensions() -> set[str]:
    return set(repo.OLAP_DIMENSIONS) | set(repo.OLAP_TIME_DIMENSION_KEYS)


def _validate_dimensions(dimensions: list[str]) -> None:
    allowed = _allowed_dimensions()
    for value in dimensions:
        if value not in allowed:
            raise ApiError(
                f"Unsupported dimension '{value}'. Allowed values: "
                f"{', '.join(sorted(allowed))}"
            )


def _validate_measures(measures: list[str]) -> None:
    for value in measures:
        if value not in repo.OLAP_MEASURES:
            raise ApiError(
                f"Unsupported measure '{value}'. Allowed values: "
                f"{', '.join(sorted(repo.OLAP_MEASURES))}"
            )


def _olap_filters(payload: dict) -> dict:
    raw = payload.get("filters")
    if raw is None:
        return {"customer_states": [], "seller_states": [], "categories": []}
    if not isinstance(raw, dict):
        raise ApiError("filters must be an object")
    return {
        "customer_states": _string_list(raw, "customer_states", required=False),
        "seller_states": _string_list(raw, "seller_states", required=False),
        "categories": _string_list(raw, "categories", required=False),
    }


def olap_payload(payload) -> dict:
    """Validate and normalise a ``POST /api/olap/query`` body."""
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object")

    time_mode = payload.get("time_mode") or "month"
    if time_mode not in TIME_MODES:
        raise ApiError(f"time_mode must be one of: {', '.join(TIME_MODES)}")

    dimensions = _string_list(payload, "dimensions", required=True)
    measures = _string_list(payload, "measures", required=True)
    _validate_dimensions(dimensions)
    _validate_measures(measures)

    from_time = payload.get("from_time")
    to_time = payload.get("to_time")
    parse_period_bound(from_time) if from_time else None
    parse_period_bound(to_time, end=True) if to_time else None
    _validate_period_range(from_time, to_time)

    return {
        "time_mode": time_mode,
        "from_time": from_time,
        "to_time": to_time,
        "dimensions": dimensions,
        "measures": measures,
        "filters": _olap_filters(payload),
    }
