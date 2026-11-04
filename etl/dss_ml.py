"""Dự báo đơn hàng có nguy cơ giao trễ tại thời điểm giao cho vận chuyển.

Phạm vi (Bước 6 - Giai đoạn ML)
-------------------------------
Chỉ dùng các thông tin *đã biết* tại thời điểm đơn hàng được giao cho đơn vị
vận chuyển. Các cột phát sinh sau thời điểm đó (transit, delay_days, is_late,
review_score, complaint, period) bị cấm làm đặc trưng vì gây rò rỉ dữ liệu.

Đặc trưng
---------
- Phân loại: ``seller_state``, ``cust_state``, ``category``, ``payment_type``.
- Số: ``approval``, ``prep``, ``freight``, ``weight``, ``volume``, ``n_items``.

Xử lý giá trị thiếu / âm
------------------------
- Giá trị phân loại thiếu: điền ``"unknown"`` (fit trên tập huấn luyện).
- Giá trị số thiếu: điền median fit trên tập huấn luyện.
- **Không** cắt/clip giá trị âm. Đặc biệt ``prep`` có 1.361 dòng âm trong dữ
  liệu gốc; các giá trị này được giữ nguyên như yêu cầu.

Chia dữ liệu
------------
- Chia theo thời gian, không chia ngẫu nhiên.
- Tập kiểm tra = ~20% số kỳ cuối (mặc định 5/23 kỳ: 201804..201808). Kỳ cắt
  được lưu trong JSON và bundle mô hình.
- Trong tập huấn luyện, dành ~20% số kỳ cuối làm validation để chọn ngưỡng.
  Ngưỡng **không** được chọn trên tập kiểm tra.

Mô hình
-------
- Chính: Logistic Regression (``class_weight="balanced"``).
- So sánh: Random Forest nhỏ.
- Baseline: (i) luôn dự báo đúng hạn; (ii) tỷ lệ trễ lịch sử của tuyến trong
  giai đoạn huấn luyện.

Chạy huấn luyện::

    .\\backend\\env\\Scripts\\python.exe etl\\dss_ml.py

Kết quả: ``data/models/late_risk.joblib`` và
``data/models/late_risk_metrics.json``.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:  # chạy như package: python -m etl.dss_ml
    from .config import PROJECT_ROOT
    from .dss_models import load_orders
except ImportError:  # chạy trực tiếp: python etl/dss_ml.py
    from config import PROJECT_ROOT
    from dss_models import load_orders

# --------------------------------------------------------------------------- #
#  Hằng số
# --------------------------------------------------------------------------- #
CATEGORICAL_FEATURES = ["seller_state", "cust_state", "category", "payment_type"]
NUMERIC_FEATURES = ["approval", "prep", "freight", "weight", "volume", "n_items"]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Các cột bị cấm làm đặc trưng (rò rỉ thông tin hoặc không có tại thời điểm
# giao cho vận chuyển).
FORBIDDEN_FEATURES = [
    "transit",
    "delay_days",
    "is_late",
    "review_score",
    "complaint",
    "period",
]

TARGET = "is_late"
RANDOM_STATE = 42
TEST_FRACTION = 0.20
VALIDATION_FRACTION = 0.20

# Ngưỡng support tối thiểu để một hệ số được xếp hạng/diễn giải.
# Lý do: hệ số của nhóm rất ít mẫu (vài chục đơn) thường dao động mạnh và
# không đại diện cho hành vi chung. 200 đơn là mức tối thiểu để một giá trị
# phân loại có đủ quan sát cho một hệ số ổn định trong dữ liệu ~97 nghìn dòng.
MIN_SUPPORT = 200
# Các mốc K cho precision@K / lift@K trên tập kiểm tra (tỷ lệ số đơn xếp cao nhất).
PRECISION_AT_K = (0.01, 0.05, 0.10)

MODEL_DIR = PROJECT_ROOT / "data" / "models"
MODEL_PATH = MODEL_DIR / "late_risk.joblib"
METRICS_PATH = MODEL_DIR / "late_risk_metrics.json"

_MODEL_CACHE: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
#  Chia dữ liệu theo thời gian
# --------------------------------------------------------------------------- #
def time_split(
    o: pd.DataFrame, test_fraction: float = TEST_FRACTION
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Chia theo kỳ: các kỳ đầu để huấn luyện, ~``test_fraction`` kỳ cuối để kiểm tra.

    Trả về ``(train, test, cutoff_period)``. ``cutoff_period`` là kỳ đầu tiên
    thuộc tập kiểm tra.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction phải nằm trong khoảng (0, 1)")

    periods = sorted(int(p) for p in o["period"].dropna().unique())
    if len(periods) < 2:
        raise ValueError("cần ít nhất 2 kỳ dữ liệu để chia train/test")

    n_test = max(1, math.ceil(len(periods) * test_fraction))
    cutoff = periods[-n_test]
    train = o[o["period"] < cutoff].copy()
    test = o[o["period"] >= cutoff].copy()
    return train, test, int(cutoff)


def train_validation_split(
    train: pd.DataFrame, validation_fraction: float = VALIDATION_FRACTION
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Tách tập huấn luyện thành fit/validation theo thời gian (kỳ cuối làm validation)."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction phải nằm trong khoảng (0, 1)")

    periods = sorted(int(p) for p in train["period"].dropna().unique())
    if len(periods) < 2:
        raise ValueError("cần ít nhất 2 kỳ huấn luyện để tách validation")

    n_val = max(1, math.ceil(len(periods) * validation_fraction))
    cutoff = periods[-n_val]
    fit = train[train["period"] < cutoff].copy()
    validation = train[train["period"] >= cutoff].copy()
    return fit, validation, int(cutoff)


# --------------------------------------------------------------------------- #
#  Tiền xử lý & mô hình
# --------------------------------------------------------------------------- #
def build_preprocessor() -> ColumnTransformer:
    """Tạo bộ tiền xử lý: one-hot cho phân loại, median + scale cho số."""
    categorical = Pipeline(
        steps=[
            (
                "impute",
                SimpleImputer(strategy="constant", fill_value="unknown"),
            ),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    numeric = Pipeline(
        steps=[
            (
                "impute",
                SimpleImputer(strategy="median", keep_empty_features=True),
            ),
            ("scale", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("cat", categorical, CATEGORICAL_FEATURES),
            ("num", numeric, NUMERIC_FEATURES),
        ]
    )


def build_logistic() -> Pipeline:
    """Mô hình chính: Logistic Regression cân bằng lớp."""
    return Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=3000,
                    solver="lbfgs",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def build_tree() -> Pipeline:
    """Mô hình so sánh: Random Forest nhỏ, cân bằng lớp."""
    return Pipeline(
        steps=[
            ("prep", build_preprocessor()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=12,
                    min_samples_leaf=25,
                    max_features="sqrt",
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def prepare_features(o: pd.DataFrame | Iterable[dict]) -> pd.DataFrame:
    """Chỉ giữ đúng các đặc trưng được phép, bổ sung cột thiếu bằng NaN.

    Hàm này cũng là lớp bảo vệ chống rò rỉ: các cột như ``transit``,
    ``delay_days``, ``is_late``... nếu có trong đầu vào sẽ bị loại bỏ.
    """
    if isinstance(o, pd.DataFrame):
        frame = o.copy()
    elif isinstance(o, dict):
        frame = pd.DataFrame([o])
    else:
        frame = pd.DataFrame(list(o))

    for column in FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
    return frame[FEATURE_COLUMNS]


# --------------------------------------------------------------------------- #
#  Ngưỡng & chỉ số
# --------------------------------------------------------------------------- #
def best_threshold(y_true, proba) -> float:
    """Chọn ngưỡng tối đa hoá F1 trên tập huấn luyện/validation.

    Không bao giờ được gọi với tập kiểm tra. Hòa F1 thì chọn ngưỡng gần 0.5
    nhất để ổn định.
    """
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba, dtype=float)
    if len(np.unique(y_true)) < 2:
        return 0.5

    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    if len(thresholds) == 0:
        return 0.5

    precision = precision[:-1]
    recall = recall[:-1]
    denominator = precision + recall
    f1 = np.divide(
        2 * precision * recall,
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator > 0,
    )
    best = float(np.max(f1))
    candidates = np.flatnonzero(np.isclose(f1, best))
    index = candidates[np.argmin(np.abs(thresholds[candidates] - 0.5))]
    return float(thresholds[index])


def _metrics(
    y_true,
    proba,
    threshold: float,
    *,
    constant_score: bool = False,
) -> dict:
    """Tính chỉ số trên một tập bất kỳ (chỉ gọi với validation/test)."""
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba, dtype=float)
    y_pred = (proba >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    if len(np.unique(y_true)) < 2:
        roc_auc = None
    elif constant_score:
        roc_auc = None
    else:
        roc_auc = float(roc_auc_score(y_true, proba))

    if len(np.unique(y_true)) < 2:
        pr_auc = None
    else:
        pr_auc = float(average_precision_score(y_true, proba))
        if constant_score:
            # Với điểm số hằng, AP bằng tỷ lệ lớp dương (prevalence).
            pr_auc = float(y_true.mean())

    return {
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
        "prevalence": float(y_true.mean()) if len(y_true) else None,
        "threshold": float(threshold),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "accuracy": float((y_pred == y_true).mean()) if len(y_true) else None,
        "predicted_positives": int(y_pred.sum()),
        "confusion_matrix": {
            "labels": [0, 1],
            "matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def precision_at_k(
    y_true,
    proba,
    fractions: Iterable[float] = PRECISION_AT_K,
    *,
    constant_score: bool = False,
) -> list[dict]:
    """Precision@K và lift@K: K là tỷ lệ số đơn được xếp điểm cao nhất.

    ``precision@K`` = tỷ lệ đơn trễ thật trong K% đơn có điểm cao nhất.
    ``lift@K`` = precision@K / tỷ lệ trễ nền của chính tập đang xét.
    Đây là chỉ số vận hành: nếu chỉ đủ nguồn lực rà soát K% đơn, nhóm đó
    chứa bao nhiêu đơn trễ thật so với chọn ngẫu nhiên.

    Với điểm số hằng (``constant_score=True``), việc chọn K% đơn đầu là ngẫu
    nhiên, nên precision@K = tỷ lệ trễ nền và lift@K = 1.
    """
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba, dtype=float)
    n = len(y_true)
    if n == 0:
        return []

    prevalence = float(y_true.mean())
    # Thứ tự giảm dần theo điểm; ổn định khi hòa điểm.
    order = np.argsort(-proba, kind="stable")
    rows = []
    for fraction in fractions:
        k = max(1, int(math.ceil(n * fraction)))
        if constant_score:
            precision = prevalence
            positives = int(round(k * prevalence))
            lift = 1.0 if prevalence > 0 else None
        else:
            top = y_true[order[:k]]
            precision = float(top.mean())
            positives = int(top.sum())
            lift = float(precision / prevalence) if prevalence > 0 else None
        rows.append(
            {
                "k_fraction": float(fraction),
                "k": int(k),
                "positives_in_top_k": positives,
                "precision_at_k": precision,
                "lift_at_k": lift,
                "prevalence": prevalence,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
#  Baseline
# --------------------------------------------------------------------------- #
def _route_series(frame: pd.DataFrame) -> pd.Series:
    """Lấy tuyến; nếu thiếu cột ``route`` thì ghép từ bang người bán/khách."""
    if "route" in frame.columns:
        return frame["route"].astype("string").fillna("unknown")
    seller = frame["seller_state"].astype("string").fillna("unknown")
    customer = frame["cust_state"].astype("string").fillna("unknown")
    return seller + "->" + customer


def route_rate_scores(
    frame: pd.DataFrame,
    rates: pd.Series,
    fallback: float,
) -> np.ndarray:
    """Điểm số baseline = tỷ lệ trễ lịch sử của tuyến (fallback: tỷ lệ chung)."""
    scores = _route_series(frame).map(rates)
    return scores.fillna(fallback).to_numpy(dtype=float)


# --------------------------------------------------------------------------- #
#  Hệ số / độ quan trọng
# --------------------------------------------------------------------------- #
def _clean_feature_name(name: str) -> str:
    return name.replace("num__", "").replace("cat__", "")


def _feature_support(model: Pipeline, frame: pd.DataFrame) -> dict[str, int]:
    """Số đơn huấn luyện (support) ứng với từng đặc trưng sau one-hot.

    - Giá trị phân loại: số dòng trong tập huấn luyện có giá trị đó (thiếu
      được tính vào ``"unknown"``, khớp với bước điền khuyết).
    - Đặc trưng số: số dòng không rỗng của cột đó.
    """
    prep = model.named_steps["prep"]
    support: dict[str, int] = {}
    n_rows = len(frame)

    for name, transformer, columns in prep.transformers_:
        if transformer == "drop" or transformer is None:
            continue
        columns = [columns] if isinstance(columns, str) else list(columns)

        if name == "cat":
            encoder = transformer.named_steps["onehot"]
            for column, categories in zip(columns, encoder.categories_):
                if column in frame.columns:
                    values = frame[column].astype("string").fillna("unknown")
                else:
                    values = pd.Series(["unknown"] * n_rows, dtype="string")
                counts = values.value_counts()
                for category in categories:
                    support[f"{column}_{category}"] = int(counts.get(category, 0))
        elif name == "num":
            for column in columns:
                support[column] = (
                    int(frame[column].notna().sum())
                    if column in frame.columns
                    else 0
                )
    return support


def _coefficient_rows(
    model: Pipeline, support: dict[str, int] | None
) -> list[dict]:
    """Toàn bộ hệ số Logistic Regression kèm support, sắp theo |hệ số| giảm dần."""
    names = model.named_steps["prep"].get_feature_names_out()
    coefficients = model.named_steps["clf"].coef_[0]
    rows = []
    for name, value in zip(names, coefficients):
        feature = _clean_feature_name(str(name))
        rows.append(
            {
                "feature": feature,
                "coefficient": float(value),
                "support": (
                    int(support[feature])
                    if support is not None and feature in support
                    else None
                ),
            }
        )
    rows.sort(key=lambda row: abs(row["coefficient"]), reverse=True)
    return rows


def logistic_coefficients(
    model: Pipeline,
    support: dict[str, int] | None = None,
    top: int = 10,
    min_support: int = MIN_SUPPORT,
) -> list[dict]:
    """Top hệ số Logistic Regression **có support đủ lớn**.

    Chỉ xếp hạng/diễn giải các đặc trưng có support >= ``min_support``.
    Nếu ``support=None`` (dùng cho kiểm thử nhỏ) thì trả về tất cả.
    """
    rows = _coefficient_rows(model, support)
    if support is not None:
        rows = [
            row
            for row in rows
            if row["support"] is not None and row["support"] >= min_support
        ]
    return rows[:top]


def low_support_coefficients(
    model: Pipeline,
    support: dict[str, int],
    top: int = 10,
    min_support: int = MIN_SUPPORT,
) -> list[dict]:
    """Hệ số của các nhóm ít mẫu (support < ngưỡng) — chỉ để minh bạch, không diễn giải."""
    rows = _coefficient_rows(model, support)
    rows = [
        row
        for row in rows
        if row["support"] is not None and row["support"] < min_support
    ]
    return rows[:top]


def numeric_coefficients(model: Pipeline) -> list[dict]:
    """Hệ số Logistic Regression của các đặc trưng số, theo đúng thứ tự khai báo.

    Các đặc trưng số đã được ``StandardScaler`` chuẩn hoá, nên hệ số đọc là
    thay đổi log-odds khi tăng 1 độ lệch chuẩn của đặc trưng đó. Support không
    áp dụng cho đặc trưng số (mọi dòng đều có giá trị sau khi điền median).
    """
    names = list(model.named_steps["prep"].get_feature_names_out())
    coefficients = model.named_steps["clf"].coef_[0]
    mapping = {
        _clean_feature_name(str(name)): float(value)
        for name, value in zip(names, coefficients)
    }
    return [
        {
            "feature": feature,
            "coefficient": mapping[feature],
            "support": None,
            "unit": "1 độ lệch chuẩn (đặc trưng đã chuẩn hoá)",
            "support_applicable": False,
        }
        for feature in NUMERIC_FEATURES
        if feature in mapping
    ]


def tree_importances(model: Pipeline, top: int = 10) -> list[dict]:
    """Top độ quan trọng đặc trưng của Random Forest."""
    names = model.named_steps["prep"].get_feature_names_out()
    importances = model.named_steps["clf"].feature_importances_
    rows = [
        {
            "feature": _clean_feature_name(str(name)),
            "importance": float(value),
        }
        for name, value in zip(names, importances)
    ]
    rows.sort(key=lambda row: row["importance"], reverse=True)
    return rows[:top]


# --------------------------------------------------------------------------- #
#  Lưu / nạp mô hình
# --------------------------------------------------------------------------- #
def _as_jsonable(value):
    if isinstance(value, dict):
        return {key: _as_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def save_model(bundle: dict, path: Path = MODEL_PATH) -> Path:
    """Lưu bundle mô hình bằng joblib (tạo thư mục nếu chưa có)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return path


