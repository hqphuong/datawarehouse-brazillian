"""Recompute the key numbers printed in main.pdf from data/processed.

Chạy: ``python -m scripts.verify_report_numbers`` (từ thư mục gốc). Script không sửa dữ liệu; nó đọc
lại CSV đã làm sạch, gọi đúng các hàm DSS và so khớp với con số trong báo cáo.
Thoát mã 1 nếu bất kỳ mục nào lệch.

Phạm vi: số đơn/đơn-tuyến, L và ngưỡng đỏ/vàng, độ nhạy ngưỡng, bất biến
Shapley, bootstrap theo tuyến, feasible cut, promise GROSS/NET, seller
scorecard và backtest một bước.
"""

from __future__ import annotations

import sys

from etl import dss_attrib as A
from etl import dss_eval as E
from etl import dss_models as M

FAILURES: list[str] = []


def exact(name: str, actual: int, expected: int) -> None:
    ok = int(actual) == int(expected)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {actual} (báo cáo {expected})")
    if not ok:
        FAILURES.append(name)


def sequence(name: str, actual, expected) -> None:
    got = tuple(int(v) for v in actual)
    ok = got == tuple(int(v) for v in expected)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {got} (báo cáo {expected})")
    if not ok:
        FAILURES.append(name)


def rounded(name: str, actual: float, expected: float, digits: int) -> None:
    got = round(float(actual), digits)
    ok = abs(got - expected) < 10 ** (-(digits + 3))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {got} (báo cáo {expected})")
    if not ok:
        FAILURES.append(name)


def main() -> int:
    all_routes = M.load_orders(include_invalid=True)
    o = M.load_orders()

    # 3.2 / 5.2: quy mô và tỷ lệ trễ toàn kỳ
    exact("Số đơn đã giao (duy nhất)", all_routes["order_id"].nunique(), 96_455)
    exact("Số đơn-tuyến trước khi loại", len(all_routes), 96_981)
    exact("Số đơn-tuyến bị loại", o.attrs["excluded_stage_invalid_rows"], 1_390)
    rounded(
        "Tỷ lệ đơn-tuyến bị loại (%)",
        o.attrs["excluded_stage_invalid_share"] * 100,
        1.4333,
        4,
    )
    exact("Số đơn-tuyến phân tích", o.attrs["n_order_route"], 95_591)
    exact("Số đơn duy nhất phân tích", o.attrs["n_orders"], 95_082)

    late_rate = float(o["is_late"].mean())
    rounded("L = tỷ lệ trễ toàn kỳ (%)", late_rate * 100, 8.1556, 4)
    rounded("Ngưỡng đỏ 2,0L (%)", late_rate * 2.0 * 100, 16.31, 2)
    rounded("Ngưỡng vàng 1,5L (%)", late_rate * 1.5 * 100, 12.23, 2)

    flagged = M.route_priority(o, top=len(o))
    exact("Số tuyến gắn cờ", len(flagged), 14)
    exact("Số tuyến đỏ", int((flagged["level"] == "red").sum()), 6)
    exact("Số tuyến vàng", int((flagged["level"] == "amber").sum()), 8)

    # 5.2: độ nhạy ngưỡng tại min_orders=100
    sens = E.threshold_sensitivity(o, min_orders_values=(100,))
    sequence(
        "Độ nhạy ngưỡng (6 cặp, min_orders=100)",
        sens["flagged_routes"],
        (14, 14, 21, 21, 10, 6),
    )

    # 5.3: Shapley và bootstrap theo tuyến
    attributed = A.attribute(o, A.fit_benchmarks(o))
    invariants = A.check_attrib(attributed)
    exact("Số đơn-tuyến attribution", invariants["n_orders"], 95_591)
    for key, label in (
        ("l1_row_efficiency", "Bất biến L1"),
        ("l2_aggregate_efficiency", "Bất biến L2"),
        ("l3_validity", "Bất biến L3"),
        ("passed", "Cả ba bất biến"),
    ):
        ok = bool(invariants[key])
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {ok}")
        if not ok:
            FAILURES.append(label)

    bootstrap = E.route_level_bootstrap(o, reps=500, seed=42)
    exact("Bootstrap: transit top ở số tuyến", bootstrap["transit_rank_1_routes"], 165)
    exact("Bootstrap: số tuyến có đơn trễ", bootstrap["routes_with_late_orders"], 226)
    exact(
        "Bootstrap: transit top cấp hệ thống (lần)",
        bootstrap["transit_system_rank_1_reps"],
        500,
    )
    rounded(
        "Tỷ trọng transit q=0,5 - điểm (%)",
        float(attributed["phi_transit"].mean()) / float(attributed["late_actual"].mean()) * 100,
        69.8820,
        4,
    )
    rounded(
        "Tỷ trọng transit q=0,5 - bootstrap (%)",
        bootstrap["shares"]["share_transit"]["estimate"] * 100,
        69.9162,
        4,
    )

    # 5.4: feasible cut
    cut = A.feasible_cut_table(o, top=10, n_boot=300, seed=42)
    exact("Feasible cut: tổng top-5", int(cut["avoided_orders"].head(5).sum()), 2_352)
    exact("Feasible cut: tổng top-10", int(cut["avoided_orders"].sum()), 2_878)

    # 5.5: promise policy (GROSS / new late / NET)
    calibration = A.promise_calibration(o)
    attrs = calibration.attrs
    exact("Promise GROSS", attrs["gross_avoidable_orders"], 3_751)
    exact("Promise new late", attrs["new_late_orders"], 884)
    exact("Promise NET", attrs["net_avoided_orders"], 2_867)
    exact("Promise số ô giữ", attrs["n_cells_kept"], 130)
    exact("Promise tổng số ô", attrs["n_cells_total"], 1_157)
    exact("Promise đơn-tuyến trong ô giữ", attrs["n_orders_kept"], 83_104)

    # 5.6: seller scorecard
    scorecard = M.seller_scorecard(o, min_orders=30)
    exact("Tổng số người bán", len(scorecard), 2_948)
    exact("Số người bán đủ mẫu", scorecard.attrs["n_sellers_scored"], 609)
    segments = scorecard.attrs["segment_counts"]
    exact("Seller nhóm ưu tiên", segments.get("ưu tiên", 0), 252)
    exact("Seller nhóm ổn định", segments.get("ổn định", 0), 357)
    exact("Seller nhóm cần thêm dữ liệu", segments.get("cần thêm dữ liệu", 0), 2_339)
    seller_counts = o.groupby("order_id")["seller_id"].nunique()
    exact("Đơn một người bán", int((seller_counts == 1).sum()), 94_580)
    exact("Đơn nhiều người bán", int((seller_counts > 1).sum()), 502)

    # 7: backtest một bước
    _, summary = E.backtest(o, min_orders=30)
    exact("Backtest: số kỳ đánh giá", summary["periods_evaluated"], 19)
    exact("Backtest: số kỳ DSS tốt hơn", summary["higher_periods"], 16)
    rounded("Backtest: weighted_diff", summary["weighted_diff"], 0.082826, 6)

    print()
    if FAILURES:
        print(f"THẤT BẠI: {len(FAILURES)} mục lệch: {', '.join(FAILURES)}")
        return 1
    print("TẤT CẢ SỐ LIỆU KHỚP BÁO CÁO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
