"""API DSS (Django): view chỉ nhận tham số, gọi mô hình trong etl/dss_models.py."""

import json
import math

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from etl import dss_models as M

from .models import ActionLog

# Dữ liệu kho chỉ nạp một lần khi module được import.
O = M.load_orders()


def _selected_orders(request):
    """Lọc theo year (tuỳ chọn). year rỗng hoặc 'all' nghĩa là toàn bộ dữ liệu."""
    year = request.GET.get("year")
    if not year or year == "all":
        return O
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise ValueError("year phải là số nguyên, ví dụ 2017 hoặc 2018")
    return O[O.period // 100 == year]


def _bad(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _clean(value):
    """Đổi NaN/Infinity thành None để JSON hợp lệ với JavaScript."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _records(df):
    # pandas to_json đã đổi NaN thành null; _clean xử lý thêm các giá trị lồng nhau.
    return json.loads(df.to_json(orient="records"))


@require_GET
def routes(request):
    """Danh sách tuyến đỏ/vàng, kèm nguyên nhân gốc của từng tuyến."""
    try:
        d = _selected_orders(request)
    except ValueError as exc:
        return _bad(str(exc))

    top = request.GET.get("top")
    try:
        top = int(top) if top is not None else 10
    except (TypeError, ValueError):
        return _bad("top phải là số nguyên dương")
    if top < 1:
        return _bad("top phải là số nguyên dương")

    rows = _records(M.route_priority(d, top=top))
    for row in rows:
        row["root_cause"] = M.root_cause(d, row["route"])
    return JsonResponse(_clean(rows), safe=False)


@require_GET
def scenario(request):
    """What-if: cắt thời gian từng giai đoạn và trả tỷ lệ trễ dự báo + độ nhạy."""
    route = request.GET.get("route")
    if not route:
        return _bad("thiếu tham số route")

    try:
        d = _selected_orders(request)
        cut = {k: float(request.GET.get(k, 0) or 0) for k in ("approval", "prep", "transit")}
    except ValueError:
        return _bad("approval/prep/transit/year phải là số hợp lệ")

    if not (d.route == route).any():
        return _bad(f"không có dữ liệu cho tuyến {route}")

    cause = M.root_cause(d, route)
    bottleneck = cause["stage"]
    # base_cut: giữ mức cắt hiện tại của các giai đoạn KHÁC bottleneck cố định
    # khi quét sensitivity, để series phản ánh đúng bối cảnh What-if.
    base_cut = {k: v for k, v in cut.items() if k != bottleneck}
    result = {
        **M.scenario(d, route, cut),
        "bottleneck": bottleneck,
        "has_bottleneck": cause["has_bottleneck"],
        "series": M.sensitivity(d, route, bottleneck, base_cut=base_cut),
    }
    return JsonResponse(_clean(result))


@require_GET
def promise(request):
    """Goal seek: số ngày cần kéo dài cam kết để tỷ lệ trễ <= target."""
    route = request.GET.get("route")
    if not route:
        return _bad("thiếu tham số route")

    try:
        d = _selected_orders(request)
        target = float(request.GET.get("target", 0.05))
    except ValueError:
        return _bad("target/year phải là số hợp lệ")
    if not 0 <= target <= 1:
        return _bad("target phải nằm trong khoảng 0..1 (ví dụ 0.05)")

    if not (d.route == route).any():
        return _bad(f"không có dữ liệu cho tuyến {route}")

    return JsonResponse(_clean(M.goal_seek_promise(d, route, target)))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def actions(request):
    """POST ghi một hành động Apply; GET trả 50 hành động gần nhất."""
    if request.method == "POST":
        try:
            body = json.loads(request.body or b"{}")
        except (TypeError, ValueError):
            return _bad("JSON không hợp lệ")
        if not isinstance(body, dict):
            return _bad("JSON phải là một object")

        ActionLog.objects.create(
            action=str(body.get("action", ""))[:40],
            route=str(body.get("route", ""))[:20],
            level=str(body.get("level", ""))[:10],
            detail=json.dumps(body, ensure_ascii=False),
        )
        return JsonResponse({"ok": True})

    rows = list(
        ActionLog.objects.order_by("-created_at").values(
            "created_at", "action", "route", "level", "detail"
        )[:50]
    )
    return JsonResponse(_clean(rows), safe=False)
