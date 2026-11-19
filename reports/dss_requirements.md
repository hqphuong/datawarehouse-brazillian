# DSS Requirements — nguồn sự thật duy nhất

Cập nhật: 08/11/2026 (sau Checkpoint C + S6 Decision Brief). Trạng thái: `todo` | `doing` | `done` | `changed` | `dropped`.
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
| F8 | P1 | done | README 5 bảng/5 CSV/mockup/tree/count; `main.py` docstring; test counts đồng bộ theo `reports/CHECK_OUTPUT.txt` (78 pytest/22 Django; `regen_eval` skipped do `-Quick`). |
| F9 | P0 | done | `reports/dss_defect_ledger.md` H1–H15 đủ verdict/evidence/action/residual. |

## DATA WAREHOUSE

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| D1 | P0 | done | `Dim_Seller` 3.095 dòng; FK location 100%; DDL/prisma/Django model/loader. |
| D2 | P0 | done | Fact 20 cột gồm seller_id, price, shipping_limit_date, promise_days, total_lead_days, distance_km; weight_band qcut4 runtime. DB reload 110.173 dòng, 0 orphan FK. |

## DSS

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| S1 | P0 | changed | Đã đổi theo G2 phương án (2): `fit_benchmarks` dùng peer group riêng từng giai đoạn — approval theo `payment_type`, prep theo `weight_band`, transit theo `distance_band` (decile khoảng cách toàn cục, **xuyên tuyến**); fallback median toàn cục khi nhóm < `min_orders` hoặc khóa `"NA"`. `attribute` giữ `benchmark_level_<stage>`; sensitivity q=0,25/0,5. Evidence: `reports/dss_eval_raw.txt` mục "Attribution" (95.591 đơn, L1–L3 pass); commit `5606c08` (`dss-opt: S1 cross-route peer benchmarks + q sensitivity`). |
| S2 | P0 | done | `attribution_summary` (thêm `cause_share_*`, `share_promise`), `bad_review_uplift`, `check_attrib` L1–L3; 12 test attribution; raw eval mục "Attribution" (95.591 đơn, invariant pass). |
| S3 | P0 | done | `promise_calibration` (route×weight_band, min 100 đơn-tuyến, `needed_days=ceil(Q95 total_lead_days)`, nhãn tight/loose/ok ±1 ngày, `avoidable_orders`). Kết quả: 130/1.157 ô đủ mẫu (83.104/95.591 đơn-tuyến); 89 tight/11 ok/30 loose. **GROSS** 3.751/6.720 đơn trễ tránh được; siết ô loose phát sinh **884** đơn trễ mới; **NET 2.867** (6.720 → 3.853), Decision Brief chỉ dùng NET. `promise_service_levels` in bảng 85/90/95% cho top 5 tuyến (`needed_days`, `late_rate`, avoidable/new/net); ví dụ SP→SP 13/15/19 ngày, SP→RJ 26/32/41. SP→SP: 4/4 ô tight; `share_promise` q=0,5 = 36,02% vs q=0,25 = 3,11% (tỷ trọng trong đơn trễ). Evidence: `reports/dss_eval_raw.txt` mục "Promise calibration"; 63 targeted pytest. |
| S4 | P0 | done | `feasible_max_cut` + `feasible_cut_table` + `marginal_cut_table`: peer P25 **cùng định nghĩa S1** (approval payment_type, prep weight_band, transit distance_band xuyên tuyến); `cut_s=max(0, mean actual − mean peer P25)`; `scenario` chặn theo thời gian thực tế; bootstrap 300× seed 42, CI 95% cho mức giảm tỷ lệ trễ. Trạng thái: CI dưới > 0 → **"ước lượng ổn định (CI hẹp)"** (đổi tên từ "có cơ sở"), CI trên < 0 → "tác động âm", CI chứa 0 → "chưa đủ bằng chứng". Thêm `peer_p50_*` / `peer_p50_total_days` (fit riêng q=0,5) làm mục tiêu tham chiếu, **không dùng để cắt**. 71/406 tuyến đủ 100 đơn-tuyến. Top theo số đơn tránh: SP→SP 1.023 (CI +3,19…+3,61 pp), SP→RJ 659 (+7,52…+8,83 pp), SP→MG 261, SP→BA 231, SP→SC 178. H10: cắt 1 ngày tại SP→RJ → approval 15,36% / prep 14,50% / transit 14,32% (baseline 15,71%). Evidence: `reports/dss_eval_raw.txt` mục "Feasible max cut"; 63 targeted pytest. |
| S5 | P1 | done | `seller_scorecard` + `seller_portfolio` **chỉ đơn single-seller** (đơn vị đơn hàng unique `order_id`; `is_late`=max, `gmv`=tổng). Loại 502 đơn nhiều seller + 0 thiếu `seller_id` = 0,5280% đơn / 1,0576% đơn-tuyến; dùng 94.580/95.082 đơn, 2.948 seller. Đủ mẫu (≥30): 609 seller. Phân khúc: ưu tiên 252 seller / 33.863 đơn / 4.117 trễ (52,86% đơn trễ); ổn định 357 / 44.733 / 2.332 (29,94%); cần thêm dữ liệu 2.339 / 15.984 / 1.339 (17,19%). Top 10 seller = 15,36% số đơn trễ / 9,79% GMV. `sellers_covering_late_share`: **102 seller ít nhất phủ 50% đơn trễ** (3.902/7.788 = 50,10%). Wilson CI giả định đơn độc lập, không hiệu chỉnh clustering; `bad_review_rate` chỉ là liên hệ. Evidence: `reports/dss_eval_raw.txt` mục "Seller scorecard"; 63 targeted pytest. |
| S6 | P0 | done | `etl/dss_brief.py::decision_brief` + `dss_eval.decision_brief_report`: 4 nhóm hành động tách biệt route/payment/promise/seller + nhóm "cần thêm dữ liệu" S7; có owner, CI, câu tiếng Việt "nếu ... thì ước tính"; promise chỉ dùng **NET**. Không có tổng `avoided_orders` xuyên loại vì các nhóm chồng lấn trên cùng đơn-tuyến; chỉ cộng trong từng loại. Evidence: `reports/dss_eval_raw.txt` mục "Decision Brief"; `tests/test_dss_brief.py` (6 test). |
| S7 | P1 | done | `low_sample_targets`: tách tuyến có orders < 200 thành nhóm "cần thêm dữ liệu" (level tạm theo cùng bội số, Wilson CI giả định đơn độc lập, `needed_orders`), **không đổi** `route_priority`. 357/406 tuyến mẫu nhỏ; 89 có tín hiệu (red/amber tạm) với 382/670 đơn trễ của nhóm. Top: MA→SP 118 đơn/31 trễ (đỏ tạm, thiếu 82), SP→TO 195/25 (vàng, thiếu 5), PR→BA 144/24 (đỏ, thiếu 56). `route_flag_check`: cả 3 đều `in_flagged=True` trong 14 tuyến mặc định (hạng 5/14/6) nhưng `status="cần thêm dữ liệu"` vì <200 đơn. Evidence: `reports/dss_eval_raw.txt` mục "Tuyến mẫu nhỏ"; 63 targeted pytest. |
| S8 | P1 | done | `threshold_sensitivity` mở rộng lưới min_orders {50, 100, 150, 200} × 6 cặp ngưỡng (mặc định 2,0/1,5; chỉ siết red 2,5/1,5; chỉ nới amber 2,0/1,25; nới cả hai 1,5/1,25; chỉ siết amber 2,0/1,75; siết cả hai 2,5/2,0), thêm cột `is_default`. Tại min_orders=50: 7–30 tuyến gắn cờ; toàn lưới 4–30. Mặc định 100/2,0/1,5 = 14 tuyến (6 đỏ, 8 vàng). Tại min_orders=100: 5 cặp quanh mặc định dao động **10–21 tuyến**; cặp siết cả hai (2,5; 2,0) chỉ còn **lõi 6 tuyến**. Evidence: `reports/dss_eval_raw.txt` mục "Độ nhạy ngưỡng"; 63 targeted pytest. |

