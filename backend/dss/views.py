"""API DSS (Django): view chỉ nhận tham số, gọi mô hình trong etl/dss_models.py."""

import json
import math
from functools import lru_cache

import numpy as np
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from etl import dss_models as M
from etl import dss_attrib as A
from etl import dss_brief as B

from .models import ActionLog

# Dữ liệu kho chỉ nạp một lần khi module được import.
O = M.load_orders()

# Tỷ lệ trễ của TOÀN BỘ giai đoạn (không phụ thuộc ?year=). Dùng làm mốc cố
# định cho ngưỡng đỏ/vàng (2,0×L và 1,5×L) để nhãn tuyến không đổi khi lọc năm.
BASE_RATE = float(O["is_late"].mean())
BASE_RATE_LABEL = "overall rate of the full period"


def _config():
    return {
        "base_rate": BASE_RATE,
        "base_rate_label": BASE_RATE_LABEL,
        "grain": "order-route",
    }


def _year_value(request):
    """Chuẩn hoá tham số year thành ``"all"`` hoặc số nguyên (hashable)."""
    year = request.GET.get("year")
    if not year or year == "all":
        return "all"
    try:
        return int(year)
    except (TypeError, ValueError):
        raise ValueError("year phải là số nguyên, ví dụ 2017 hoặc 2018")


def _orders_for_year(year):
    """Lọc dữ liệu theo year đã chuẩn hoá; ``"all"`` = toàn bộ."""
    if year == "all":
        return O
    return O[O.period // 100 == year]


def _selected_orders(request):
    """Lọc theo year (tuỳ chọn). year rỗng hoặc 'all' nghĩa là toàn bộ dữ liệu."""
    return _orders_for_year(_year_value(request))


@lru_cache(maxsize=24)
def _attribution_bundle(year, quantile):
    """Fit benchmark + attribution một lần cho mỗi cặp (year, q).

    Cache theo ``(year, q)`` vì UI gọi cả q=0,5 và q=0,25 mỗi lần đổi năm.
    Không cache request/DataFrame đầu vào; chỉ cache kết quả đã tổng hợp.
    """
    orders = _orders_for_year(year)
    benchmarks = A.fit_benchmarks(orders, quantile=quantile)
    attributed = A.attribute(orders, benchmarks)
    summary = A.attribution_summary(attributed, min_orders=30)
    peers = A.route_peer_table(attributed, min_orders=30)

    late_rate = float(attributed["late_actual"].mean())
    systemwide = {
        "orders": int(len(attributed)),
        "late_rate": late_rate,
        "shares_in_late_orders": None,
        "grain": "order-route",
    }
    if late_rate > 0:
        systemwide["shares_in_late_orders"] = {
            **{
                f"share_{stage}": float(attributed[f"phi_{stage}"].mean() / late_rate)
                for stage in A.STAGES
            },
            "share_promise": float(
                attributed["late_benchmark"].mean() / late_rate
            ),
        }
    return summary, peers, systemwide, A.check_attrib(attributed)


def _bad(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _clean(value):
    """Đổi NaN/Infinity thành None để JSON hợp lệ với JavaScript."""
    if isinstance(value, np.generic):
        return _clean(value.item())
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

    rows = _records(M.route_priority(d, top=top, overall=BASE_RATE))
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
        "config": _config(),
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


@require_GET
def brief(request):
    try:
        orders = _selected_orders(request)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        result = B.decision_brief(
            orders, n_boot=300, seed=42, overall=BASE_RATE
        )
    except ValueError as exc:
        return _bad(str(exc))
    return JsonResponse(
        _clean(
            {
                key: _records(value)
                if hasattr(value, "to_dict")
                else value
                for key, value in result.items()
            }
            | {"config": _config()}
        )
    )


@require_GET
def attribution(request):
    q = request.GET.get("q", "0.5")
    try:
        quantile = float(q)
    except (TypeError, ValueError):
        return _bad("q chỉ nhận 0.25 hoặc 0.5; q=0.75 bị loại vì benchmark "
                    "chậm hơn actual, tạo phi âm và phân rã không hợp lệ.")
    if quantile not in (0.25, 0.5):
        return _bad("q chỉ nhận 0.25 hoặc 0.5; q=0.75 bị loại vì benchmark "
                    "chậm hơn actual, tạo phi âm và phân rã không hợp lệ.")
    try:
        year = _year_value(request)
        summary, peers, systemwide, invariants = _attribution_bundle(year, quantile)
    except ValueError as exc:
        return _bad(str(exc))
    return JsonResponse(
        _clean(
            {
                "q": quantile,
                "design": "Shapley attribution theo peer group",
                "grain": "order-route",
                "rows": _records(summary),
                # Bảng xếp hạng theo nền peer: expected_late_rate + excess_pp.
                # Giữ nguyên route_priority (so với tỷ lệ trễ hệ thống) ở /routes.
                "ranked_routes": _records(peers),
                "systemwide": systemwide,
                "invariants": invariants,
                "config": _config(),
            }
        )
    )


@require_GET
def promise_policy(request):
    try:
        orders = _selected_orders(request)
        calibration = A.promise_calibration(orders)
        table = A.promise_service_levels(
            orders, levels=(0.85, 0.90, 0.95), top=5,
            calibration=calibration,
        )
    except ValueError as exc:
        return _bad(str(exc))
    return JsonResponse(
        _clean(
            {
                "label": "mức phục vụ, không phải khuyến nghị đặt promise",
                "note": "Đổi định nghĩa trễ, không rút ngắn thời gian giao.",
                "rows": _records(table),
                "config": _config(),
            }
        )
    )


@require_GET
def sellers(request):
    try:
        orders = _selected_orders(request)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        scorecard = M.seller_scorecard(orders, min_orders=30)
    except ValueError as exc:
        return _bad(str(exc))
    return JsonResponse(
        _clean(
            {
                "summary": scorecard.attrs,
                "rows": _records(scorecard),
                "note": "Liên hệ mô tả, không phải kết luận nhân quả.",
                "config": _config(),
            }
        )
    )


@require_GET
def portfolio(request):
    try:
        orders = _selected_orders(request)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        scorecard = M.seller_scorecard(orders, min_orders=30)
        result = M.seller_portfolio(
            orders, min_orders=30, top=10, scorecard=scorecard
        )
        coverage = M.sellers_covering_late_share(scorecard, target=0.5)
    except ValueError as exc:
        return _bad(str(exc))
    return JsonResponse(
        _clean(
            {
                "summary": result["summary"],
                "segments": _records(result["segments"]),
                "top_sellers": _records(result["top_sellers"]),
                "coverage_50_percent": coverage,
                "note": "Liên hệ mô tả, không phải kết luận nhân quả.",
                "config": _config(),
            }
        )
    )
