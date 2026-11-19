"""Flask blueprint for /api/dss/*.  Mirrors the former Django view contract."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, request

from . import db, service as S

bp = Blueprint("dss", __name__, url_prefix="/api/dss")

Q_ERROR = (
    "q chỉ nhận 0.25 hoặc 0.5; q=0.75 bị loại vì benchmark "
    "chậm hơn actual, tạo phi âm và phân rã không hợp lệ."
)


def _json(payload, status=200):
    return current_app.response_class(
        current_app.json.dumps(payload),
        status=status,
        mimetype="application/json",
    )


def _bad(message, status=400):
    return _json({"error": message}, status=status)


@bp.get("/routes")
def routes():
    try:
        d = S.selected_orders(request.args)
    except ValueError as exc:
        return _bad(str(exc))

    top = request.args.get("top")
    try:
        top = int(top) if top is not None else 10
    except (TypeError, ValueError):
        return _bad("top phải là số nguyên dương")
    if top < 1:
        return _bad("top phải là số nguyên dương")

    return _json(S.clean(S.routes(d, top)))


@bp.get("/scenario")
def scenario():
    route = request.args.get("route")
    if not route:
        return _bad("thiếu tham số route")

    try:
        d = S.selected_orders(request.args)
        cut = {
            k: float(request.args.get(k, 0) or 0)
            for k in ("approval", "prep", "transit")
        }
    except ValueError:
        return _bad("approval/prep/transit/year phải là số hợp lệ")

    if not (d.route == route).any():
        return _bad(f"không có dữ liệu cho tuyến {route}")

    return _json(S.clean(S.scenario(d, route, cut)))


@bp.get("/promise")
def promise():
    route = request.args.get("route")
    if not route:
        return _bad("thiếu tham số route")

    try:
        d = S.selected_orders(request.args)
        target = float(request.args.get("target", 0.05))
    except ValueError:
        return _bad("target/year phải là số hợp lệ")
    if not 0 <= target <= 1:
        return _bad("target phải nằm trong khoảng 0..1 (ví dụ 0.05)")

    if not (d.route == route).any():
        return _bad(f"không có dữ liệu cho tuyến {route}")

    return _json(S.clean(S.promise(d, route, target)))


@bp.route("/actions", methods=["GET", "POST"])
def actions():
    if request.method == "POST":
        try:
            body = json.loads(request.get_data() or b"{}")
        except (TypeError, ValueError):
            return _bad("JSON không hợp lệ")
        if not isinstance(body, dict):
            return _bad("JSON phải là một object")

        db.insert_action(body, current_app.config)
        return _json({"ok": True})

    rows = db.list_actions(current_app.config)
    return _json(S.actions_listing(rows))


@bp.get("/brief")
def brief():
    try:
        year = S.year_value(request.args)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        result = S.brief_for_year(year)
    except ValueError as exc:
        return _bad(str(exc))
    return _json(S.clean(result))


@bp.get("/attribution")
def attribution():
    q = request.args.get("q", "0.5")
    try:
        quantile = float(q)
    except (TypeError, ValueError):
        return _bad(Q_ERROR)
    if quantile not in (0.25, 0.5):
        return _bad(Q_ERROR)
    try:
        year = S.year_value(request.args)
        result = S.attribution(year, quantile)
    except ValueError as exc:
        return _bad(str(exc))
    return _json(S.clean(result))


@bp.get("/promise-policy")
def promise_policy():
    try:
        orders = S.selected_orders(request.args)
        result = S.promise_policy(orders)
    except ValueError as exc:
        return _bad(str(exc))
    return _json(S.clean(result))


@bp.get("/sellers")
def sellers():
    try:
        orders = S.selected_orders(request.args)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        result = S.sellers(orders)
    except ValueError as exc:
        return _bad(str(exc))
    return _json(S.clean(result))


@bp.get("/portfolio")
def portfolio():
    try:
        orders = S.selected_orders(request.args)
    except ValueError as exc:
        return _bad(str(exc))
    try:
        result = S.portfolio(orders)
    except ValueError as exc:
        return _bad(str(exc))
    return _json(S.clean(result))
