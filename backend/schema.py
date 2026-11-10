from marshmallow import Schema, fields, validate, validates_schema, ValidationError


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


# ============================================================================
# Aliases supporting both prefix and suffix naming conventions
# ============================================================================
Filter_req_Schema = req_FilterSchema
LateTrend_req_Schema = req_LateTrendSchema
OrdersQuery_req_Schema = req_OrdersQuerySchema
SellerQuery_req_Schema = req_SellerQuerySchema
AlertsQuery_req_Schema = req_AlertsQuerySchema

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
