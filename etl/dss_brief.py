"""S6: Decision Brief — gom hành động theo 4 loại, không cộng chéo loại.

Brief chỉ là lớp trình bày: mọi con số lấy từ S3 (promise), S4 (route/payment),
S5 (seller), S7 (low-sample). Các nhóm hành động **chồng lấn** trên cùng đơn-tuyến
(ví dụ một tuyến vừa có hành động route vừa có hành động payment), nên tuyệt đối
không cộng ``avoided_orders`` giữa các loại. Chỉ được cộng trong cùng một loại.

Quy ước câu chữ: "NẾU ... THÌ ƯỚC TÍNH ...". Đây là mô
phỏng theo luật, không phải counterfactual thật. Promise dùng **NET** (đã trừ
đơn trễ mới do siết ô loose), không dùng GROSS.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:  # chạy như package: python -m etl.dss_brief
    from . import dss_attrib as ATTRIB
    from . import dss_models as M
except ImportError:  # chạy trực tiếp: python etl/dss_brief.py
    import dss_attrib as ATTRIB
    import dss_models as M

PROMISE_OWNER = "Vận hành cam kết giao hàng"
LOW_SAMPLE_OWNER = "Đội dữ liệu / vận hành tuyến"

ROUTE_COLUMNS = [
    "route",
    "stage",
    "owner",
    "gmv",
    "action",
    "avoided_orders",
    "avoided_ci_low",
    "avoided_ci_high",
    "delta_pp",
    "delta_ci_low_pp",
    "delta_ci_high_pp",
    "status",
    "peer_p50_total_days",
]
PAYMENT_COLUMNS = [
    "payment_type",
    "owner",
    "gmv",
    "action",
    "avoided_orders",
    "avoided_ci_low",
    "avoided_ci_high",
    "delta_pp",
    "delta_ci_low_pp",
    "delta_ci_high_pp",
    "status",
]
PROMISE_COLUMNS = [
    "route",
    "weight_band",
    "owner",
    "gmv",
    "action",
    "needed_days",
    "net_avoided_orders",
    "new_late_orders",
    "late_orders",
    "label",
]
SELLER_COLUMNS = [
    "seller_id",
    "owner",
    "gmv",
    "action",
    "orders",
    "late_orders",
    "late_rate",
    "wilson_low",
    "wilson_high",
    "level",
    "segment",
    "estimated_excess_late_orders",
]
LOW_SAMPLE_COLUMNS = [
    "route",
    "owner",
    "gmv",
    "action",
    "orders",
    "late_orders",
    "late_rate",
    "level",
    "needed_orders",
    "in_flagged",
    "flagged_rank",
    "status",
]


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _fmt_gmv(value) -> str:
    """Định dạng GMV kiểu Việt Nam: phân cách nghìn bằng dấu chấm."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "—"
    if np.isnan(f) or np.isinf(f):
        return "—"
    return f"{f:,.0f}".replace(",", ".")


def _gmv_map(o: pd.DataFrame, keys) -> dict:
    """Tổng GMV theo khóa (một khóa hoặc list khóa); rỗng nếu thiếu cột gmv."""
    if "gmv" not in o.columns:
        return {}
    grouped = o.groupby(keys, as_index=False)["gmv"].sum()
    if isinstance(keys, str):
        return {
            row[keys]: int(round(float(row["gmv"])))
            for _, row in grouped.iterrows()
        }
    return {
        tuple(row[k] for k in keys): int(round(float(row["gmv"])))
        for _, row in grouped.iterrows()
    }


def _dominant_stage(cuts: dict[str, float]) -> str:
    positive = {s: v for s, v in cuts.items() if v > 0}
    if not positive:
        return max(cuts, key=cuts.get)
    return max(positive, key=positive.get)


