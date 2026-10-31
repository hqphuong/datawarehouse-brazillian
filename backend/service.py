from schema import StdResponse
import repo

def health_check() -> StdResponse:
    return StdResponse(True, "I love Kasane Teto")

def count_orders() -> StdResponse:
    count = repo.count_orders()
    return StdResponse(True, count)

def count_orders_by_date(product_id: str) -> StdResponse:
    return StdResponse(True, repo.count_orders_by_date(product_id))