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


def normalize_location_id(values: pd.Series, column: str) -> pd.Series:
    """Chuẩn hoá zip prefix về 5 ký tự, không bao giờ biến NaN thành ``"00nan"``.

    ``Series.astype(str).str.zfill(5)`` biến ``NaN`` thành chuỗi ``"nan"`` rồi
    thành ``"00nan"`` (đủ 5 ký tự nên lọt qua kiểm tra độ dài). Hàm này chặn
    trường hợp đó bằng lỗi rõ ràng trước khi zfill.
    """
    missing = values.isna()
    if missing.any():
        raise ValueError(
            f"{column} thiếu giá trị ở {int(missing.sum())} dòng; "
            "không thể zfill vì sẽ tạo '00nan'. "
            f"Index mẫu: {values.loc[missing].head(5).index.tolist()}"
        )

    normalized = values.astype(str).str.zfill(5)
    bad_len = normalized.str.len() != 5
    if bad_len.any():
        raise ValueError(
            f"{column} không đủ 5 ký tự sau khi zfill: {int(bad_len.sum())} dòng "
            f"{normalized.loc[bad_len].head(5).tolist()}"
        )
    return normalized


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