def _route_actions(
    route_table: pd.DataFrame, route_gmv: dict | None = None
) -> pd.DataFrame:
    if len(route_table) == 0:
        return _empty(ROUTE_COLUMNS)
    route_gmv = route_gmv or {}
    rows = []
    for _, r in route_table.iterrows():
        cuts = {s: float(r.get(f"cut_{s}", 0.0)) for s in M.STAGES}
        stage = _dominant_stage(cuts)
        cut = cuts[stage]
        avoided = int(r["avoided_orders"])
        lo = int(r["avoided_ci_low"])
        hi = int(r["avoided_ci_high"])
        gmv = int(route_gmv.get(r["route"], 0))
        rows.append(
            {
                "route": r["route"],
                "stage": stage,
                "owner": M.OWNER[stage],
                "gmv": gmv,
                "action": (
                    f"Nếu rút ngắn {stage} của tuyến {r['route']} khoảng "
                    f"{cut:.2f} ngày (về peer P25), thì ước tính tránh "
                    f"{avoided} đơn trễ (CI {lo}–{hi}); GMV tuyến "
                    f"{_fmt_gmv(gmv)}."
                ),
                "avoided_orders": avoided,
                "avoided_ci_low": lo,
                "avoided_ci_high": hi,
                "delta_pp": float(r["delta_pp"]),
                "delta_ci_low_pp": float(r["delta_ci_low_pp"]),
                "delta_ci_high_pp": float(r["delta_ci_high_pp"]),
                "status": r["status"],
                "peer_p50_total_days": float(r.get("peer_p50_total_days", np.nan)),
            }
        )
    return pd.DataFrame(rows, columns=ROUTE_COLUMNS)


def _payment_actions(
    payment_table: pd.DataFrame, payment_gmv: dict | None = None
) -> pd.DataFrame:
    if len(payment_table) == 0:
        return _empty(PAYMENT_COLUMNS)
    payment_gmv = payment_gmv or {}
    rows = []
    for _, r in payment_table.iterrows():
        cut = float(r["cut_approval"])
        avoided = int(r["avoided_orders"])
        lo = int(r["avoided_ci_low"])
        hi = int(r["avoided_ci_high"])
        gmv = int(payment_gmv.get(r["payment_type"], 0))
        rows.append(
            {
                "payment_type": r["payment_type"],
                "owner": M.OWNER["approval"],
                "gmv": gmv,
                "action": (
                    f"Nếu rút ngắn duyệt thanh toán cho {r['payment_type']} "
                    f"khoảng {cut:.2f} ngày (về peer P25), thì ước tính tránh "
                    f"{avoided} đơn trễ (CI {lo}–{hi}); GMV nhóm "
                    f"{_fmt_gmv(gmv)}."
                ),
                "avoided_orders": avoided,
                "avoided_ci_low": lo,
                "avoided_ci_high": hi,
                "delta_pp": float(r["delta_pp"]),
                "delta_ci_low_pp": float(r["delta_ci_low_pp"]),
                "delta_ci_high_pp": float(r["delta_ci_high_pp"]),
                "status": r["status"],
            }
        )
    return pd.DataFrame(rows, columns=PAYMENT_COLUMNS)