## VALIDATION

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| V1 | P1 | dropped | Được chủ động loại khỏi phạm vi; không triển khai AUC rank-based theo stage excess. |
| V2 | P1 | done | `reports/dss_eval_raw.txt`, mục “Bootstrap route-level (V2)”: 500 reps, seed 42; transit đứng đầu cấp hệ thống 500/500 lần. `165/226` là thống kê theo tuyến trên tập tuyến có `late>0`; bootstrap CI là nhiễu lấy mẫu giữa tuyến tại q=0,5, không phải độ nhạy benchmark. Shares không có cột kiểm định “CI không chứa 0” vì không âm theo định nghĩa. |
| V3 | P1 | dropped | Được chủ động loại khỏi phạm vi; không triển khai time-split replay cutoff 2018-01-01. |
| V4 | P1 | done | `etl/dss_eval.py::sign_test_v4_report`, mục “Sign test (V4)” trong `reports/dss_eval_raw.txt`; min_orders=30 có 19 kỳ, 100 có 13; exact sign test đã qua check Phase 1. Ghi rõ giả định tháng độc lập và nguy cơ p-value lạc quan do tháng liền kề tương quan. |

## API / UI

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| A1 | P0 | done | `backend/dss/views.py` + `backend/dss/urls.py`: `/brief`, `/attribution`, `/promise-policy`, `/sellers`, `/portfolio`, giữ `/routes`, `/scenario`, `/promise`, `/actions`; Phase 1 `CHECK_OUTPUT.txt`: Django 22/22 pass. |
| U1 | P1 | done | `frontend/src/views/DssViewImpl.jsx`: tab DSS gọi API thật `/api/dss/routes`, `/attribution` (q=0,5 và q=0,25), `/scenario`, `/brief` và `POST /actions` qua `src/data/api.js` + `src/data/dssAdapter.js`; đã bỏ mock trong tab này. Root Cause lấy Shapley/peer từ `/attribution`; Decision Brief đủ 5 nhóm, route priority phân biệt tỷ lệ với tác động theo số đơn, bộ lọc năm áp dụng. CI what-if lấy từ `/brief.route_actions`, kịch bản tuỳ ý không có CI. Dashboard/OLAP/Analytics cũng gọi API thật; ETL Monitor còn mock. |
| U2 | P2 | dropped | Không nối BI/Dashboard vào API; theo phạm vi đã chốt, chỉ DSS dùng API thật và Dashboard/OLAP/ETL vẫn mock. |

## DOCS

| ID | Ưu tiên | Trạng thái | Evidence |
|---|---|---|---|
| X1 | P0 | done | `reports/dss_formulas.md`, `reports/dss_results.md`: attribution/Shapley, q sensitivity, promise, feasible cut, sellers, low-sample, V2/V4 và hạn chế; V2 CI được giới hạn đúng là nhiễu tuyến tại q=0,5, transit rank #1 cấp hệ thống 500/500; V4 ghi giả định độc lập tháng. |
| X2 | P1 | done | `reports/defense/CHEAT_SHEET.md`, `QA_BANK.md` (71 Q&A), `DEMO_SCRIPT.md`: headline/câu trả lời về Shapley, q=0,75, GROSS/NET, CI-feasibility, seller confounding, sign test; đã bổ sung caveat V2/V4 và không bịa x/500. |
| X3 | P1 | done | Đã đồng bộ một lần sau Checkpoint D: `README.md`, `reports/run_guide.md`, `TOM_TAT_DU_AN.md`, `reports/dss_results.md`, và các defense files; test snapshot là 78 pytest/22 Django; check dùng `-Quick`, nên regen eval skipped. |
