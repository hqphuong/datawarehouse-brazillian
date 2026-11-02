# Hướng dẫn xây dựng phần DSS – Đề tài Olist Delivery SLA (CO4031)

Tài liệu gồm **Phần A (lý thuyết ứng với đề tài)** và **Phần B (10 bước thực hiện)**. Cấu trúc thư mục bám theo repo hiện có: các script ETL nằm trong gói `etl/` (chạy bằng `python -m etl.<tên_script>`) và import `from .config import PROCESSED_DIR`.

---

## Phần A. Lý thuyết ứng với đề tài

### A.1 Kiến trúc DSS ↔ hệ thống của nhóm

| Lý thuyết | Trong đề tài |
|---|---|
| Data Layer / Phân hệ quản lý dữ liệu | Kho dữ liệu: `Fact_Delivery_SLA` + `Dim_Product`, `Dim_Time`, `Dim_Location` (các file `cleaned_*.csv` hoặc CSDL) |
| Model Layer / Phân hệ quản lý mô hình (Model Base) | `route_priority`, `root_cause`, mô hình dự báo đơn có nguy cơ trễ |
| MBMS Tools | `scenario` (What-if), `sensitivity` (độ nhạy), `goal_seek_*` (tìm mục tiêu) |
| User Interface Layer / UIMS | Giao diện web: Dashboard, DSS Action Center, OLAP |
| Knowledge Layer (tuỳ chọn) | Bảng luật khuyến nghị: giai đoạn nghẽn → hành động |
| Communication Layer (tuỳ chọn) | Không làm |

- **Phân loại theo Holsapple & Whinston:** Compound DSS (database-oriented + solver-oriented + rule-oriented).
- **Phân loại theo triển khai:** Web-based DSS.
- **Phương pháp phát triển:** Prototyping (RAD) – nhóm đã có bản HTML mẫu, lặp lại theo phản hồi.

### A.2 Bốn giai đoạn ra quyết định ↔ bốn khối DSS

| Giai đoạn | Nội dung trong đề tài | Khối DSS |
|---|---|---|
| **Intelligence** | *Phân loại bài toán:* bán cấu trúc (có quy tắc SLA rõ nhưng cần phán đoán để chọn hành động). *Phân rã:* 3 giai đoạn của đơn hàng (duyệt thanh toán, người bán đóng gói, vận chuyển). *Quyền sở hữu:* Giám đốc Vận hành. | 1. Route Priority, 2. Root Cause |
| **Design** | Mô hình: `ngày trễ mới = ngày trễ cũ − tổng thời gian cắt giảm`. *Nguyên tắc lựa chọn:* tỷ lệ trễ ≤ mục tiêu (mặc định 5%). | 3. Scenario (What-if) |
| **Choice** | So sánh kịch bản (sensitivity), chọn phương án nhỏ nhất đạt mục tiêu (goal seek). | 3. Scenario, 4. Recommendation |
| **Implementation & Evaluation** | Nút Apply ghi log; đánh giá bằng kiểm thử mô hình, backtest, chỉ số ML. | 4. Recommendation & Action |

---

## Phần B. 10 bước thực hiện

### Bước 1. Cấu trúc dự án

```
etl/                      # gói hiện có (config.py, dim_*.py, fact_delivery_sla.py, __init__.py)
  dss_models.py           # Model Base (Bước 3)
  dss_ml.py               # mô hình dự báo (Bước 6, tuỳ chọn)
manage.py                 # Django, chỉ phục vụ DSS (Bước 7)
dss_project/              # settings.py, urls.py của Django
dss/                      # app DSS: views.py, urls.py, models.py
tests/test_dss_models.py  # Bước 4
web/Olist_Logistics_DSS_v3.html
data/                     # dữ liệu đã xử lý, action_log.jsonl
reports/dss_results.md    # kết quả đánh giá (Bước 9)
```

Cài đặt: `pip install pandas numpy scikit-learn django django-cors-headers pytest`

### Bước 2. Tầng dữ liệu: kiểm tra Fact (đã có `delay_days`)

