"""Quy tắc chọn bản ghi suy biến cho Fact_Delivery_SLA.

Tách khỏi script ETL (script chạy ngay khi import) để kiểm thử được bằng
pytest mà không cần đọc/ghi CSV.
"""

from __future__ import annotations

import pandas as pd


def select_payment_type(payments: pd.DataFrame) -> pd.DataFrame:
    """Chọn 1 payment_type cho mỗi đơn.

    Quy tắc: loại có **tổng** ``payment_value`` lớn nhất; hòa thì loại có
    ``payment_sequential`` nhỏ nhất; vẫn hòa thì theo tên loại (A→Z) để kết
    quả tất định.
    """
    totals = (
        payments.groupby(["order_id", "payment_type"], as_index=False)
        .agg(
            total_value=("payment_value", "sum"),
            min_seq=("payment_sequential", "min"),
        )
        .sort_values(
            ["order_id", "total_value", "min_seq", "payment_type"],
            ascending=[True, False, True, True],
        )
    )
    return totals.drop_duplicates("order_id", keep="first")[
        ["order_id", "payment_type"]
    ].reset_index(drop=True)


def select_latest_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Chọn 1 review cho mỗi đơn.

    Quy tắc: mới nhất theo ``review_creation_date``; hòa thì theo
    ``review_answer_timestamp``; vẫn hòa thì theo ``review_id`` (lớn hơn).
    """
    frame = reviews.copy()
    frame["review_creation_date"] = pd.to_datetime(frame["review_creation_date"])
    frame["review_answer_timestamp"] = pd.to_datetime(
        frame["review_answer_timestamp"]
    )
    return (
        frame.sort_values(
            [
                "order_id",
                "review_creation_date",
                "review_answer_timestamp",
                "review_id",
            ]
        )
        .drop_duplicates("order_id", keep="last")
        .reset_index(drop=True)
    )
