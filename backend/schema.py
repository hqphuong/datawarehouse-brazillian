import calendar
import datetime
import re

from marshmallow import Schema, fields, validate, validates_schema, ValidationError


# ---------------------------------------------------------------------------
# Period helpers (shared with service.py)
# ---------------------------------------------------------------------------
_PERIOD_PATTERN = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")


def parse_period_bound(value, end: bool = False):
    """
    Parse a `YYYY-MM` or `YYYY-MM-DD` string into an inclusive `datetime.date`.

    - `YYYY-MM` is expanded to the first day of the month when `end=False` and to
      the last day of the month when `end=True` (inclusive range semantics).
    - Returns `None` for empty input.
    - Raises `marshmallow.ValidationError` for malformed or impossible dates.
    """
    if value in (None, ""):
        return None

    match = _PERIOD_PATTERN.match(str(value).strip())
    if not match:
        raise ValidationError("Time values must use the format YYYY-MM or YYYY-MM-DD")

    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 01 and 12")

    if match.group(3):
        day = int(match.group(3))
    else:
        day = calendar.monthrange(year, month)[1] if end else 1

    try:
        return datetime.date(year, month, day)
    except ValueError:
        raise ValidationError("Invalid calendar date in time value")


def validate_period_format(value):
    """Marshmallow field validator for `YYYY-MM` / `YYYY-MM-DD` strings."""
    if value:
        parse_period_bound(value)


def validate_period_range(data):
    """Schema-level validator ensuring from_time <= to_time."""
    start_value = data.get("from_time")
    end_value = data.get("to_time")
    start = parse_period_bound(start_value, end=False) if start_value else None
    end = parse_period_bound(end_value, end=True) if end_value else None
    if start and end and start > end:
        raise ValidationError(
            "The lower time bound must be before or equal to the upper time bound",
            field_name="from_time",
        )


def _allowed_olap_dimensions():
    # Imported lazily to keep `schema.py` free of `app`/SQLAlchemy imports at
    # module load time and to avoid an import cycle with `repo.py`.
    import repo
    return set(repo.OLAP_DIMENSIONS) | set(repo.OLAP_TIME_DIMENSION_KEYS)


def validate_olap_dimension(value):
    allowed = _allowed_olap_dimensions()
    if value not in allowed:
        raise ValidationError(
            f"Unsupported dimension '{value}'. Allowed values: {', '.join(sorted(allowed))}"
        )


def validate_olap_measure(value):
    import repo
    if value not in repo.OLAP_MEASURES:
        raise ValidationError(
            f"Unsupported measure '{value}'. Allowed values: "
            f"{', '.join(sorted(repo.OLAP_MEASURES))}"
        )


class SafeDateField(fields.Date):
    """DateField that serializes datetime.date, datetime.datetime, or pre-formatted ISO strings cleanly."""
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return super()._serialize(value, attr, obj, **kwargs)


# ---------- Error response schema ----------
class StdErrorSchema(Schema):
    message = fields.Str(required=True)
    code = fields.Int(required=False)
    status = fields.Str(required=False)


# ============================================================================
# Request Schemas (Query & Filter Arguments)
# ============================================================================

class req_FilterSchema(Schema):
    """Global filters applied across analytics and order endpoints."""
    customer_state = fields.Str(
        required=False,
        allow_none=True,
        metadata={"description": "2-letter customer state code, e.g., SP, RJ"}
    )
    seller_state = fields.Str(
        required=False,
        allow_none=True,
        metadata={"description": "2-letter seller state code, e.g., SP, PR"}
    )
    start_date = fields.Date(
        required=False,
        allow_none=True,
        metadata={"description": "Filter purchase date on or after YYYY-MM-DD"}
    )
    end_date = fields.Date(
        required=False,
        allow_none=True,
        metadata={"description": "Filter purchase date on or before YYYY-MM-DD"}
    )

    @validates_schema
    def validate_date_range(self, data, **kwargs):
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and start > end:
            raise ValidationError(
                "start_date must be before or equal to end_date",
                field_name="start_date"
            )


class req_LateTrendSchema(req_FilterSchema):
    """Query parameters for late delivery trend analytics."""
    granularity = fields.Str(
        load_default="month",
        validate=validate.OneOf(["month", "quarter", "year"]),
        metadata={"description": "Aggregation period granularity (month, quarter, or year)"}
    )


