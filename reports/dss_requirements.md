# DSS Requirements — nguồn sự thật duy nhất

Cập nhật: 06/11/2026 (sau Checkpoint A). Trạng thái: `todo` | `doing` | `done` | `changed` | `dropped`.
Mọi thay đổi trạng thái phải kèm evidence (lệnh chạy/file). Không đổi âm thầm.

## DATA

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| F1 | P0 | done | `dim_location.py` zfill(5)+assert; fact FK zfill+assert. 3.908 mã 4 ký tự → 0; coverage 100% trước/sau; DDL `VARCHAR(5)`. |
| F2 | P0 | done | `etl/transform_rules.py` + test: payment tổng value max (tie seq min), review creation→answer→id. Share: payment >1 type 2,2586%; review >1 0,5544%. |
| F3 | P0 | done | `etl/load_data.py`: 1 transaction, commit 1 lần, rollback+raise. `tests/test_load_data.py` failure path; reload DB thật OK. |
| F4 | P0 | done | `load_orders`: grain order-route, `gmv=sum(price)`, `late_rate_order` unique order_id (8,1950% vs 8,1556%). Wording UI "đơn-tuyến" thuộc U1. |
| F5 | P0 | done | Loại 1.390 order-route (1,4333%; prep<0=1361, transit<0=29, NaN=0) khỏi DSS; raw eval in share; test `stage_invalid_excluded`. |
| F6 | P0 | done | fact `total_lead_days`, `promise_days`; gap max abs = 0; late0 != (delay>0) = 0 dòng; test `delay_days_valid`. |
| F7 | P1 | done | `raw_data_summary()`: 2.963 không giao, 23 delivered dropna, status counts; nhãn "trên đơn đã giao". |
| F8 | P1 | done | README 5 bảng/5 CSV/mockup/tree/count; `main.py` docstring; `dss_results.md` counts 38/16. |
| F9 | P0 | done | `reports/dss_defect_ledger.md` H1–H15 đủ verdict/evidence/action/residual. |

## DATA WAREHOUSE

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| D1 | P0 | done | `Dim_Seller` 3.095 dòng; FK location 100%; DDL/prisma/Django model/loader. |
| D2 | P0 | done | Fact 21 cột gồm seller_id, price, shipping_limit_date, promise_days, total_lead_days, handoff_slack_days, distance_km; weight_band qcut4 runtime. DB reload 110.173 dòng, 0 orphan FK. |

## DSS

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| S1 | P0 | todo | fit_benchmarks/attribute: Shapley 3 stage, phi_*, residual_promise, invariants |
| S2 | P0 | todo | attribution_summary + bad_review_uplift + check_attrib L1–L3 |
| S3 | P0 | todo | promise calibration route×weight_band, min 100; tight/loose/ok; avoidable items |
| S4 | P0 | todo | feasible_max_cut, status, bootstrap 300× CI, marginal_cut_table |
| S5 | P1 | todo | seller_scorecard + portfolio; chỉ đơn single-seller, báo share loại |
| S6 | P0 | todo | /brief: actions route/payment/promise (+seller), owner, CI, Vietnamese text |
| S7 | P1 | todo | low_sample targets tách riêng "cần thêm dữ liệu"; route_priority không đổi (H7) |
| S8 | P1 | todo | bảng nhạy ngưỡng min_orders × (red,amber) (H8) |

## VALIDATION

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| V1 | P1 | todo | AUC rank-based từng stage excess, flagged vs unflagged |
| V2 | P1 | todo | bootstrap 500× route-level: CI cause shares + top-stage rank |
| V3 | P1 | todo | time-split replay cutoff 2018-01-01 |
| V4 | P1 | todo | backtest per-period + binomial sign test 16/19 (H13) |

## API / UI

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| A1 | P0 | todo | /attribution, /promise-policy, /brief (P0); /sellers, /portfolio (P1); giữ 4 endpoint cũ |
| U1 | P1 | todo | DSS tab: Decision Brief, Seller Scorecard, Promise Policy |
| U2 | P2 | todo | nối BI tab vào API thật — chỉ khi gate G4 duyệt |

## DOCS

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| X1 | P0 | todo | append mục tiếng Việt vào dss_formulas.md + dss_results.md (số từ raw eval) |
| X2 | P1 | todo | refresh CHEAT_SHEET.md, QA_BANK.md (≥57 Q), DEMO_SCRIPT.md |
