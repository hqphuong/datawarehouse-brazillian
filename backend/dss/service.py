"""Framework-free DSS application service.

All formulas live in ``etl``.  This module only holds the request-independent
glue that used to sit in the Django views (year filtering, attribution bundle,
JSON cleaning, threshold/config lookup), so the Flask layer contains no
computation of its own.
"""

from __future__ import annotations

import inspect
import json
import math
from functools import lru_cache
from pathlib import Path
import sys
import threading

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl import dss_attrib as A  # noqa: E402
from etl import dss_brief as B  # noqa: E402
from etl import dss_models as M  # noqa: E402

# The warehouse snapshot is loaded once per process, exactly like the Django
# views did at import time.
O = M.load_orders()

# Full-period late rate.  This is the canonical value exposed by
# ``/brief.config`` and reused by every other endpoint.
BASE_RATE = float(O["is_late"].mean())
BASE_RATE_LABEL = "overall rate of the full period"

# Thresholds are not duplicated here: they are read from the parameter contract
# of ``etl.dss_brief.decision_brief``, i.e. the values reported by
# ``/brief.parameters``.  This keeps a single source of truth.
THRESHOLD_KEYS = ("min_orders", "seller_min_orders", "low_sample_threshold")
BRIEF_RUNTIME_KEYS = ("n_boot", "seed")


def brief_parameters() -> dict[str, int]:
    """Return the threshold block reported by ``/brief.parameters``."""
    signature = inspect.signature(B.decision_brief)
    return {
        key: int(signature.parameters[key].default) for key in THRESHOLD_KEYS
    }


def brief_runtime() -> dict[str, int]:
    """Runtime knobs mirrored from the same brief signature."""
    signature = inspect.signature(B.decision_brief)
    return {
        key: int(signature.parameters[key].default) for key in BRIEF_RUNTIME_KEYS
    }


def config() -> dict:
    """Payload of ``/brief.config`` (and every other endpoint's config)."""
    return {
        "base_rate": BASE_RATE,
        "base_rate_label": BASE_RATE_LABEL,
        "grain": "order-route",
    }


def year_value(params) -> str | int:
    """Normalise ``year`` to ``"all"`` or an integer (hashable)."""
    year = params.get("year")
    if not year or year == "all":
        return "all"
    try:
        return int(year)
    except (TypeError, ValueError):
        raise ValueError("year phải là số nguyên, ví dụ 2017 hoặc 2018")


def orders_for_year(year):
    if year == "all":
        return O
    return O[O.period // 100 == year]


def selected_orders(params):
    return orders_for_year(year_value(params))


@lru_cache(maxsize=24)
def attribution_bundle(year, quantile):
    """Fit benchmarks + attribution once per ``(year, q)``."""
    orders = orders_for_year(year)
    benchmarks = A.fit_benchmarks(orders, quantile=quantile)
    attributed = A.attribute(orders, benchmarks)
    peer_min = brief_parameters()["seller_min_orders"]
    summary = A.attribution_summary(attributed, min_orders=peer_min)
    peers = A.route_peer_table(attributed, min_orders=peer_min)

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
                f"share_{stage}": float(
                    attributed[f"phi_{stage}"].mean() / late_rate
                )
                for stage in A.STAGES
            },
            "share_promise": float(
                attributed["late_benchmark"].mean() / late_rate
            ),
        }
    return summary, peers, systemwide, A.check_attrib(attributed)


def clean(value):
    """NaN/Infinity -> None so the result is valid JavaScript JSON."""
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def records(df):
    # pandas to_json already maps NaN to null; clean() covers nested values.
    return json.loads(df.to_json(orient="records"))


def routes(d, top):
    rows = records(
        M.route_priority(
            d,
            top=top,
            overall=BASE_RATE,
            min_orders=brief_parameters()["min_orders"],
        )
    )
    for row in rows:
        row["root_cause"] = M.root_cause(d, row["route"])
    return rows


def scenario(d, route, cut):
    cause = M.root_cause(d, route)
    bottleneck = cause["stage"]
    base_cut = {k: v for k, v in cut.items() if k != bottleneck}
    return {
        **M.scenario(d, route, cut),
        "bottleneck": bottleneck,
        "has_bottleneck": cause["has_bottleneck"],
        "series": M.sensitivity(d, route, bottleneck, base_cut=base_cut),
        "config": config(),
    }


def promise(d, route, target):
    return M.goal_seek_promise(d, route, target)


def actions_listing(rows):
    return clean(rows)


def brief(orders):
    parameters = brief_parameters()
    runtime = brief_runtime()
    result = B.decision_brief(
        orders,
        n_boot=runtime["n_boot"],
        seed=runtime["seed"],
        overall=BASE_RATE,
        **parameters,
    )
    payload = {
        key: records(value) if hasattr(value, "to_dict") else value
        for key, value in result.items()
    }
    payload["config"] = config()
    return payload


# Decision Brief là phép bootstrap nặng (~25s mỗi lần). Cache theo năm để đổi
# năm / chuyển tab không phải tính lại. Khoá riêng từng năm giúp năm khác không
# bị chờ theo năm đang tính, đồng thời tránh hai luồng cùng tính một khoá.
_brief_cache: dict[str | int, dict] = {}
_brief_locks: dict[str | int, threading.Lock] = {}
_brief_guard = threading.Lock()


def brief_for_year(year):
    """Trả payload /brief của một năm, chỉ tính lần đầu cho mỗi năm."""
    with _brief_guard:
        if year in _brief_cache:
            return _brief_cache[year]
        lock = _brief_locks.setdefault(year, threading.Lock())
    with lock:
        with _brief_guard:
            if year in _brief_cache:
                return _brief_cache[year]
        result = brief(orders_for_year(year))
        with _brief_guard:
            _brief_cache[year] = result
        return result


def attribution(year, quantile):
    summary, peers, systemwide, invariants = attribution_bundle(year, quantile)
    return {
        "q": quantile,
        "design": "Shapley attribution theo peer group",
        "grain": "order-route",
        "rows": records(summary),
        "ranked_routes": records(peers),
        "systemwide": systemwide,
        "invariants": invariants,
        "config": config(),
    }


def promise_policy(orders):
    calibration = A.promise_calibration(orders)
    table = A.promise_service_levels(
        orders,
        levels=(0.85, 0.90, 0.95),
        top=5,
        calibration=calibration,
    )
    return {
        "label": "mức phục vụ, không phải khuyến nghị đặt promise",
        "note": "Đổi định nghĩa trễ, không rút ngắn thời gian giao.",
        "rows": records(table),
        "config": config(),
    }


def seller_scorecard(orders):
    return M.seller_scorecard(
        orders, min_orders=brief_parameters()["seller_min_orders"]
    )


def sellers(orders):
    scorecard = seller_scorecard(orders)
    return {
        "summary": scorecard.attrs,
        "rows": records(scorecard),
        "note": "Liên hệ mô tả, không phải kết luận nhân quả.",
        "config": config(),
    }


def portfolio(orders):
    scorecard = seller_scorecard(orders)
    result = M.seller_portfolio(
        orders,
        min_orders=brief_parameters()["seller_min_orders"],
        top=10,
        scorecard=scorecard,
    )
    coverage = M.sellers_covering_late_share(scorecard, target=0.5)
    return {
        "summary": result["summary"],
        "segments": records(result["segments"]),
        "top_sellers": records(result["top_sellers"]),
        "coverage_50_percent": coverage,
        "note": "Liên hệ mô tả, không phải kết luận nhân quả.",
        "config": config(),
    }