Fact thật của nhóm (110 173 dòng, 96 455 đơn) **đã có `delay_days`** và `has_logistics_complaint`, nhưng **không có cột `is_late`**. Quy ước dùng trong DSS: một đơn trễ khi `delay_days > 0`, và `is_late` được suy ra trong `load_orders` (Bước 3).

Kiểm tra nhanh trên CSV:
- `delay_days` không rỗng và cùng giá trị cho mọi item của một đơn.
- Khóa ngoại hợp lệ: mọi `customer_location_id`, `seller_location_id`, `time_id`, `product_id` đều có trong các bảng chiều (đã kiểm tra: 0 lỗi).

Lưu ý dữ liệu: `seller_prep_time_days` âm ở 1 542 dòng và `carrier_transit_time_days` âm ở 50 dòng; `review_score` rỗng ở 827 dòng. `scenario` đã chặn về 0 khi cắt giảm; các trung bình trong `root_cause` vẫn gồm giá trị âm, nên ghi vào phần hạn chế của báo cáo (hoặc lọc nếu nhóm muốn).

**Xong khi:** các kiểm tra trên đạt.

### Bước 3. Viết Model Base (`etl/dss_models.py`)

Mô hình làm việc trên bảng cấp **đơn hàng** (Fact có hạt là item).

```python
"""Model Base của DSS: các mô hình phân tích chạy trên dữ liệu kho."""
import math

import numpy as np
import pandas as pd

try:
    from .config import PROCESSED_DIR
except ImportError:
    from config import PROCESSED_DIR

STAGES = ["approval", "prep", "transit"]
OWNER = {"approval": "Duyệt thanh toán", "prep": "Người bán", "transit": "Đơn vị vận chuyển"}
RULES = {
    "approval": "Rà soát khâu duyệt thanh toán của tuyến này.",
    "prep": "Làm việc với nhóm người bán trên tuyến để rút ngắn thời gian chuẩn bị hàng.",
    "transit": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng.",
}


def load_orders() -> pd.DataFrame:
    """Đọc Fact + 3 Dim, trả về bảng 1 dòng = 1 (đơn hàng, tuyến)."""
    f = pd.read_csv(PROCESSED_DIR / "cleaned_fact_orders.csv")
    loc = pd.read_csv(PROCESSED_DIR / "cleaned_dim_location.csv")[["location_id", "state"]]
    t = pd.read_csv(PROCESSED_DIR / "cleaned_dim_time.csv")[["time_id", "year", "month"]]
    p = pd.read_csv(PROCESSED_DIR / "cleaned_dim_product.csv")
    f = (
        f.merge(loc.rename(columns={"location_id": "customer_location_id", "state": "cust_state"}), on="customer_location_id", how="left")
        .merge(loc.rename(columns={"location_id": "seller_location_id", "state": "seller_state"}), on="seller_location_id", how="left")
        .merge(t, on="time_id", how="left")
        .merge(p, on="product_id", how="left")
    )
    f["is_late"] = f["delay_days"] > 0      # Fact không có is_late; suy ra từ delay_days
    f["route"] = f["seller_state"] + "->" + f["cust_state"]
    f["period"] = f["year"] * 100 + f["month"]
    return f.groupby(["order_id", "route"], as_index=False).agg(
        period=("period", "first"), seller_state=("seller_state", "first"), cust_state=("cust_state", "first"),
        is_late=("is_late", "max"), delay_days=("delay_days", "first"),
        complaint=("has_logistics_complaint", "max"),
        approval=("approval_time_days", "first"), prep=("seller_prep_time_days", "first"),
        transit=("carrier_transit_time_days", "first"),
        freight=("freight_value", "sum"), n_items=("order_item_id", "count"),
        payment_type=("payment_type", "first"), review_score=("review_score", "first"),
        category=("category_name_english", "first"), weight=("weight_g", "sum"), volume=("volume_cm3", "sum"),
    )


def route_priority(o, red=2.0, amber=1.5, min_orders=100, top=10):
    """Khối 1: xếp hạng tuyến theo mức vượt tỷ lệ trễ toàn hệ thống."""
    overall = o.is_late.mean()
    g = o.groupby("route").agg(orders=("order_id", "nunique"), late_orders=("is_late", "sum"), late_rate=("is_late", "mean")).reset_index()
    g = g[g.orders >= min_orders]
    g["level"] = np.where(g.late_rate >= overall * red, "red", np.where(g.late_rate >= overall * amber, "amber", "ok"))
    return g[g.level != "ok"].sort_values("late_orders", ascending=False).head(top)


def root_cause(o, route):
    """Khối 2: giai đoạn vượt mức trung bình hệ thống nhiều nhất."""
    r = o[o.route == route]
    exc = {s: float(r[s].mean() - o[s].mean()) for s in STAGES}
    worst = max(exc, key=exc.get)
    return {"stage": worst, "owner": OWNER[worst], "excess": exc, "recommendation": RULES[worst]}


def scenario(o, route=None, cut=None):
    """Khối 3 (What-if): cắt giảm thời gian từng giai đoạn (ngày), tính lại tỷ lệ trễ."""
    cut = {"approval": 0, "prep": 0, "transit": 0, **(cut or {})}
    d = o if route is None else o[o.route == route]
    total = sum(np.minimum(v, d[s].clip(lower=0)) for s, v in cut.items())
    new_late = (d.delay_days - total) > 0
    return {"orders": len(d), "baseline": float(d.is_late.mean()), "projected": float(new_late.mean()),
            "avoided": int(d.is_late.sum() - new_late.sum())}


def sensitivity(o, route, stage, max_days=5):
    """Phân tích độ nhạy: tỷ lệ trễ dự báo khi cắt 0..max_days ngày ở một giai đoạn."""
    return [{"cut": x, "projected": scenario(o, route, {stage: x})["projected"]} for x in range(max_days + 1)]


def goal_seek_promise(o, route, target=0.05):
    """Tìm mục tiêu 1: cần kéo dài cam kết giao hàng bao nhiêu ngày để tỷ lệ trễ <= target."""
    d = o[o.route == route]
    x = max(0, math.ceil(d.delay_days.quantile(1 - target)))
    return {"extra_days": x, "late_after": float((d.delay_days - x > 0).mean())}


def goal_seek_cut(o, route, stage, target=0.05, step=0.5, max_days=10):
    """Tìm mục tiêu 2: cần cắt tối thiểu bao nhiêu ngày ở một giai đoạn (None nếu không đạt)."""
    x = 0.0
    while x <= max_days:
        if scenario(o, route, {stage: x})["projected"] <= target:
            return x
        x += step
    return None
```

