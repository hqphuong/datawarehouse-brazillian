"""Test cho module dự báo nguy cơ giao trễ ``etl/dss_ml.py``."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from etl import dss_ml as ML


@pytest.fixture(scope="module")
def o():
    return ML.load_orders()


# --------------------------------------------------------------------------- #
#  Đặc trưng: không rò rỉ
# --------------------------------------------------------------------------- #
def test_feature_columns_exclude_forbidden_features():
    """Danh sách đặc trưng không giao với danh sách cột bị cấm."""
    assert set(ML.FEATURE_COLUMNS).isdisjoint(ML.FORBIDDEN_FEATURES)


def test_prepare_features_drops_forbidden_columns():
    """Kể cả khi đầu vào có cột rò rỉ, prepare_features phải loại bỏ chúng."""
    frame = pd.DataFrame(
        {
            "seller_state": ["SP", "RJ"],
            "cust_state": ["RJ", "SP"],
            "category": ["health_beauty", "auto"],
            "payment_type": ["credit_card", "voucher"],
            "approval": [0.5, 1.0],
            "prep": [2.0, -1.0],  # giá trị âm phải được giữ nguyên
            "freight": [10.0, 20.0],
            "weight": [500.0, 1000.0],
            "volume": [1000.0, 2000.0],
            "n_items": [1, 2],
            # Các cột bị cấm — phải bị loại bỏ:
            "transit": [3.0, 4.0],
            "delay_days": [1.0, -2.0],
            "is_late": [True, False],
            "review_score": [1, 5],
            "complaint": [True, False],
            "period": [201801, 201802],
        }
    )

    prepared = ML.prepare_features(frame)

    assert list(prepared.columns) == ML.FEATURE_COLUMNS
    assert set(prepared.columns).isdisjoint(ML.FORBIDDEN_FEATURES)
    # Không được clip giá trị âm của prep.
    assert prepared["prep"].tolist() == [2.0, -1.0]


# --------------------------------------------------------------------------- #
#  Chia dữ liệu theo thời gian: không chồng kỳ, đúng thứ tự
# --------------------------------------------------------------------------- #
def test_time_split_has_no_overlap_and_is_chronological(o):
    """Train/test chia theo kỳ, không chồng lấn và train đứng trước test."""
    train, test, cutoff = ML.time_split(o)

    assert set(train["period"].unique()).isdisjoint(test["period"].unique())
    assert train["period"].max() < test["period"].min()
    assert test["period"].min() == cutoff
    assert train["period"].max() < cutoff

    n_periods = o["period"].nunique()
    expected_test = max(1, math.ceil(n_periods * ML.TEST_FRACTION))
    assert test["period"].nunique() == expected_test
    assert train["period"].nunique() + test["period"].nunique() == n_periods
    assert set(train["period"].unique()) | set(test["period"].unique()) == set(
        o["period"].unique()
    )


def test_train_validation_split_has_no_overlap_and_is_chronological(o):
    """fit/validation tách theo thời gian, không chồng kỳ, fit đứng trước."""
    train, _, _ = ML.time_split(o)
    fit, validation, cutoff = ML.train_validation_split(train)

    assert set(fit["period"].unique()).isdisjoint(validation["period"].unique())
    assert fit["period"].max() < validation["period"].min()
    assert validation["period"].min() == cutoff
    assert fit["period"].max() < cutoff

    assert set(fit["period"].unique()) | set(validation["period"].unique()) == set(
        train["period"].unique()
    )


# --------------------------------------------------------------------------- #
#  Dự báo: xác suất hợp lệ, lưu/nạp cho cùng kết quả
# --------------------------------------------------------------------------- #
def _small_model(o):
    """Huấn luyện nhanh một Logistic Regression trên mẫu nhỏ, đủ hai lớp."""
    train, _, _ = ML.time_split(o)
    sample = train.sample(n=800, random_state=42)
    assert sample[ML.TARGET].nunique() == 2

    model = ML.build_logistic()
    model.fit(ML.prepare_features(sample), sample[ML.TARGET].astype(int))
    return model, sample


def test_model_feature_names_have_no_forbidden_features(o):
    """Bộ mã hoá one-hot của mô hình không chứa bất kỳ đặc trưng bị cấm nào."""
    model, _ = _small_model(o)
    names = model.named_steps["prep"].get_feature_names_out()
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ML.FORBIDDEN_FEATURES
    )


def test_save_load_and_predict_are_identical(o, tmp_path):
    """Lưu rồi nạp lại mô hình cho cùng xác suất; xác suất nằm trong [0, 1]."""
    model, sample = _small_model(o)
    head = sample.head(20)
    x_head = ML.prepare_features(head)

    predictions_before = model.predict_proba(x_head)[:, 1]
    assert np.all(predictions_before >= 0.0)
    assert np.all(predictions_before <= 1.0)

    bundle = {
        "model": model,
        "model_name": "logistic_regression",
        "threshold": 0.5,
        "features": {
            "categorical": ML.CATEGORICAL_FEATURES,
            "numeric": ML.NUMERIC_FEATURES,
            "forbidden": ML.FORBIDDEN_FEATURES,
        },
        "split": {"cutoff_period": int(head["period"].max())},
        "metrics": {},
    }
    path = tmp_path / "late_risk.joblib"

    ML.save_model(bundle, path)
    ML.clear_model_cache(path)
    assert path.is_file()

    loaded = ML.load_model(path)
    predictions_loaded = loaded["model"].predict_proba(x_head)[:, 1]
    np.testing.assert_allclose(predictions_loaded, predictions_before)

    # predict_orders đi qua đúng hàm nạp + tiền xử lý.
    probabilities = ML.predict_orders(head, path=path)
    np.testing.assert_allclose(probabilities, predictions_before)
    assert probabilities.shape == (20,)
    assert np.all(np.isfinite(probabilities))
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)

    ML.clear_model_cache(path)


def test_predict_missing_model_raises_clear_error(o, tmp_path):
    """Chưa có file mô hình phải báo lỗi rõ ràng (để API trả 503)."""
    missing = tmp_path / "khong_ton_tai.joblib"
    with pytest.raises(FileNotFoundError, match="Chưa có mô hình"):
        ML.predict_orders(o.head(1), path=missing)


# --------------------------------------------------------------------------- #
#  JSON chỉ số: đủ các khoá của mục 0a
# --------------------------------------------------------------------------- #
def test_metrics_json_has_required_keys():
    """JSON chỉ số phải có số dòng/tỷ lệ trễ từng tập, ngưỡng, precision@K."""
    assert ML.METRICS_PATH.is_file(), (
        "Thiếu data/models/late_risk_metrics.json; hãy chạy etl/dss_ml.py"
    )
    payload = json.loads(ML.METRICS_PATH.read_text(encoding="utf-8"))

    assert payload["sklearn_version"]
    assert payload["primary_model"] == "logistic_regression"

    data = payload["data"]
    for key in (
        "fit_rows",
        "validation_rows",
        "train_rows",
        "final_train_rows",
        "test_rows",
        "fit_late_rate",
        "validation_late_rate",
        "train_late_rate",
        "test_late_rate",
        "overall_late_rate",
    ):
        assert key in data, key
    assert data["final_training_set"] == "fit+validation"
    # Mô hình cuối huấn luyện trên fit + validation.
    assert data["final_train_rows"] == data["fit_rows"] + data["validation_rows"]
    assert data["train_rows"] == data["final_train_rows"]

    threshold = payload["threshold_selection"]
    assert threshold["selected_on"] == "validation"
    assert threshold["criterion"] == "max F1"
    assert 0.0 <= threshold["value"] <= 1.0

    # precision@K / lift@K cho cả 4 mô hình (LR, RF, 2 baseline).
    for name in ("logistic_regression", "random_forest"):
        rows = payload["models"][name]["precision_at_k"]
        assert [row["k_fraction"] for row in rows] == list(ML.PRECISION_AT_K)
        for row in rows:
            assert 0.0 <= row["precision_at_k"] <= 1.0
            assert row["lift_at_k"] >= 0.0
    for name in ("always_on_time", "route_historical_rate"):
        rows = payload["baselines"][name]["precision_at_k"]
        assert [row["k_fraction"] for row in rows] == list(ML.PRECISION_AT_K)

    lr = payload["models"]["logistic_regression"]
    assert lr["coefficient_min_support"] == ML.MIN_SUPPORT
    assert lr["top_coefficients"]
    assert all(row["support"] >= ML.MIN_SUPPORT for row in lr["top_coefficients"])
    assert all(
        row["support"] < ML.MIN_SUPPORT for row in lr["low_support_coefficients"]
    )
    assert [row["feature"] for row in lr["numeric_coefficients"]] == (
        ML.NUMERIC_FEATURES
    )
    assert all(
        row["support"] is None and row["support_applicable"] is False
        for row in lr["numeric_coefficients"]
    )