def _promise_actions(
    calibration: pd.DataFrame, top: int, cell_gmv: dict | None = None
) -> tuple[pd.DataFrame, dict]:
    attrs = calibration.attrs
    summary = {
        "late_orders_before": int(attrs.get("late_orders_kept", 0)),
        "late_orders_after": int(attrs.get("calibrated_late_orders", 0)),
        "net_avoided_orders": int(attrs.get("net_avoided_orders", 0)),
        "new_late_orders": int(attrs.get("new_late_orders", 0)),
        "late_rate_before": (
            float(attrs.get("late_orders_kept", 0)) / attrs["n_orders_kept"]
            if attrs.get("n_orders_kept")
            else float("nan")
        ),
        "late_rate_after": (
            float(attrs.get("calibrated_late_orders", 0)) / attrs["n_orders_kept"]
            if attrs.get("n_orders_kept")
            else float("nan")
        ),
        "n_cells_kept": int(attrs.get("n_cells_kept", 0)),
        "min_orders": int(attrs.get("min_orders", 0)),
    }
    if len(calibration) == 0:
        return _empty(PROMISE_COLUMNS), summary

    ranked = calibration.sort_values(
        ["net_avoided_orders", "avoidable_orders", "n_orders"],
        ascending=[False, False, False],
    ).head(top)
    cell_gmv = cell_gmv or {}
    rows = []
    for _, r in ranked.iterrows():
        net = int(r["net_avoided_orders"])
        new = int(r["new_late_orders"])
        gmv = int(cell_gmv.get((r["route"], r["weight_band"]), 0))
        rows.append(
            {
                "route": r["route"],
                "weight_band": r["weight_band"],
                "owner": PROMISE_OWNER,
                "gmv": gmv,
                "action": (
                    f"Nếu đặt promise = {int(r['needed_days'])} ngày cho ô "
                    f"{r['route']} × {r['weight_band']}, thì ước tính NET "
                    f"{net} đơn trễ được phân loại lại là đúng hạn theo "
                    f"promise mới (phát sinh {new} đơn trễ mới); đổi định nghĩa "
                    f"trễ, không rút ngắn thời gian giao. GMV ô {_fmt_gmv(gmv)}."
                ),
                "needed_days": int(r["needed_days"]),
                "net_avoided_orders": net,
                "new_late_orders": new,
                "late_orders": int(r["late_orders"]),
                "label": r["label"],
            }
        )
    return pd.DataFrame(rows, columns=PROMISE_COLUMNS), summary


def _seller_actions(
    seller_card: pd.DataFrame, system_late_rate: float, top: int,
    seller_gmv: dict | None = None,
) -> pd.DataFrame:
    if len(seller_card) == 0:
        return _empty(SELLER_COLUMNS)
    priority = seller_card[seller_card["segment"] == "ưu tiên"].copy()
    priority["estimated_excess_late_orders"] = np.maximum(
        0,
        np.rint(
            priority["late_orders"].astype(float)
            - priority["orders"].astype(float) * float(system_late_rate)
        ),
    ).astype(int)
    priority = priority.sort_values(
        ["estimated_excess_late_orders", "orders"], ascending=False
    ).head(top)
    seller_gmv = seller_gmv or {}
    rows = []
    for _, r in priority.iterrows():
        excess = int(r["estimated_excess_late_orders"])
        rows.append(
            {
                "seller_id": r["seller_id"],
                "owner": M.OWNER["prep"],
                "gmv": int(round(float(seller_gmv.get(r["seller_id"], r["gmv"])))),
                "action": (
                    f"Làm việc với seller {str(r['seller_id'])[:8]}…: "
                    f"{int(r['late_orders'])} đơn trễ, tỷ lệ "
                    f"{float(r['late_rate']):.2%} (CI {float(r['wilson_low']):.2%}–"
                    f"{float(r['wilson_high']):.2%}); ước tính "
                    f"{excess} đơn trễ vượt mức hệ thống (liên hệ, không phải "
                    f"đơn tránh được); GMV seller "
                    f"{_fmt_gmv(seller_gmv.get(r['seller_id'], r['gmv']))}."
                ),
                "orders": int(r["orders"]),
                "late_orders": int(r["late_orders"]),
                "late_rate": float(r["late_rate"]),
                "wilson_low": float(r["wilson_low"]),
                "wilson_high": float(r["wilson_high"]),
                "level": r["level"],
                "segment": r["segment"],
                "estimated_excess_late_orders": excess,
            }
        )
    return pd.DataFrame(rows, columns=SELLER_COLUMNS)