**Đã thử trên dữ liệu thật** (96 455 đơn, tỷ lệ trễ theo đơn 8,07%, 72 tuyến có ≥100 đơn): với `min_orders=100`, `red=2,0`, `amber=1,5` có 6 tuyến đỏ và 8 tuyến vàng (`top=10` giữ 10 tuyến đầu); với `min_orders=200` có 4 đỏ và 7 vàng. Nên giữ mặc định hoặc chọn 200 để danh sách gọn. Với tuyến SP→SP, cắt 0 ngày chuẩn bị hàng cho đúng tỷ lệ gốc (6,2%) và giảm dần khi cắt nhiều hơn (cắt 5 ngày còn 3,4%).

### Bước 4. Kiểm thử Model Base (`tests/test_dss_models.py`)

```python
import pytest
from etl import dss_models as M


@pytest.fixture(scope="module")
def o():
    return M.load_orders()


def test_unique_order_route(o):
    assert not o.duplicated(["order_id", "route"]).any()


def test_delay_days_valid(o):
    assert o.delay_days.notna().all()
    assert ((o.delay_days > 0) == o.is_late).all()


def test_zero_cut_is_baseline(o):
    r = M.route_priority(o).route.iloc[0]
    s = M.scenario(o, r)
    assert abs(s["projected"] - s["baseline"]) < 1e-9


def test_sensitivity_monotone(o):
    r = M.route_priority(o).route.iloc[0]
    ser = [x["projected"] for x in M.sensitivity(o, r, "prep")]
    assert all(a >= b for a, b in zip(ser, ser[1:]))


def test_goal_seek_promise(o):
    r = M.route_priority(o).route.iloc[0]
    assert M.goal_seek_promise(o, r, 0.05)["late_after"] <= 0.05 + 1e-9
```