def load_model(path: Path = MODEL_PATH) -> dict:
    """Nạp bundle mô hình; cache theo đường dẫn."""
    path = Path(path)
    key = str(path.resolve())
    if key not in _MODEL_CACHE:
        if not path.is_file():
            raise FileNotFoundError(
                f"Chưa có mô hình tại {path}. "
                "Hãy chạy: .\\backend\\env\\Scripts\\python.exe etl\\dss_ml.py"
            )
        _MODEL_CACHE[key] = joblib.load(path)
    return _MODEL_CACHE[key]


def clear_model_cache(path: Path | None = None) -> None:
    """Xoá cache mô hình (dùng cho test hoặc sau khi huấn luyện lại)."""
    if path is None:
        _MODEL_CACHE.clear()
    else:
        _MODEL_CACHE.pop(str(Path(path).resolve()), None)


def predict_orders(o, path: Path = MODEL_PATH) -> np.ndarray:
    """Trả xác suất trễ cho từng dòng đầu vào (0..1).

    ``o`` có thể là DataFrame, dict hoặc iterable[dict]. Chỉ các cột trong
    ``FEATURE_COLUMNS`` được dùng; cột bị cấm/không liên quan bị bỏ qua.
    """
    bundle = load_model(path)
    frame = prepare_features(o)
    return bundle["model"].predict_proba(frame)[:, 1]


