from router import db
from sqlalchemy import text

def count_orders():
    sql = text("SELECT COUNT(order_id) FROM fact_delivery_sla")
    result = db.session.execute(sql)
    count = [row.count for row in result]
    return count[0]

def count_orders_by_date(product_id) -> list[dict]:
    sql = text(f"SELECT time_id, count(product_id) FROM fact_delivery_sla WHERE product_id='{product_id}'GROUP BY time_id ORDER BY time_id DESC")
    result = db.session.execute(sql)
    return [{"time": row.time_id, "count": row.count} for row in result]
