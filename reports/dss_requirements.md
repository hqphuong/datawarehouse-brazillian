# DSS Requirements — nguồn sự thật duy nhất

Cập nhật: 07/11/2026 (sau G2 — S1 redesign). Trạng thái: `todo` | `doing` | `done` | `changed` | `dropped`.
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
| S1 | P0 | changed | Đã đổi theo G2 phương án (2): `fit_benchmarks` dùng peer group riêng từng giai đoạn — approval theo `payment_type`, prep theo `weight_band`, transit theo `distance_band` (decile khoảng cách toàn cục, **xuyên tuyến**); fallback median toàn cục khi nhóm < `min_orders` hoặc khóa `"NA"`. `attribute` giữ `benchmark_level_<stage>`; sensitivity q=0,25/0,5. Evidence: `reports/dss_eval_raw.txt` mục "Attribution" (95.591 đơn, L1–L3 pass); commit `5606c08` (`dss-opt: S1 cross-route peer benchmarks + q sensitivity`). |
| S2 | P0 | done | `attribution_summary` (thêm `cause_share_*`, `share_promise`), `bad_review_uplift`, `check_attrib` L1–L3; 12 test attribution; raw eval mục "Attribution" (95.591 đơn, invariant pass). |
| S3 | P0 | done | `promise_calibration` (route×weight_band, min 100 đơn-tuyến, `needed_days=ceil(Q95 total_lead_days)`, nhãn tight/loose/ok ±1 ngày, `avoidable_orders`). Kết quả: 130/1.157 ô đủ mẫu (83.104/95.591 đơn-tuyến); 89 tight/11 ok/30 loose; 3.751/6.720 đơn trễ có thể tránh nếu đặt promise = Q95 (chỉ đổi định nghĩa trễ, không rút ngắn giao). SP->SP: 4/4 ô tight; `share_promise` q=0,5 = 36,02% vs q=0,25 = 3,11% (tỷ trọng trong đơn trễ). Evidence: `reports/dss_eval_raw.txt` mục "Promise calibration"; 53 pytest / 16 Django. |
| S4 | P0 | done | `feasible_max_cut` + `feasible_cut_table` + `marginal_cut_table`: peer P25 **cùng định nghĩa S1** (approval payment_type, prep weight_band, transit distance_band xuyên tuyến); `cut_s=max(0, mean actual − mean peer P25)`; `scenario` chặn theo thời gian thực tế; bootstrap 300× seed 42, CI 95% cho mức giảm tỷ lệ trễ, CI chứa 0 → "chưa đủ bằng chứng". 71/406 tuyến đủ 100 đơn-tuyến. Top theo số đơn tránh: SP→SP 1.023 (CI +3,19…+3,61 pp), SP→RJ 659 (+7,52…+8,83 pp), SP→MG 261, SP→BA 231, SP→SC 178. H10: cắt 1 ngày tại SP→RJ → approval 15,36% / prep 14,50% / transit 14,32% (baseline 15,71%). Evidence: `reports/dss_eval_raw.txt` mục "Feasible max cut"; 58 pytest / 16 Django. |
| S5 | P1 | done | `seller_scorecard` + `seller_portfolio` **chỉ đơn single-seller** (đơn vị đơn hàng unique `order_id`; `is_late`=max, `gmv`=tổng). Loại 502 đơn nhiều seller + 0 thiếu `seller_id` = 0,5280% đơn / 1,0576% đơn-tuyến; dùng 94.580/95.082 đơn, 2.948 seller. Đủ mẫu (≥30): 609 seller. Phân khúc: ưu tiên 252 seller / 33.863 đơn / 4.117 trễ (52,86% đơn trễ); ổn định 357 / 44.733 / 2.332 (29,94%); cần thêm dữ liệu 2.339 / 15.984 / 1.339 (17,19%). Top 10 seller = 15,36% số đơn trễ / 9,79% GMV. Wilson CI + level red/amber/ok; `bad_review_rate` chỉ là liên hệ. Evidence: `reports/dss_eval_raw.txt` mục \"Seller scorecard\"; 62 pytest / 16 Django. |
| S6 | P0 | todo | /brief: actions route/payment/promise (+seller), owner, CI, Vietnamese text |
| S7 | P1 | done | `low_sample_targets`: tách tuyến có orders < 200 thành nhóm "cần thêm dữ liệu" (level tạm theo cùng bội số, Wilson CI, `needed_orders`), **không đổi** `route_priority`. 357/406 tuyến mẫu nhỏ; 89 có tín hiệu (red/amber tạm) với 382/670 đơn trễ của nhóm. Top: MA→SP 118 đơn/31 trễ (đỏ tạm, thiếu 82), SP→TO 195/25 (vàng, thiếu 5), PR→BA 144/24 (đỏ, thiếu 56). Evidence: `reports/dss_eval_raw.txt` mục "Tuyến mẫu nhỏ"; 64 pytest / 16 Django. |
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
| X3 | P1 | todo | Deviation đã duyệt (G2): đồng bộ số cũ (README, run_guide, TOM_TAT, dss_results.md, defense files) MỘT LẦN sau Checkpoint D, dùng số cuối từ `dss_eval_raw.txt` (test hiện tại 50/16). Ưu tiên nếu hết giờ: README, run_guide, TOM_TAT, QA_BANK. Không done khi chưa evidence. |