class req_OrdersQuerySchema(req_FilterSchema):
    """Query parameters for order drill-through with search and pagination."""
    search = fields.Str(
        required=False,
        allow_none=True,
        metadata={"description": "Search keyword for order_id"}
    )
    page = fields.Int(
        load_default=1,
        validate=validate.Range(min=1),
        metadata={"description": "Page number (1-based)"}
    )
    page_size = fields.Int(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={"description": "Number of records per page (max 100)"}
    )


class req_SellerQuerySchema(req_FilterSchema):
    """Query parameters for seller performance analytics."""
    limit = fields.Int(
        load_default=50,
        validate=validate.Range(min=1, max=500),
        metadata={"description": "Maximum number of sellers to return (default: 50)"}
    )
    sort_by = fields.Str(
        load_default="total_orders",
        validate=validate.OneOf(["total_orders", "avg_prep_time", "avg_score"]),
        metadata={"description": "Metric to sort sellers by"}
    )


class req_AlertsQuerySchema(req_FilterSchema):
    """Query parameters for operational alerts."""
    limit = fields.Int(
        load_default=50,
        validate=validate.Range(min=1, max=200),
        metadata={"description": "Maximum number of alerts to return (default: 50)"}
    )
    severity = fields.Str(
        required=False,
        validate=validate.OneOf(["ALL", "CRITICAL", "WARNING", "INFO"]),
        metadata={"description": "Filter alerts by severity level"}
    )


# ----------------------------------------------------------------------------
# OLAP Query Builder
# ----------------------------------------------------------------------------

class req_OlapFiltersSchema(Schema):
    """Multi-select filters for the OLAP query engine."""
    customer_states = fields.List(
        fields.Str(),
        load_default=list,
        metadata={"description": "Customer state codes; empty list means no filter"}
    )
    seller_states = fields.List(
        fields.Str(),
        load_default=list,
        metadata={"description": "Seller state codes; empty list means no filter"}
    )
    categories = fields.List(
        fields.Str(),
        load_default=list,
        metadata={"description": "Product category names; empty list means no filter"}
    )


class req_OlapQuerySchema(Schema):
    """Payload for the dynamic OLAP pivot/aggregation engine."""
    time_mode = fields.Str(
        load_default="month",
        validate=validate.OneOf(["month", "quarter", "year"]),
        metadata={"description": "Granularity of the time axis (month, quarter, year)"}
    )
    from_time = fields.Str(
        required=False,
        allow_none=True,
        validate=validate_period_format,
        metadata={"description": "Inclusive lower bound, YYYY-MM or YYYY-MM-DD"}
    )
    to_time = fields.Str(
        required=False,
        allow_none=True,
        validate=validate_period_format,
        metadata={"description": "Inclusive upper bound, YYYY-MM or YYYY-MM-DD"}
    )
    dimensions = fields.List(
        fields.Str(validate=validate_olap_dimension),
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "Dimension keys from the whitelist, e.g. Dim_Time.month"}
    )
    measures = fields.List(
        fields.Str(validate=validate_olap_measure),
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "Measure keys from the whitelist, e.g. total_orders"}
    )
    filters = fields.Nested(
        req_OlapFiltersSchema,
        required=False,
        load_default=dict,
        metadata={"description": "Multi-select filters"}
    )

    @validates_schema
    def validate_olap_range(self, data, **kwargs):
        validate_period_range(data)


# ----------------------------------------------------------------------------
# BI Dashboard overview
# ----------------------------------------------------------------------------

class req_OverviewSchema(Schema):
    """Query parameters for the BI dashboard overview."""
    time_mode = fields.Str(
        data_key="time_mode",
        load_default="month",
        validate=validate.OneOf(["month", "quarter", "year"]),
        metadata={"description": "Aggregation granularity (month, quarter, year)"}
    )
    from_time = fields.Str(
        data_key="from",
        required=False,
        allow_none=True,
        validate=validate_period_format,
        metadata={"description": "Inclusive lower bound, YYYY-MM or YYYY-MM-DD"}
    )
    to_time = fields.Str(
        data_key="to",
        required=False,
        allow_none=True,
        validate=validate_period_format,
        metadata={"description": "Inclusive upper bound, YYYY-MM or YYYY-MM-DD"}
    )
    customer_state = fields.Str(
        required=False,
        allow_none=True,
        metadata={"description": "2-letter customer state code, e.g. SP"}
    )
    seller_state = fields.Str(
        required=False,
        allow_none=True,
        metadata={"description": "2-letter seller state code, e.g. SP"}
    )

    @validates_schema
    def validate_overview_range(self, data, **kwargs):
        validate_period_range(data)


# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------

class req_LoginSchema(Schema):
    """Login credentials (plain text; this assignment does not require hashing)."""
    username = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        metadata={"description": "Account username (primary key of accounts table)"}
    )
    password = fields.Str(
        required=True,
        load_only=True,
        validate=validate.Length(min=1),
        metadata={"description": "Plain-text account password"}
    )


# ============================================================================
# Response Schemas
# ============================================================================

class res_HealthSchema(Schema):
    message = fields.Str(required=True)


class res_KpiSchema(Schema):
    order_count = fields.Int(required=True)
    delay_rate = fields.Float(required=True)
    complaint_rate = fields.Float(required=True)
    avg_delivery_time = fields.Float(required=True)
    avg_freight_cost = fields.Float(required=True)
    avg_score = fields.Float(required=True)


class res_StatesSchema(Schema):
    """Returns a list of unique state codes."""
    states = fields.List(fields.Str(), required=True)


class res_LateTrendSchema(Schema):
    """Data point in the late delivery trend timeline."""
    order_count = fields.Int(required=True, metadata={"description": "Total number of orders in period"})
    late_count = fields.Int(required=False, metadata={"description": "Number of late orders in period"})
    delay_rate = fields.Float(required=True, metadata={"description": "Ratio of late orders to total orders"})
    avg_delivery_time = fields.Float(required=True, metadata={"description": "Average total delivery time in days"})
    year = fields.Int(required=False, allow_none=True)
    month = fields.Int(required=False, allow_none=True)
    quarter = fields.Int(required=False, allow_none=True)


class res_SlaBreakdownSchema(Schema):
    """Breakdown of delivery stages in days."""
    avg_approval_time = fields.Float(required=True, metadata={"description": "Average approval time in days"})
    avg_prep_time = fields.Float(required=True, metadata={"description": "Average seller prep time in days"})
    avg_transit_time = fields.Float(required=True, metadata={"description": "Average carrier transit time in days"})
    avg_delivery_time = fields.Float(required=True, metadata={"description": "Average total delivery time in days"})


class res_OrderItemSchema(Schema):
    """Order detail row for drill-through view."""
    order_id = fields.Str(required=True)
    order_date = SafeDateField(required=False, allow_none=True)
    customer_state = fields.Str(required=False, allow_none=True)
    seller_state = fields.Str(required=False, allow_none=True)
    approval_time_days = fields.Float(required=False, allow_none=True)
    seller_prep_time_days = fields.Float(required=False, allow_none=True)
    carrier_transit_time_days = fields.Float(required=False, allow_none=True)
    total_delivery_time_days = fields.Float(required=False, allow_none=True)
    review_score = fields.Int(required=False, allow_none=True)
    is_late = fields.Bool(required=True)
    sla_status = fields.Str(required=True, metadata={"description": "Status text: 'late' or 'on_time'"})


class res_OrdersSchema(Schema):
    """Paginated list of orders."""
    total = fields.Int(required=True)
    page = fields.Int(required=True)
    page_size = fields.Int(required=True)
    total_pages = fields.Int(required=True)
    orders = fields.List(fields.Nested(res_OrderItemSchema), required=True)


class res_RegionSchema(Schema):
    """Regional route pair statistics."""
    seller_state = fields.Str(required=True)
    customer_state = fields.Str(required=True)
    order_count = fields.Int(required=True)
    late_count = fields.Int(required=True)
    late_rate = fields.Float(required=True)
    avg_delivery_time = fields.Float(required=True)


class res_SellerSchema(Schema):
    """Seller performance metrics."""
    seller_id = fields.Str(required=True, metadata={"description": "Unique seller identifier (UUID from Dim_Seller)"})
    seller_city = fields.Str(required=False, allow_none=True)
    seller_state = fields.Str(required=False, allow_none=True)
    total_orders = fields.Int(required=True)
    avg_prep_time = fields.Float(required=True)
    avg_score = fields.Float(required=True)