Chạy: `pytest -q`. Đối chiếu thêm: tỷ lệ trễ của một tuyến tính thủ công bằng pandas/SQL phải khớp `baseline`.
**Xong khi:** tất cả test qua.

### Bước 5. Bảng luật khuyến nghị (Knowledge Layer)

Đã nằm trong `RULES` ở Bước 3. Khuyến nghị cho một tuyến = `RULES[root_cause(...)["stage"]]` kèm số ngày điều chỉnh từ `goal_seek_promise`.

### Bước 6. Mô hình dự báo đơn có nguy cơ trễ (tuỳ chọn, `etl/dss_ml.py`)

Khớp lý thuyết học máy trong học phần (Logistic Regression, Random Forest, Accuracy/Precision/Recall/F1/Confusion Matrix/ROC-AUC).

**Quy tắc bắt buộc:** chỉ dùng đặc trưng biết được **trước khi giao hàng**. Cấm dùng `transit`, `delay_days`, `review_score` (rò rỉ dữ liệu). Chia train/test **theo thời gian**, không chia ngẫu nhiên.

```python
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import dss_models as M

CAT = ["seller_state", "cust_state", "category", "payment_type"]
NUM = ["approval", "prep", "freight", "weight", "volume", "n_items"]


def train_and_eval():
    o = M.load_orders()
    d = o.dropna(subset=CAT + NUM).copy()
    ps = sorted(d.period.unique())
    cut = ps[int(len(ps) * 0.8)]
    tr, te = d[d.period <= cut], d[d.period > cut]
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), CAT), ("n", StandardScaler(), NUM)])
    models = {
        "logreg": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "rf": RandomForestClassifier(n_estimators=200, min_samples_leaf=20, class_weight="balanced", n_jobs=-1, random_state=42),
    }
    fitted, report = {}, {}
    for name, m in models.items():
        p = Pipeline([("pre", clone(pre)), ("m", m)]).fit(tr[CAT + NUM], tr.is_late)
        proba = p.predict_proba(te[CAT + NUM])[:, 1]
        pred = proba >= 0.5
        fitted[name] = p
        report[name] = {"roc_auc": roc_auc_score(te.is_late, proba),
                        "report": classification_report(te.is_late, pred, output_dict=True),
                        "confusion": confusion_matrix(te.is_late, pred).tolist()}
    return fitted, report, te


if __name__ == "__main__":
    _, rep, _ = train_and_eval()
    for k, v in rep.items():
        print(k, "ROC-AUC:", round(v["roc_auc"], 3), "confusion:", v["confusion"])
```

- Đơn trễ là thiểu số nên **không chỉ báo cáo Accuracy**; báo cáo cả Precision, Recall, F1, Confusion Matrix, ROC-AUC.
- Chọn mô hình có Recall/F1 tốt hơn; Logistic Regression dễ giải thích hơn.
- Dùng trong DSS: endpoint `/api/dss/at-risk` trả top-N đơn có xác suất trễ cao nhất (minh hoạ, vì dữ liệu lịch sử).
- Hạn chế cần ghi: Fact chỉ chứa đơn đã giao, mô hình chưa thấy đơn huỷ/thất lạc.

**Xong khi:** có bảng so sánh 2 mô hình trên tập kiểm tra.

### Bước 7. API: Flask cho OLAP/dữ liệu, Django cho DSS

**Chia việc giữa hai service** (cùng đọc một kho dữ liệu, chạy ở hai cổng khác nhau):

| Service | Cổng | Endpoint |
|---|---|---|
| **Flask** (OLAP và dữ liệu) | 5000 | `/api/filters`, `/api/kpis`, `/api/charts/*` (Dashboard); `/api/olap/meta`, `/api/olap/query`; `/api/etl/*` (ETL Monitor) |
| **Django** (DSS) | 8000 | `/api/dss/routes`, `/api/dss/scenario`, `/api/dss/promise`, `/api/dss/actions`, (tuỳ chọn) `/api/dss/at-risk` |

**Hợp đồng chung giữa hai bên** (để số liệu không lệch nhau):
- Đơn trễ khi `delay_days > 0`.
- Đếm đơn theo `order_id` khác nhau (Fact có hạt là item).
- Cả hai đọc cùng đường dẫn/CSDL qua `etl/config.py` và `.env`.
- **Kiểm tra chéo:** tỷ lệ trễ tổng thể từ Flask `/api/kpis` phải bằng `baseline` của DSS khi không lọc (khoảng 8,07% theo đơn trên dữ liệu hiện có).