# --------------------------------------------------------------------------- #
#  Huấn luyện & đánh giá
# --------------------------------------------------------------------------- #
def train_and_save(
    o: pd.DataFrame | None = None,
    *,
    test_fraction: float = TEST_FRACTION,
    validation_fraction: float = VALIDATION_FRACTION,
    model_path: Path = MODEL_PATH,
    metrics_path: Path = METRICS_PATH,
) -> dict:
    """Huấn luyện, đánh giá trên tập kiểm tra và lưu mô hình + JSON chỉ số."""
    if o is None:
        o = load_orders()
    if o["period"].isna().any():
        raise ValueError("dữ liệu có period rỗng, không thể chia theo thời gian")

    train, test, cutoff = time_split(o, test_fraction)
    fit, validation, val_cutoff = train_validation_split(
        train, validation_fraction
    )

    y_fit = fit[TARGET].astype(int).to_numpy()
    y_val = validation[TARGET].astype(int).to_numpy()
    y_train = train[TARGET].astype(int).to_numpy()
    y_test = test[TARGET].astype(int).to_numpy()

    x_fit = prepare_features(fit)
    x_val = prepare_features(validation)
    x_train = prepare_features(train)
    x_test = prepare_features(test)

    models: dict[str, Pipeline] = {}
    model_metrics: dict[str, dict] = {}
    thresholds: dict[str, float] = {}

    # 1) Logistic Regression (mô hình chính)
    # 2) Random Forest (so sánh)
    for name, factory in (
        ("logistic_regression", build_logistic),
        ("random_forest", build_tree),
    ):
        # Fit trên phần đầu của train, chọn ngưỡng trên validation.
        probe = factory()
        probe.fit(x_fit, y_fit)
        threshold = best_threshold(y_val, probe.predict_proba(x_val)[:, 1])
        thresholds[name] = threshold

        # Refit trên toàn bộ train với ngưỡng đã chốt.
        model = factory()
        model.fit(x_train, y_train)
        models[name] = model

        proba = model.predict_proba(x_test)[:, 1]
        model_metrics[name] = _metrics(y_test, proba, threshold)
        model_metrics[name]["validation_threshold"] = threshold
        model_metrics[name]["precision_at_k"] = precision_at_k(y_test, proba)

    # 3) Baseline (i): luôn dự báo đúng hạn
    always_on_time = _metrics(
        y_test,
        np.zeros(len(test), dtype=float),
        0.5,
        constant_score=True,
    )
    always_on_time["precision_at_k"] = precision_at_k(
        y_test, np.zeros(len(test), dtype=float), constant_score=True
    )

    # 4) Baseline (ii): tỷ lệ trễ lịch sử của tuyến
    # Chọn ngưỡng trên validation bằng tỷ lệ tính từ fit-train, rồi áp ngưỡng
    # cố định cho test với tỷ lệ tính lại trên toàn bộ train.
    fit_rates = fit.groupby(_route_series(fit), observed=True)[TARGET].mean()
    fit_fallback = float(fit[TARGET].mean())
    val_scores = route_rate_scores(validation, fit_rates, fit_fallback)
    route_threshold = best_threshold(y_val, val_scores)

    train_rates = train.groupby(_route_series(train), observed=True)[TARGET].mean()
    train_fallback = float(train[TARGET].mean())
    test_scores = route_rate_scores(test, train_rates, train_fallback)
    route_baseline = _metrics(y_test, test_scores, route_threshold)
    route_baseline["validation_threshold"] = route_threshold
    route_baseline["precision_at_k"] = precision_at_k(y_test, test_scores)

    # Chỉ số mô hình chính được đưa lên đầu JSON.
    primary = "logistic_regression"
    support = _feature_support(models[primary], x_train)
    coefficients = logistic_coefficients(models[primary], support)
    low_support = low_support_coefficients(models[primary], support)
    numeric = numeric_coefficients(models[primary])
    importances = tree_importances(models["random_forest"])

    training_summary = {
        "final_training_set": "fit+validation",
        "fit_rows": int(len(fit)),
        "validation_rows": int(len(validation)),
        "train_rows": int(len(train)),
        "final_train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "fit_late_rate": float(fit[TARGET].mean()),
        "validation_late_rate": float(validation[TARGET].mean()),
        "train_late_rate": float(train[TARGET].mean()),
        "test_late_rate": float(test[TARGET].mean()),
        "overall_late_rate": float(o[TARGET].mean()),
    }
    threshold_selection = {
        "value": float(thresholds[primary]),
        "selected_on": "validation",
        "criterion": "max F1",
        "validation_cutoff_period": int(val_cutoff),
        "note": (
            "Ngưỡng chọn trên validation (các kỳ cuối của tập huấn luyện); "
            "không dùng tập kiểm tra để chọn ngưỡng."
        ),
    }

    bundle = {
        "model": models[primary],
        "model_name": primary,
        "threshold": thresholds[primary],
        "threshold_selection": threshold_selection,
        "sklearn_version": sklearn.__version__,
        "training": training_summary,
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
            "forbidden": FORBIDDEN_FEATURES,
        },
        "split": {
            "cutoff_period": cutoff,
            "train_periods": sorted(int(p) for p in train["period"].unique()),
            "validation_cutoff_period": val_cutoff,
            "validation_periods": sorted(
                int(p) for p in validation["period"].unique()
            ),
            "test_periods": sorted(int(p) for p in test["period"].unique()),
        },
        "metrics": model_metrics[primary],
        "coefficient_support": {
            "min_support": MIN_SUPPORT,
            "top_coefficients": coefficients,
            "low_support_coefficients": low_support,
            "numeric_coefficients": numeric,
            "numeric_note": (
                "Hệ số đặc trưng số tính trên dữ liệu đã chuẩn hoá: mỗi 1 độ "
                "lệch chuẩn. Support không áp dụng cho đặc trưng số."
            ),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Mô phỏng trên dữ liệu lịch sử; chỉ dùng thông tin biết được tại "
            "thời điểm giao hàng cho đơn vị vận chuyển."
        ),
    }
    save_model(bundle, model_path)

    payload = {
        "generated_at": bundle["created_at"],
        "sklearn_version": sklearn.__version__,
        "data": {
            "order_route_rows": int(len(o)),
            "late_rate": float(o[TARGET].mean()),
            "final_training_set": "fit+validation",
            "fit_rows": int(len(fit)),
            "validation_rows": int(len(validation)),
            "train_rows": int(len(train)),
            "final_train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "fit_late_rate": float(fit[TARGET].mean()),
            "validation_late_rate": float(validation[TARGET].mean()),
            "train_late_rate": float(train[TARGET].mean()),
            "test_late_rate": float(test[TARGET].mean()),
            "overall_late_rate": float(o[TARGET].mean()),
        },
        "split": {
            "test_fraction_periods": test_fraction,
            "validation_fraction_periods": validation_fraction,
            "cutoff_period": cutoff,
            "validation_cutoff_period": val_cutoff,
            "train_periods": sorted(int(p) for p in train["period"].unique()),
            "validation_periods": sorted(
                int(p) for p in validation["period"].unique()
            ),
            "test_periods": sorted(int(p) for p in test["period"].unique()),
            "n_train_periods": int(train["period"].nunique()),
            "n_test_periods": int(test["period"].nunique()),
        },
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
            "forbidden": FORBIDDEN_FEATURES,
            "preprocessing": {
                "categorical_missing": "unknown",
                "numeric_missing": "median (fit on training data)",
                "negative_values": (
                    "Giữ nguyên; prep có giá trị âm trong dữ liệu gốc, không clip."
                ),
            },
        },
        "threshold_selection": threshold_selection,
        "precision_at_k": {
            "fractions": list(PRECISION_AT_K),
            "note": (
                "K là tỷ lệ số đơn có xác suất trễ cao nhất trong tập kiểm tra; "
                "lift = precision@K / tỷ lệ trễ nền của tập kiểm tra."
            ),
        },
        "models": {
            name: {
                **model_metrics[name],
                **(
                    {
                        "top_coefficients": coefficients,
                        "low_support_coefficients": low_support,
                        "coefficient_min_support": MIN_SUPPORT,
                        "numeric_coefficients": numeric,
                        "numeric_note": (
                            "Hệ số đặc trưng số tính trên dữ liệu đã chuẩn hoá: "
                            "mỗi 1 độ lệch chuẩn. Support không áp dụng cho "
                            "đặc trưng số."
                        ),
                    }
                    if name == primary
                    else {"top_importances": importances}
                ),
            }
            for name in model_metrics
        },
        "baselines": {
            "always_on_time": always_on_time,
            "route_historical_rate": route_baseline,
        },
        "primary_model": primary,
        "notes": [
            "Chia theo thời gian, không chia ngẫu nhiên.",
            "Ngưỡng chọn trên validation (kỳ cuối của tập huấn luyện), không chọn trên test.",
            "Mô hình cuối được huấn luyện lại trên fit+validation; test chỉ dùng để đánh giá.",
            "precision@K và lift@K là chỉ số vận hành chính; K = 1%, 5%, 10% số đơn xếp cao nhất.",
            "Hệ số Logistic Regression chỉ xếp hạng/diễn giải khi support >= "
            f"{MIN_SUPPORT} đơn; nhóm ít mẫu được liệt kê riêng, không diễn giải.",
            "Dữ liệu chỉ gồm các đơn đã giao (delivered), có đủ mốc thời gian.",
            "Không có số ngày cam kết giao hàng gốc trong đặc trưng.",
            "Mô hình học trên dữ liệu lịch sử, không phải quan hệ nhân quả.",
        ],
    }
    payload = _as_jsonable(payload)
    metrics_path = Path(metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def _print_summary(payload: dict) -> None:
    split = payload["split"]
    data = payload["data"]
    print("## Dữ liệu & chia tập")
    print(
        f"- Dòng (đơn, tuyến): {data['order_route_rows']}; "
        f"tỷ lệ trễ toàn bộ: {data['late_rate']:.4%}"
    )
    print(
        f"- Cutoff test: {split['cutoff_period']} "
        f"(train: {split['n_train_periods']} kỳ, test: {split['n_test_periods']} kỳ); "
        f"validation cutoff: {split['validation_cutoff_period']}"
    )
    print(
        f"- Rows: fit={data['fit_rows']} ({data['fit_late_rate']:.4%} trễ), "
        f"validation={data['validation_rows']} ({data['validation_late_rate']:.4%}), "
        f"test={data['test_rows']} ({data['test_late_rate']:.4%})"
    )
    print(
        f"- Mô hình cuối huấn luyện trên {data['final_training_set']}: "
        f"{data['final_train_rows']} dòng ({data['train_late_rate']:.4%} trễ)"
    )
    print(f"- scikit-learn: {payload['sklearn_version']}")
    print(
        f"- Ngưỡng: {payload['threshold_selection']['value']:.4f} "
        f"(chọn trên {payload['threshold_selection']['selected_on']}, "
        f"{payload['threshold_selection']['criterion']})"
    )

    print("\n## Kết quả trên tập kiểm tra")
    header = (
        f"{'model':<24} {'threshold':>9} {'ROC-AUC':>8} {'PR-AUC':>8} "
        f"{'precision':>9} {'recall':>7} {'F1':>7}"
    )
    print(header)
    for name, metrics in payload["models"].items():
        print(
            f"{name:<24} {metrics['threshold']:>9.4f} "
            f"{(metrics['roc_auc'] if metrics['roc_auc'] is not None else float('nan')):>8.4f} "
            f"{(metrics['pr_auc'] if metrics['pr_auc'] is not None else float('nan')):>8.4f} "
            f"{metrics['precision']:>9.4f} {metrics['recall']:>7.4f} "
            f"{metrics['f1']:>7.4f}"
        )
    for name, metrics in payload["baselines"].items():
        print(
            f"{name:<24} {metrics['threshold']:>9.4f} "
            f"{(metrics['roc_auc'] if metrics['roc_auc'] is not None else float('nan')):>8.4f} "
            f"{(metrics['pr_auc'] if metrics['pr_auc'] is not None else float('nan')):>8.4f} "
            f"{metrics['precision']:>9.4f} {metrics['recall']:>7.4f} "
            f"{metrics['f1']:>7.4f}"
        )

    print("\n## precision@K / lift@K trên tập kiểm tra (mô hình chính)")
    print(f"{'K':>6} {'k':>7} {'precision@K':>13} {'lift@K':>9} {'positives':>10}")
    for row in payload["models"][payload["primary_model"]]["precision_at_k"]:
        lift = row["lift_at_k"] if row["lift_at_k"] is not None else float("nan")
        print(
            f"{row['k_fraction']:>6.0%} {row['k']:>7d} "
            f"{row['precision_at_k']:>13.4f} {lift:>9.4f} "
            f"{row['positives_in_top_k']:>10d}"
        )

    lr = payload["models"]["logistic_regression"]
    print(
        f"\n## Top 10 hệ số Logistic Regression "
        f"(support >= {lr['coefficient_min_support']})"
    )
    for row in lr["top_coefficients"]:
        print(
            f"- {row['feature']}: {row['coefficient']:+.4f} "
            f"(support={row['support']})"
        )
    print(
        "\n## Hệ số đặc trưng số (đã chuẩn hoá, mỗi 1 độ lệch chuẩn; "
        "support không áp dụng)"
    )
    for row in lr["numeric_coefficients"]:
        print(f"- {row['feature']}: {row['coefficient']:+.4f}")
    if lr["low_support_coefficients"]:
        print("\n## Hệ số nhóm ít mẫu (KHÔNG diễn giải)")
        for row in lr["low_support_coefficients"]:
            print(
                f"- {row['feature']}: {row['coefficient']:+.4f} "
                f"(support={row['support']})"
            )

    print(
        f"\nĐã lưu mô hình: {MODEL_PATH}\n"
        f"Đã lưu chỉ số: {METRICS_PATH}"
    )


if __name__ == "__main__":
    _print_summary(train_and_save())
