"""Compare tests/golden/django.json with tests/golden/flask.json."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

GOLDEN = Path(__file__).resolve().parent / "golden"
HEADERS = [
    "content-type",
    "vary",
    "access-control-allow-origin",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-max-age",
    "allow",
]
ENDPOINTS = [
    "routes",
    "scenario",
    "promise",
    "actions",
    "brief",
    "attribution",
    "promise-policy",
    "sellers",
    "portfolio",
]


def _diff(expected, actual, path="body"):
    """Return a list of minimal structural/value/type differences."""
    problems = []
    if type(expected) is not type(actual):
        # bool is a subclass of int; type() already separates them.
        return [f"{path}: type {type(expected).__name__} != {type(actual).__name__}"]
    if isinstance(expected, dict):
        if list(expected) != list(actual):
            problems.append(f"{path}: key order {list(expected)} != {list(actual)}")
        for key in expected:
            if key not in actual:
                problems.append(f"{path}.{key}: missing")
            else:
                problems.extend(_diff(expected[key], actual[key], f"{path}.{key}"))
        for key in actual:
            if key not in expected:
                problems.append(f"{path}.{key}: unexpected")
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            problems.append(f"{path}: length {len(expected)} != {len(actual)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            problems.extend(_diff(left, right, f"{path}[{index}]"))
    elif isinstance(expected, float):
        if expected != actual or math.copysign(1, expected) != math.copysign(1, actual):
            problems.append(f"{path}: {expected!r} != {actual!r}")
    elif expected != actual:
        problems.append(f"{path}: {expected!r} != {actual!r}")
    return problems


def _endpoint(case_id: str) -> str:
    prefixes = [
        ("promise_policy", "promise-policy"),
        ("attribution", "attribution"),
        ("scenario", "scenario"),
        ("promise", "promise"),
        ("actions", "actions"),
        ("routes", "routes"),
        ("brief", "brief"),
        ("sellers", "sellers"),
        ("portfolio", "portfolio"),
    ]
    for prefix, name in prefixes:
        if case_id.startswith(prefix + "_"):
            return name
    return "framework"


def compare():
    baseline = {
        row["id"]: row
        for row in json.loads((GOLDEN / "django.json").read_text(encoding="utf-8"))
    }
    current = {
        row["id"]: row
        for row in json.loads((GOLDEN / "flask.json").read_text(encoding="utf-8"))
    }
    if list(baseline) != list(current):
        raise SystemExit("case ids/order differ between snapshots")

    summary = {}
    failures = []
    for case_id, expected in baseline.items():
        actual = current[case_id]
        status_ok = expected["status"] == actual["status"]
        header_problems = []
        for name in HEADERS:
            left = expected["headers"].get(name)
            right = actual["headers"].get(name)
            if name == "vary" and left and right:
                left, right = left.lower(), right.lower()
            if left != right:
                header_problems.append(f"header {name}: {left!r} != {right!r}")
        if expected["body_kind"] == "json":
            body_problems = _diff(expected["body"], actual["body"])
            body_ok = not body_problems
        else:
            body_problems = []
            body_ok = (
                expected["body_kind"] == actual["body_kind"]
                and expected["body_text"] == actual["body_text"]
            )
            if not body_ok:
                body_problems = [
                    f"body_text: {expected['body_text']!r} != {actual['body_text']!r}"
                ]
        headers_ok = not header_problems
        endpoint = _endpoint(case_id)
        slot = summary.setdefault(
            endpoint,
            {"status": True, "body": True, "headers": True, "cases": 0, "fails": []},
        )
        slot["cases"] += 1
        slot["status"] &= status_ok
        slot["body"] &= body_ok
        slot["headers"] &= headers_ok
        if not (status_ok and body_ok and headers_ok):
            details = header_problems + body_problems
            if not status_ok:
                details.insert(0, f"status {expected['status']} != {actual['status']}")
            slot["fails"].append((case_id, details))
            failures.append((case_id, details))

    print("| Endpoint | Status | Body | Headers | Cases |")
    print("|---|---|---|---|---|")
    for name in ENDPOINTS + ["framework"]:
        slot = summary[name]
        mark = lambda ok: "PASS" if ok else "FAIL"  # noqa: E731
        print(
            f"| {name} | {mark(slot['status'])} | {mark(slot['body'])} | "
            f"{mark(slot['headers'])} | {slot['cases']} |"
        )

    if failures:
        print("\nMinimal diffs:")
        for case_id, details in failures:
            print(f"- {case_id}")
            for detail in details[:12]:
                print(f"    {detail}")
        return 1
    print("\nPARITY OK")
    return 0


if __name__ == "__main__":
    sys.exit(compare())
