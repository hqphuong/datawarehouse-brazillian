-- Performance indexes required by the OLAP API specification (PHẦN 4, item 2).
-- Safe to re-run: every statement is idempotent.

-- Foreign keys on Fact_Delivery_SLA used by SELECT ... JOIN ... GROUP BY.
CREATE INDEX IF NOT EXISTS idx_fact_sla_time_id
    ON fact_delivery_sla (time_id);

CREATE INDEX IF NOT EXISTS idx_fact_sla_customer_location_id
    ON fact_delivery_sla (customer_location_id);

CREATE INDEX IF NOT EXISTS idx_fact_sla_seller_location_id
    ON fact_delivery_sla (seller_location_id);

CREATE INDEX IF NOT EXISTS idx_fact_sla_product_id
    ON fact_delivery_sla (product_id);

-- Extra index used by seller joins/filters (Dim_Seller.seller_id).
CREATE INDEX IF NOT EXISTS idx_fact_sla_seller_id
    ON fact_delivery_sla (seller_id);

-- Dimension columns frequently used for multi-select filters.
CREATE INDEX IF NOT EXISTS idx_dim_location_state
    ON dim_location (state);

CREATE INDEX IF NOT EXISTS idx_dim_seller_state
    ON dim_seller (state);

CREATE INDEX IF NOT EXISTS idx_dim_product_category
    ON dim_product (category_name_english);