def _low_sample_actions(
    o: pd.DataFrame,
    low_sample_table: pd.DataFrame,
    top: int,
    min_orders: int,
    low_sample_threshold: int,
    route_gmv: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    check = M.route_flag_check(
        o,
        low_sample_table["route"].tolist() if len(low_sample_table) else [],
        min_orders=min_orders,
        low_sample_threshold=low_sample_threshold,
    )
    if len(low_sample_table) == 0:
        return _empty(LOW_SAMPLE_COLUMNS), check
    merged = low_sample_table.merge(
        check[["route", "in_flagged", "flagged_rank"]],
        on="route",
        how="left",
        suffixes=("", "_check"),
    )
    merged = merged.sort_values(
        ["late_orders", "orders"], ascending=False
    ).head(top)
    route_gmv = route_gmv or {}
    rows = []
    for _, r in merged.iterrows():
        needed = int(r["needed_orders"])
        rows.append(
            {
                "route": r["route"],
                "owner": LOW_SAMPLE_OWNER,
                "gmv": int(route_gmv.get(r["route"], 0)),
                "action": (
                    f"Thu thập thêm {needed} đơn cho tuyến {r['route']} rồi "
                    f"đánh giá lại (hiện {int(r['orders'])} đơn, "
                    f"{int(r['late_orders'])} trễ; GMV tuyến "
                    f"{_fmt_gmv(route_gmv.get(r['route'], 0))})."
                ),
                "orders": int(r["orders"]),
                "late_orders": int(r["late_orders"]),
                "late_rate": float(r["late_rate"]),
                "level": r["level"],
                "needed_orders": needed,
                "in_flagged": bool(r["in_flagged"]),
                "flagged_rank": (
                    int(r["flagged_rank"])
                    if pd.notna(r["flagged_rank"])
                    else None
                ),
                "status": "cần thêm dữ liệu",
            }
        )
    return pd.DataFrame(rows, columns=LOW_SAMPLE_COLUMNS), check


def decision_brief(
    o: pd.DataFrame,
    top_routes: int = 5,
    top_payment: int = 5,
    top_sellers: int = 5,
    top_low_sample: int = 5,
    min_orders: int = 100,
    seller_min_orders: int = 30,
    low_sample_threshold: int = 200,
    n_boot: int = 300,
    seed: int = 42,
    route_table: pd.DataFrame | None = None,
    payment_table: pd.DataFrame | None = None,
    calibration: pd.DataFrame | None = None,
    seller_card: pd.DataFrame | None = None,
    seller_port: dict | None = None,
    low_sample_table: pd.DataFrame | None = None,
) -> dict:
    """Tạo Decision Brief (S6) từ các mô hình S3/S4/S5/S7.

    Trả về dict gồm 4 nhóm hành động tách biệt + nhóm "cần thêm dữ liệu":

    - ``route_actions``: S4, top theo ``avoided_orders`` (mô phỏng cắt P25).
    - ``payment_actions``: S4 mở rộng theo ``payment_type``, chỉ cắt approval.
    - ``promise_actions`` + ``promise_summary``: S3, chỉ dùng **NET**.
    - ``seller_actions``: S5, seller segment "ưu tiên".
    - ``low_sample_actions`` + ``low_sample_check``: S7.

    Không có tổng ``avoided_orders`` xuyên loại. Các tham số cho phép truyền
    bảng đã tính sẵn để tái dùng (tránh bootstrap lặp).
    """
    if top_routes < 1 or top_payment < 1 or top_sellers < 1:
        raise ValueError("top_routes/top_payment/top_sellers phải >= 1")
    if top_low_sample < 0:
        raise ValueError("top_low_sample phải >= 0")
    if len(o) == 0:
        raise ValueError("Không có dòng nào để decision_brief")

    if route_table is None:
        route_table = ATTRIB.feasible_cut_table(
            o,
            min_orders=min_orders,
            top=top_routes,
            n_boot=n_boot,
            seed=seed,
        )
    if payment_table is None:
        payment_table = ATTRIB.approval_action_table(
            o,
            min_orders=min_orders,
            top=top_payment,
            n_boot=n_boot,
            seed=seed,
        )
    if calibration is None:
        calibration = ATTRIB.promise_calibration(o, min_orders=min_orders)
    if seller_card is None:
        seller_card = M.seller_scorecard(o, min_orders=seller_min_orders)
    if seller_port is None:
        seller_port = M.seller_portfolio(
            o, min_orders=seller_min_orders, top=top_sellers, scorecard=seller_card
        )
    route_gmv = _gmv_map(o, "route")
    if low_sample_table is None:
        low_sample_table = M.low_sample_targets(
            o, min_orders=low_sample_threshold, top=top_low_sample
        )

    payment_gmv = (
        _gmv_map(o, "payment_type") if "payment_type" in o.columns else {}
    )
    cell_gmv = _gmv_map(o, ["route", "weight_band"])
    route_actions = _route_actions(route_table, route_gmv=route_gmv)
    payment_actions = _payment_actions(payment_table, payment_gmv=payment_gmv)
    promise_actions, promise_summary = _promise_actions(
        calibration, top=top_routes, cell_gmv=cell_gmv
    )
    seller_gmv = (
        dict(zip(seller_card["seller_id"], seller_card["gmv"]))
        if "gmv" in seller_card.columns
        else {}
    )
    seller_actions = _seller_actions(
        seller_card,
        system_late_rate=float(seller_port["summary"]["late_rate"]),
        top=top_sellers,
        seller_gmv=seller_gmv,
    )
    low_sample_actions, low_sample_check = _low_sample_actions(
        o,
        low_sample_table,
        top=top_low_sample,
        min_orders=min_orders,
        low_sample_threshold=low_sample_threshold,
        route_gmv=route_gmv,
    )

    notes = [
        "KHÔNG cộng 'đơn tránh được' giữa route / payment / promise / seller: "
        "tổng các nhóm KHÔNG phải tổng đơn tránh được (chồng lấn trên cùng tập "
        "đơn trễ). Chỉ cộng trong cùng một loại.",
        f"Tập mỗi tổng là riêng: route = top {top_routes} tuyến theo S4 peer P25; "
        f"payment = top {top_payment} payment_type, chỉ approval và tác động "
        f"thấp; promise = top {top_routes} ô route×weight_band theo NET; seller = "
        f"top {top_sellers} seller theo excess. Các top-N khác S4 top-10 và S3 "
        "NET toàn bộ ô đủ mẫu.",
        "Số đếm theo tuyến là đơn-tuyến; số seller là đơn single-seller.",
        "Promise chỉ dùng NET (đã trừ đơn trễ mới do siết ô loose), không dùng GROSS; "
        "đổi định nghĩa trễ, không rút ngắn thời gian giao.",
        "Mọi con số avoided/NET là mô phỏng theo luật: nói 'nếu ... thì ước tính', "
        "Mô phỏng cần được diễn đạt bằng câu điều kiện; không phải counterfactual thật.",
        "Seller và review chỉ là liên hệ, không phải kết luận nhân quả.",
        "GMV là số nguyên và mô tả đúng tập nhóm; excess seller không phải số "
        "đơn tránh được theo tuyến.",
        "MA→SP, PR→BA, SP→TO nằm trong 14 tuyến gắn cờ mặc định nhưng có <200 đơn, "
        "nên được xếp vào 'cần thêm dữ liệu', không tính trùng như hành động "
        "ưu tiên chính.",
    ]

    return {
        "route_actions": route_actions,
        "payment_actions": payment_actions,
        "promise_actions": promise_actions,
        "promise_summary": promise_summary,
        "seller_actions": seller_actions,
        "low_sample_actions": low_sample_actions,
        "low_sample_check": low_sample_check,
        "notes": notes,
        "parameters": {
            "top_routes": int(top_routes),
            "top_payment": int(top_payment),
            "top_sellers": int(top_sellers),
            "top_low_sample": int(top_low_sample),
            "min_orders": int(min_orders),
            "seller_min_orders": int(seller_min_orders),
            "low_sample_threshold": int(low_sample_threshold),
            "n_boot": int(n_boot),
            "seed": int(seed),
        },
    }


def main() -> None:
    """In nhanh Decision Brief để kiểm tra thủ công."""
    o = M.load_orders()
    brief = decision_brief(o, n_boot=300, seed=42)
    for name in (
        "route_actions",
        "payment_actions",
        "promise_actions",
        "seller_actions",
        "low_sample_actions",
    ):
        print(f"\n## {name}")
        print(brief[name].to_string(index=False))
    print("\n## promise_summary")
    print(brief["promise_summary"])
    print("\n## notes")
    for note in brief["notes"]:
        print(f"- {note}")


if __name__ == "__main__":
    main()