class res_AlertSchema(Schema):
    """Operational alert item."""
    id = fields.Str(required=True)
    type = fields.Str(required=True, metadata={"description": "Alert category (e.g. LOGISTICS_COMPLAINT, LATE_DELIVERY)"})
    severity = fields.Str(required=True, metadata={"description": "CRITICAL, WARNING, or INFO"})
    title = fields.Str(required=True)
    message = fields.Str(required=True)
    order_id = fields.Str(required=False, allow_none=True)
    order_date = SafeDateField(required=False, allow_none=True)
    customer_state = fields.Str(required=False, allow_none=True)
    seller_state = fields.Str(required=False, allow_none=True)
    metric_value = fields.Float(required=False, allow_none=True)


# ----------------------------------------------------------------------------
# OLAP Query Builder
# ----------------------------------------------------------------------------

class res_TimeRangeSchema(Schema):
    """Available month range in the warehouse."""
    min_month = fields.Str(required=False, allow_none=True, metadata={"description": "Earliest YYYY-MM in the fact table"})
    max_month = fields.Str(required=False, allow_none=True, metadata={"description": "Latest YYYY-MM in the fact table"})


class res_OlapMetadataSchema(Schema):
    """Filter values available to the OLAP query builder."""
    states = fields.List(fields.Str(), required=True, metadata={"description": "Distinct customer states"})
    categories = fields.List(fields.Str(), required=True, metadata={"description": "Distinct product categories"})
    seller_states = fields.List(fields.Str(), required=True, metadata={"description": "Distinct seller states (extension)"})
    time_range = fields.Nested(res_TimeRangeSchema, required=True)


class res_OlapQuerySchema(Schema):
    """Dynamic OLAP result: ordered column names and grouped rows."""
    columns = fields.List(fields.Str(), required=True)
    data = fields.List(fields.Dict(keys=fields.Str(), values=fields.Raw()), required=True)


# ----------------------------------------------------------------------------
# BI Dashboard overview
# ----------------------------------------------------------------------------

class res_OverviewSchema(Schema):
    """Six KPI cards plus a late-rate trend for the dashboard."""
    time_mode = fields.Str(required=True)
    from_time = fields.Str(required=False, allow_none=True)
    to_time = fields.Str(required=False, allow_none=True)
    customer_state = fields.Str(required=False, allow_none=True)
    seller_state = fields.Str(required=False, allow_none=True)
    kpis = fields.Nested(res_KpiSchema, required=True)
    late_trend = fields.List(fields.Nested(res_LateTrendSchema), required=True)


# ----------------------------------------------------------------------------
# Authentication
# ----------------------------------------------------------------------------

class res_LoginSchema(Schema):
    """Successful login result."""
    message = fields.Str(required=True)
    username = fields.Str(required=True)


class res_LogoutSchema(Schema):
    """Logout acknowledgement."""
    message = fields.Str(required=True)


class res_MeSchema(Schema):
    """Current session state."""
    authenticated = fields.Bool(required=True)
    username = fields.Str(required=False, allow_none=True)


# ============================================================================
# Aliases supporting both prefix and suffix naming conventions
# ============================================================================
Filter_req_Schema = req_FilterSchema
LateTrend_req_Schema = req_LateTrendSchema
OrdersQuery_req_Schema = req_OrdersQuerySchema
SellerQuery_req_Schema = req_SellerQuerySchema
AlertsQuery_req_Schema = req_AlertsQuerySchema
OlapQuery_req_Schema = req_OlapQuerySchema
OlapFilters_req_Schema = req_OlapFiltersSchema
Overview_req_Schema = req_OverviewSchema
Login_req_Schema = req_LoginSchema

Health_res_Schema = res_HealthSchema
Kpi_res_Schema = res_KpiSchema
States_res_Schema = res_StatesSchema
LateTrend_res_Schema = res_LateTrendSchema
SlaBreakdown_res_Schema = res_SlaBreakdownSchema
Orders_res_Schema = res_OrdersSchema
OrderItem_res_Schema = res_OrderItemSchema
Region_res_Schema = res_RegionSchema
Seller_res_Schema = res_SellerSchema
Alert_res_Schema = res_AlertSchema
TimeRange_res_Schema = res_TimeRangeSchema
OlapMetadata_res_Schema = res_OlapMetadataSchema
OlapQuery_res_Schema = res_OlapQuerySchema
Overview_res_Schema = res_OverviewSchema
Login_res_Schema = res_LoginSchema
Logout_res_Schema = res_LogoutSchema
Me_res_Schema = res_MeSchema