#### Cài đặt Django (đặt `manage.py` ở thư mục gốc repo để import được `etl`)
```bash
pip install django django-cors-headers
django-admin startproject dss_project .
python manage.py startapp dss
```

`dss_project/settings.py` (phần cần có):
```python
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "dev-only-change-me"
DEBUG = True
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["corsheaders", "dss"]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", "django.middleware.common.CommonMiddleware"]
CORS_ALLOW_ALL_ORIGINS = True
ROOT_URLCONF = "dss_project.urls"
# CSDL của Django chỉ để lưu log hành động DSS; kho dữ liệu đọc qua etl/dss_models.py
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "dss_actions.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

`dss_project/urls.py`:
```python
from django.urls import include, path
urlpatterns = [path("api/dss/", include("dss.urls"))]
```

`dss/models.py`:
```python
from django.db import models

class ActionLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=40)      # auto_reroute | extend_promise | email_carrier
    route = models.CharField(max_length=20)
    level = models.CharField(max_length=10, blank=True)
    detail = models.TextField(blank=True)
```

`dss/urls.py`:
```python
from django.urls import path
from . import views
urlpatterns = [
    path("routes", views.routes),
    path("scenario", views.scenario),
    path("promise", views.promise),
    path("actions", views.actions),
]
```

`dss/views.py` (logic mô hình nằm hết trong `etl/dss_models.py`, view chỉ nhận tham số, gọi hàm, trả JSON):
```python
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from etl import dss_models as M
from .models import ActionLog

O = M.load_orders()  # nạp một lần khi khởi động


