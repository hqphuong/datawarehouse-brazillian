from pathlib import Path

import pandas as pd
import pytest

from etl.config import WAREHOUSE_TABLES, get_db_config

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


def _read(name, **kwargs):
    return pd.read_csv(PROC / name, **kwargs)


def test_dim_seller_contract():
    sellers = _read("cleaned_dim_seller.csv", dtype={"seller_id": str, "location_id": str})
    locations = _read("cleaned_dim_location.csv", dtype={"location_id": str})
    assert list(sellers.columns) == ["seller_id", "location_id", "city", "state"]
    assert not sellers["seller_id"].duplicated().any()
    assert (sellers["location_id"].str.len() == 5).all()
    assert sellers["location_id"].isin(locations["location_id"]).all()


def test_fact_has_d2_columns_and_values():
    fact = _read(
        "cleaned_fact_orders.csv",
        dtype={"customer_location_id": str, "seller_location_id": str},
    )
    required = {
        "seller_id",
        "price",
        "shipping_limit_date",
        "promise_days",
        "total_lead_days",
        "distance_km",
    }
    assert required <= set(fact.columns)
    assert fact["price"].notna().all()
    assert fact["shipping_limit_date"].notna().all()
    assert (fact["promise_days"] - (fact["total_lead_days"] - fact["delay_days"])).abs().max() < 1e-9
    assert (fact["distance_km"].dropna() >= 0).all()
    assert (fact.loc[fact["distance_km"].notna(), "distance_km"] <= 20000).all()


def test_processed_csv_counts_match_loaded_postgresql_tables():
    """C10: CSV (nguồn backend đọc) và bảng PostgreSQL đã nạp phải cùng số dòng."""
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        conn = psycopg2.connect(**get_db_config(), connect_timeout=5)
    except Exception as exc:  # DB không chạy / thiếu .env
        pytest.skip(f"PostgreSQL không sẵn sàng: {exc}")

    try:
        with conn.cursor() as cur:
            for table, csv_path in WAREHOUSE_TABLES.items():
                csv_rows = len(_read(csv_path.name))
                cur.execute(f'SELECT COUNT(*) FROM "{table.lower()}"')
                db_rows = int(cur.fetchone()[0])
                assert db_rows == csv_rows, (
                    f"{table}: CSV {csv_rows} dòng nhưng PostgreSQL {db_rows} dòng"
                )
    finally:
        conn.close()


def test_fact_location_fks_are_zfilled_and_covered():
    fact = _read(
        "cleaned_fact_orders.csv",
        dtype={"customer_location_id": str, "seller_location_id": str},
    )
    locations = _read("cleaned_dim_location.csv", dtype={"location_id": str})
    sellers = _read("cleaned_dim_seller.csv", dtype={"seller_id": str})
    for col in ("customer_location_id", "seller_location_id"):
        assert (fact[col].str.len() == 5).all()
        assert fact[col].isin(locations["location_id"]).all()
    assert fact["seller_id"].isin(sellers["seller_id"]).all()
