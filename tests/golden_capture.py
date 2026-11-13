"""Capture the DSS API golden snapshot from either the Django or Flask app.

Usage (from repo root, with backend\\env on PATH):

    python tests\\golden_capture.py django
    python tests\\golden_capture.py flask

Writes tests/golden/<target>.json.  Cases are deterministic: the action log is
cleared before and after the run, and created_at values are masked in the
snapshot (their presence/type is still asserted by the comparer).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Headers that form part of the public contract. Values are compared
# case-insensitively, and only when present in the Django baseline.
HEADER_NAMES = [
    "content-type",
    "vary",
    "access-control-allow-origin",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-max-age",
    "allow",
]

ORIGIN = "null"

CASES = [
    # --- success paths, all / 2017 / 2018 ---
    {"id": "routes_all", "method": "GET", "path": "/api/dss/routes"},
    {"id": "routes_2017", "method": "GET", "path": "/api/dss/routes?year=2017"},
    {"id": "routes_2018", "method": "GET", "path": "/api/dss/routes?year=2018"},
    {"id": "routes_top100", "method": "GET", "path": "/api/dss/routes?top=100"},
    {"id": "scenario_all", "method": "GET", "path": "/api/dss/scenario?route=SP-%3ERJ"},
    {"id": "scenario_2017", "method": "GET", "path": "/api/dss/scenario?route=SP-%3ERJ&year=2017"},
    {"id": "scenario_2018", "method": "GET", "path": "/api/dss/scenario?route=SP-%3ERJ&year=2018"},
    {"id": "scenario_cut", "method": "GET", "path": "/api/dss/scenario?route=SP-%3ERJ&prep=2&transit=1"},
    {"id": "promise_all", "method": "GET", "path": "/api/dss/promise?route=SP-%3ERJ&target=0.05"},
    {"id": "promise_2017", "method": "GET", "path": "/api/dss/promise?route=SP-%3ERJ&target=0.05&year=2017"},
    {"id": "promise_2018", "method": "GET", "path": "/api/dss/promise?route=SP-%3ERJ&target=0.05&year=2018"},
    {"id": "actions_get_empty", "method": "GET", "path": "/api/dss/actions"},
    {
        "id": "actions_post_valid",
        "method": "POST",
        "path": "/api/dss/actions",
        "body": '{"action":"extend_promise","route":"SP->RJ","level":"amber","extra_days":15}',
    },
    {"id": "actions_get_after_post", "method": "GET", "path": "/api/dss/actions"},
    {"id": "actions_post_empty_body", "method": "POST", "path": "/api/dss/actions", "body": ""},
    {"id": "brief_all", "method": "GET", "path": "/api/dss/brief"},
    {"id": "brief_2017", "method": "GET", "path": "/api/dss/brief?year=2017"},
    {"id": "brief_2018", "method": "GET", "path": "/api/dss/brief?year=2018"},
    {"id": "attribution_all_q50", "method": "GET", "path": "/api/dss/attribution?q=0.5"},
    {"id": "attribution_all_q25", "method": "GET", "path": "/api/dss/attribution?q=0.25"},
    {"id": "attribution_2017", "method": "GET", "path": "/api/dss/attribution?q=0.5&year=2017"},
    {"id": "attribution_2018", "method": "GET", "path": "/api/dss/attribution?q=0.5&year=2018"},
    {"id": "promise_policy_all", "method": "GET", "path": "/api/dss/promise-policy"},
    {"id": "promise_policy_2017", "method": "GET", "path": "/api/dss/promise-policy?year=2017"},
    {"id": "promise_policy_2018", "method": "GET", "path": "/api/dss/promise-policy?year=2018"},
    {"id": "sellers_all", "method": "GET", "path": "/api/dss/sellers"},
    {"id": "sellers_2017", "method": "GET", "path": "/api/dss/sellers?year=2017"},
    {"id": "sellers_2018", "method": "GET", "path": "/api/dss/sellers?year=2018"},
    {"id": "portfolio_all", "method": "GET", "path": "/api/dss/portfolio"},
    {"id": "portfolio_2017", "method": "GET", "path": "/api/dss/portfolio?year=2017"},
    {"id": "portfolio_2018", "method": "GET", "path": "/api/dss/portfolio?year=2018"},
    # --- error paths ---
    {"id": "err_routes_year", "method": "GET", "path": "/api/dss/routes?year=abc"},
    {"id": "err_routes_top_zero", "method": "GET", "path": "/api/dss/routes?top=0"},
    {"id": "err_routes_top_text", "method": "GET", "path": "/api/dss/routes?top=abc"},
    {"id": "err_scenario_missing", "method": "GET", "path": "/api/dss/scenario"},
    {"id": "err_scenario_unknown", "method": "GET", "path": "/api/dss/scenario?route=XX-%3EYY"},
    {"id": "err_scenario_cut", "method": "GET", "path": "/api/dss/scenario?route=SP-%3ERJ&prep=abc"},
    {"id": "err_promise_missing", "method": "GET", "path": "/api/dss/promise"},
    {"id": "err_promise_target_range", "method": "GET", "path": "/api/dss/promise?route=SP-%3ERJ&target=2"},
    {"id": "err_promise_target_text", "method": "GET", "path": "/api/dss/promise?route=SP-%3ERJ&target=abc"},
    {"id": "err_promise_unknown", "method": "GET", "path": "/api/dss/promise?route=XX-%3EYY"},
    {"id": "err_brief_year", "method": "GET", "path": "/api/dss/brief?year=abc"},
    {"id": "err_attribution_q75", "method": "GET", "path": "/api/dss/attribution?q=0.75"},
    {"id": "err_attribution_q_text", "method": "GET", "path": "/api/dss/attribution?q=abc"},
    {"id": "err_attribution_year", "method": "GET", "path": "/api/dss/attribution?year=abc"},
    {"id": "err_promise_policy_year", "method": "GET", "path": "/api/dss/promise-policy?year=abc"},
    {"id": "err_sellers_year", "method": "GET", "path": "/api/dss/sellers?year=abc"},
    {"id": "err_portfolio_year", "method": "GET", "path": "/api/dss/portfolio?year=abc"},
    {
        "id": "err_actions_bad_json",
        "method": "POST",
        "path": "/api/dss/actions",
        "body": "{not-json",
    },
    {
        "id": "err_actions_not_object",
        "method": "POST",
        "path": "/api/dss/actions",
        "body": "[1,2]",
    },
    # --- framework-level behavior ---
    {"id": "err_route_post_405", "method": "POST", "path": "/api/dss/routes"},
    {"id": "err_trailing_slash_404", "method": "GET", "path": "/api/dss/routes/"},
    {
        "id": "cors_preflight_actions",
        "method": "OPTIONS",
        "path": "/api/dss/actions",
        "preflight": True,
    },
]

CREATED_AT = re.compile(r'"created_at":\s*"[^"]*"')


def _clean_body(body: str, case: dict) -> str:
    """Mask only the non-deterministic action timestamp."""
    return CREATED_AT.sub('"created_at": "<timestamp>"', body)


def _normalize_json(value):
    return value


def _collect_headers(headers) -> dict:
    lowered = {k.lower(): v for k, v in headers.items()}
    return {name: lowered.get(name) for name in HEADER_NAMES}


def _run_django(cases):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django

    django.setup()
    from django.test import Client, override_settings

    from dss.models import ActionLog

    ActionLog.objects.all().delete()
    client = Client(HTTP_HOST="localhost")
    out = []
    try:
        with override_settings(DEBUG=False):
            for case in cases:
                kwargs = {"HTTP_ORIGIN": ORIGIN}
                if case.get("preflight"):
                    kwargs["HTTP_ACCESS_CONTROL_REQUEST_METHOD"] = "POST"
                    kwargs["HTTP_ACCESS_CONTROL_REQUEST_HEADERS"] = "content-type"
                if case["method"] == "POST":
                    res = client.post(
                        case["path"],
                        data=case.get("body", ""),
                        content_type="application/json",
                        **kwargs,
                    )
                else:
                    res = client.generic(case["method"], case["path"], **kwargs)
                out.append(_snapshot(case, res.status_code, res.headers, res.content))
    finally:
        ActionLog.objects.all().delete()
    return out


def _run_flask(cases):
    from dss import db
    from dss.app import create_app

    app = create_app({"TESTING": True})
    db.clear_actions()
    client = app.test_client()
    out = []
    try:
        for case in cases:
            headers = {"Origin": ORIGIN}
            if case.get("preflight"):
                headers["Access-Control-Request-Method"] = "POST"
                headers["Access-Control-Request-Headers"] = "content-type"
            kwargs = {"headers": headers}
            if case["method"] == "POST":
                kwargs["data"] = case.get("body", "")
                kwargs["content_type"] = "application/json"
            res = client.open(case["path"], method=case["method"], **kwargs)
            out.append(_snapshot(case, res.status_code, res.headers, res.data))
    finally:
        db.clear_actions()
    return out


def _snapshot(case, status, headers, raw: bytes) -> dict:
    text = raw.decode("utf-8")
    body_text = _clean_body(text, case)
    try:
        payload = json.loads(body_text)
        body = _normalize_json(payload)
        body_kind = "json"
    except (ValueError, UnicodeDecodeError):
        body = None
        body_kind = "html/empty" if "text/html" in headers.get("Content-Type", "") else "text"
    return {
        "id": case["id"],
        "method": case["method"],
        "path": case["path"],
        "request_body": case.get("body"),
        "status": status,
        "headers": _collect_headers(headers),
        "body_kind": body_kind,
        "body": body,
        "body_text": body_text if body_kind != "json" else None,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"django", "flask"}:
        print("usage: python tests/golden_capture.py django|flask")
        return 2
    target = argv[1]
    rows = _run_django(CASES) if target == "django" else _run_flask(CASES)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    destination = GOLDEN_DIR / f"{target}.json"
    destination.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(rows)} cases -> {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