def _orders(request):
    year = request.GET.get("year")
    return O if not year else O[O.period // 100 == int(year)]


def _bad(msg):
    return JsonResponse({"error": msg}, status=400)


@require_GET
def routes(request):
    d = _orders(request)
    rows = json.loads(M.route_priority(d).to_json(orient="records"))
    for r in rows:
        r["root_cause"] = M.root_cause(d, r["route"])
    return JsonResponse(rows, safe=False)


@require_GET
def scenario(request):
    route = request.GET.get("route")
    if not route:
        return _bad("thiếu tham số route")
    d = _orders(request)
    cut = {k: float(request.GET.get(k, 0)) for k in ("approval", "prep", "transit")}
    worst = M.root_cause(d, route)["stage"]
    return JsonResponse({**M.scenario(d, route, cut), "bottleneck": worst, "series": M.sensitivity(d, route, worst)})


@require_GET
def promise(request):
    route = request.GET.get("route")
    if not route:
        return _bad("thiếu tham số route")
    return JsonResponse(M.goal_seek_promise(_orders(request), route, float(request.GET.get("target", 0.05))))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def actions(request):
    if request.method == "POST":
        b = json.loads(request.body or "{}")
        ActionLog.objects.create(action=b.get("action", ""), route=b.get("route", ""),
                                 level=b.get("level", ""), detail=json.dumps(b, ensure_ascii=False))
        return JsonResponse({"ok": True})
    rows = list(ActionLog.objects.order_by("-created_at").values("created_at", "action", "route", "level")[:50])
    return JsonResponse(rows, safe=False)
```

Chạy:
```bash
python manage.py makemigrations dss && python manage.py migrate
python manage.py runserver 8000          # DSS (Django)
flask --app <module_flask> run --port 5000   # OLAP và dữ liệu (Flask, bật flask-cors)
```
Tuyến trong URL dùng dạng `SP->RJ`; tham số `route` nên được mã hoá khi gọi từ trình duyệt (`encodeURIComponent`). Nếu làm Bước 6, thêm view `at_risk` tương tự.

**Lưu ý khi demo:** phải chạy cả hai server; nên viết sẵn một file hướng dẫn hoặc script khởi động. Trong báo cáo (Chương 6) mô tả kiến trúc hai service cùng đọc kho dữ liệu.

### Bước 8. Nối giao diện

Trong hàm `DSS()` của `web/Olist_Logistics_DSS_v3.html`, thay các hàm tính trên dữ liệu mẫu `DS_ORD` bằng gọi API:

```jsx
const API = 'http://localhost:8000/api/dss';   // Django; OLAP/Dashboard gọi Flask ở http://localhost:5000/api
const [pri, setPri] = useState([]);
useEffect(() => {
  fetch(`${API}/routes${year === 'all' ? '' : '?year=' + year}`).then(r => r.json()).then(setPri);
}, [year]);
useEffect(() => {
  if (!route) return;
  const t = setTimeout(() => fetch(`${API}/scenario?route=${encodeURIComponent(route)}&approval=${cut.approval}&prep=${cut.prep}&transit=${cut.transit}`)
    .then(r => r.json()).then(setSc), 250);   // debounce thanh trượt
  return () => clearTimeout(t);
}, [route, cut]);
```

- Đổi tên trường cho khớp API (`late_rate`, `late_orders`, `projected`, `avoided`…).
- Nút Apply gọi `POST /api/dss/actions`.
- Xoá `DS_ORD` và các hàm `ds*` khi giao diện đã chạy bằng API.

### Bước 9. Đánh giá (số liệu đưa vào báo cáo)

1. **Kiểm thử mô hình:** kết quả các test ở Bước 4.
2. **Backtest cảnh báo:** tuyến bị gắn đỏ/vàng ở kỳ *t* có thực sự trễ nhiều hơn ở kỳ *t+1* không?

```python
import pandas as pd
from etl import dss_models as M


def backtest(o, min_orders=50):
    ps, res = sorted(o.period.unique()), []
    for a, b in zip(ps[:-1], ps[1:]):
        flag = set(M.route_priority(o[o.period == a], min_orders=min_orders).route)
        n = o[o.period == b]
        res.append({"period": b,
                    "flagged": n[n.route.isin(flag)].is_late.mean(),
                    "others": n[~n.route.isin(flag)].is_late.mean()})
    return pd.DataFrame(res)
```

3. **Chỉ số ML:** bảng so sánh ở Bước 6.
4. **Ảnh chụp giao diện:** 4 khối của DSS Action Center.

Ghi tất cả kết quả vào `reports/dss_results.md`.

### Bước 10. Viết vào báo cáo

| Nội dung | Chỗ viết |
|---|---|
| Phân loại bài toán, phân rã, quyền sở hữu, nguyên tắc lựa chọn | Mục 5.2.1 |
| Công thức các hàm mô hình + giả định (giảm thời gian chuyển 1:1 sang ngày giao) | Mục 5.2.1 (đã có công thức What-if; bổ sung các quy tắc còn lại) |
| Kiến trúc DSS theo bảng ở A.1 | Đầu Chương 5 |
| Cài đặt, API, ảnh chụp màn hình | Chương 6 |
| Kết quả backtest, ML, hạn chế | Chương 7 |
| Chuẩn đầu ra | Cột "Minh chứng": L.O.3.2 (4 giai đoạn), L.O.3.3 (mô hình hoá), L.O.4.2 (hiện thực DSS) |

**Hạn chế nên ghi:** dữ liệu lịch sử nên cảnh báo mang tính mô phỏng; What-if giả định cắt giảm chuyển 1:1; nguyên nhân gốc chỉ đến mức giai đoạn vì Fact chưa có `seller_id`; mô hình ML chỉ huấn luyện trên đơn đã giao.

---

## Lịch gợi ý (hạn nộp 15/11/2026)

| Ngày | Việc |
|---|---|
| 1–2 | Bước 1–2 (`delay_days`, chạy lại ETL) |
| 3–5 | Bước 3–5 và kiểm thử |
| 6–7 | Bước 6 (ML), nếu kịp thời gian |
| 8–9 | Bước 7–8 (API và giao diện) |
| 10–11 | Bước 9 (đánh giá, chụp ảnh) |
| 12–14 | Bước 10 (viết báo cáo, quay video, đóng gói mã nguồn (thư mục `src/` theo quy định nộp bài) và `data/`) |

Nếu thiếu thời gian: bỏ Bước 5 và 6. Phần cốt lõi là Bước 2–4 và 7–8.
