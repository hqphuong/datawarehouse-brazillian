import pandas as pd
import pytest

from etl.transform_rules import (
    normalize_location_id,
    select_latest_reviews,
    select_payment_type,
)


def _payments(rows):
    return pd.DataFrame(rows, columns=["order_id", "payment_type", "payment_value", "payment_sequential"])


def test_payment_type_is_max_summed_value():
    out = select_payment_type(
        _payments(
            [
                ("A", "credit_card", 10.0, 1),
                ("A", "voucher", 15.0, 2),
            ]
        )
    ).set_index("order_id")
    assert out.loc["A", "payment_type"] == "voucher"


def test_payment_type_tie_uses_lowest_sequential():
    out = select_payment_type(
        _payments(
            [
                ("B", "credit_card", 10.0, 1),
                ("B", "voucher", 10.0, 2),
            ]
        )
    ).set_index("order_id")
    assert out.loc["B", "payment_type"] == "credit_card"


def test_payment_type_sums_rows_of_same_type():
    out = select_payment_type(
        _payments(
            [
                ("C", "voucher", 4.0, 1),
                ("C", "voucher", 4.0, 2),
                ("C", "credit_card", 7.0, 3),
            ]
        )
    ).set_index("order_id")
    assert out.loc["C", "payment_type"] == "voucher"


def test_normalize_location_id_pads_to_five():
    out = normalize_location_id(pd.Series(["1037", "01037", "95010"]), "zip")
    assert out.tolist() == ["01037", "01037", "95010"]


def test_normalize_location_id_rejects_missing_before_zfill():
    values = pd.Series(["1037", None, "95010"], name="zip")
    with pytest.raises(ValueError, match="00nan"):
        normalize_location_id(values, "zip")


def test_normalize_location_id_rejects_wrong_length():
    with pytest.raises(ValueError, match="không đủ 5 ký tự"):
        normalize_location_id(pd.Series(["123456"]), "zip")


def test_review_latest_creation_date_wins():
    out = select_latest_reviews(
        pd.DataFrame(
            [
                ("X", "r1", "2018-01-01", "2018-02-01", 1),
                ("X", "r2", "2018-01-02", "2018-01-03", 2),
            ],
            columns=[
                "order_id",
                "review_id",
                "review_creation_date",
                "review_answer_timestamp",
                "review_score",
            ],
        )
    ).set_index("order_id")
    assert out.loc["X", "review_id"] == "r2"


def test_review_tie_creation_uses_answer_timestamp_then_id():
    out = select_latest_reviews(
        pd.DataFrame(
            [
                ("Y", "r1", "2018-01-01", "2018-02-01", 1),
                ("Y", "r2", "2018-01-01", "2018-03-01", 2),
                ("Z", "a", "2018-01-01", "2018-02-01", 1),
                ("Z", "b", "2018-01-01", "2018-02-01", 2),
            ],
            columns=[
                "order_id",
                "review_id",
                "review_creation_date",
                "review_answer_timestamp",
                "review_score",
            ],
        )
    ).set_index("order_id")
    assert out.loc["Y", "review_id"] == "r2"
    assert out.loc["Z", "review_id"] == "b"
