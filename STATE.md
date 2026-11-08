# STATE (cập nhật sau mỗi việc; cập nhật 08/11/2026)

## Quy tắc

- Tiếng Việt, ngắn. Không bịa số: số lấy từ lệnh chạy thật. Mô hình hoàn toàn theo luật và mô phỏng, chủ ý để dễ giải thích. Không sửa report/ (LaTeX) khi chưa được nói.
- Một việc mỗi lượt; xong thì dừng. Không `git add -A`. Chạy test trúng đích, full suite chỉ ở cuối.

## Số đã kiểm chứng (Checkpoint A–B, nguồn `reports/dss_eval_raw.txt`)

- Tỷ lệ trễ order-route 8,1556%; order-level (unique order_id) 8,1950% trên 95.082 đơn.
- 96.981 order-route trước lọc; loại 1.390 (1,4333%): prep<0=1.361, transit<0=29, NaN=0.
- 14 tuyến gắn cờ ở min_orders=100 / red 2,0 / amber 1,5 (6 đỏ, 8 vàng); GMV 13.043.202,42.
- Backtest min_orders=30: 16/19 kỳ DSS cao hơn baseline; 201807→201808 n=162, diff −9,40 pp.
- Bootstrap pair (seed 42): vs 0 [+3,77; +12,55] pp; vs prior [+0,52; +5,92]; vs through [−0,50; +2,52] (chứa 0, không nói "vượt through").
- Đơn trễ có review xấu (≤2) 54,16% vs 9,44% đúng hạn (+44,72 pp; liên hệ, không nhân quả).
- Attribution cross-route peer (q=0,5): toàn hệ thống approval 1,58% / prep 15,15% / transit 69,88% / promise 13,39%; q=0,25: 2,53 / 20,08 / 76,33 / 1,06. Đây là **tỷ trọng trong đơn trễ**, không phải tỷ lệ trễ.
- Fallback global: transit 0,4959% (chỉ đơn thiếu `distance_km`); approval 0,001% (1 đơn thiếu `payment_type`); prep 0%.
- `phi_transit` q=0,5: SP→RJ 14,11 pp (trước 13,50), SP→SP 2,46 pp (trước 2,90); hạng nguyên nhân không đổi (transit đứng đầu).
- S3 promise calibration: 130/1.157 ô route×weight_band đủ mẫu (83.104/95.591 đơn-tuyến); 89 tight / 11 ok / 30 loose. **GROSS** 3.751/6.720 đơn trễ tránh được; siết ô loose phát sinh **884** đơn trễ mới; **NET 2.867** (6.720 → 3.853), brief chỉ dùng NET. Bảng mức phục vụ 85/90/95% cho top 5 tuyến (`needed_days`, `late_rate`); ví dụ SP→SP 13/15/19 ngày, SP→RJ 26/32/41. SP→SP: 4/4 ô tight; `share_promise` 36,02% (q=0,5) vs 3,11% (q=0,25).
- S4 feasible max cut (peer P25 cùng định nghĩa S1, bootstrap 300× seed 42): 71/406 tuyến đủ 100 đơn-tuyến. Top theo số đơn tránh: SP→SP 1.023 đơn (CI +3,19…+3,61 pp), SP→RJ 659 (+7,52…+8,83 pp), SP→MG 261, SP→BA 231, SP→SC 178; trạng thái **"ước lượng ổn định (CI hẹp)"** (đổi tên từ "có cơ sở"). Thêm mục tiêu `peer_p50_*` (tham chiếu, không dùng để cắt). H10: cắt 1 ngày tại SP→RJ → approval 15,36% / prep 14,50% / transit 14,32% (baseline 15,71%).
- S5 seller scorecard/portfolio (chỉ đơn single-seller): loại 502 đơn nhiều seller (0,5280% đơn / 1,0576% đơn-tuyến); 94.580/95.082 đơn, 2.948 seller, 609 seller đủ mẫu ≥30. Ưu tiên 252 seller / 4.117 đơn trễ (52,86% đơn trễ); ổn định 357 / 2.332 (29,94%); cần thêm dữ liệu 2.339 / 1.339 (17,19%). Top 10 seller = 15,36% đơn trễ, 9,79% GMV. **102 seller ít nhất phủ 50% đơn trễ** (3.902/7.788 = 50,10%).
- S7 low-sample split: 357/406 tuyến có <200 đơn; 89 tuyến có tín hiệu tạm (red/amber) với 382/670 đơn trễ của nhóm. Top: MA→SP 118/31 (thiếu 82 đơn), SP→TO 195/25 (thiếu 5), PR→BA 144/24 (thiếu 56). `route_flag_check`: cả 3 đều nằm trong 14 tuyến gắn cờ mặc định (hạng 5/14/6) nhưng xếp "cần thêm dữ liệu" vì <200 đơn. `route_priority` không đổi.
- S8 threshold sensitivity: lưới 4 mức min_orders × 6 cặp ngưỡng (mặc định + một-nhân-tố-mỗi-lần + kết hợp). Tại min_orders=50: 7–30 tuyến gắn cờ; toàn lưới 4–30; mặc định 100/2,0/1,5 = 14 (6 đỏ, 8 vàng). Tại 100: 5 cặp quanh mặc định dao động **10–21 tuyến**; cặp (2,5; 2,0) chỉ còn **lõi 6 tuyến**.
- S6 Decision Brief: `decision_brief` + `decision_brief_report` tách 4 nhóm route/payment/promise/seller + nhóm "cần thêm dữ liệu"; **không cộng avoided xuyên loại**; promise chỉ dùng NET; câu "nếu ... thì ước tính".
- Test 08/11/2026: **73 pytest passed** (targeted S3/S4/S5/S6/S7/S8: **63 passed**), **16 Django tests OK**; S1 `5606c08`, S3 `0f84768`, S4 `33d98e8`, S5 `9e6c72f`, S7 `5b34579`, S8 `ace7473`.

## Đã xong (THẬT, kiểm 08/11/2026)

- Checkpoint A: H1–H15 trong `reports/dss_defect_ledger.md`; F1–F9, D1–D2 `done` trong `reports/dss_requirements.md`.
- Checkpoint B: `etl/dss_attrib.py` + `tests/test_dss_attrib.py` (benchmark peer group từng giai đoạn, Shapley, summary, bad review, L1–L3); 12 test attribution.
- DB reload đủ 5 bảng: Dim_Time 612, Dim_Location 15.078, Dim_Product 32.951, Dim_Seller 3.095, Fact_Delivery_SLA 110.173; 0 orphan FK.
- Fact 21 cột: thêm seller_id, price, shipping_limit_date, promise_days, total_lead_days, handoff_slack_days, distance_km; weight_band qcut 4 lúc chạy.
- Base DSS hiện có: `route_priority`, `root_cause`, `scenario`, `sensitivity`, `goal_seek_promise`, `goal_seek_cut`, Wilson/red-first/uncertain, bootstrap CI, excess_ratio.
- Checkpoint C + S6: S3 promise calibration (GROSS/NET, mức phục vụ 85/90/95%), S4 feasible cut (peer P50 tham chiếu), S5 seller scorecard/portfolio + k-cover, S7 low-sample split + `route_flag_check`, S8 threshold grid, S6 Decision Brief; tất cả có test và số trong `reports/dss_eval_raw.txt`.
- Chỉ tab DSS gọi API thật; Dashboard/OLAP/ETL vẫn mock (`web/Olist_Logistics_DSS_v3.html:427`, `reports/run_guide.md:93-96`).
- Đã gỡ ML.

## CHƯA có trong repo (đừng dạy/đừng nói là đã có)

AUC/time-split/replay, các badge UI v2.

## Deviation đã duyệt (G1/G2)

- G1: bỏ U2; U1 chỉ 3 thẻ chính; X2 chỉ sửa số headline; V1/V3 hoãn nếu hết giờ. Giữ P0 S3, S4, S6, A1, X1; không cắt S1, S3, S4, S6.
- G2: thêm X3 (P1): đồng bộ docs còn số cũ MỘT LẦN sau Checkpoint D, dùng số cuối; không sửa rải rác. Không đánh done khi chưa evidence.
- G2b: đã duyệt phương án (2) và triển khai: transit benchmark xuyên tuyến theo decile khoảng cách; approval theo `payment_type`; prep theo `weight_band`; bỏ within-route dispersion (ghi hạn chế).

## Còn lại

- UI còn chữ "đơn-tuyến" (F4 → U1).
- Wilson CI giả định đơn độc lập; V2 xử lý route-level.
- `PROMPT_AI_TIEP_TUC.md` đang bị xoá ở worktree (chưa stage) — người dùng quyết định.
- 6 huy hiệu giao diện (checkpoint E).

## DSS optimize progress

Branch: `dss-v2` (tag `before-optimize` tại 32a34ca). Deadline 15/11/2026 23:59 — còn 8 ngày.

- [x] F1 [x] F2 [x] F3 [x] F4 [x] F5 [x] F6 [x] F7 [x] F8 [x] F9
- [x] D1 [x] D2
- [x] S1 [x] S2 [x] S3 [x] S4 [x] S5 [x] S6 [x] S7 [x] S8 [x]
- [ ] V1 [ ] V2 [ ] V3 [ ] V4
- [ ] A1 [ ] U1 [ ] U2
- [ ] X1 [ ] X2 [ ] X3

NEXT: A1 — API `/brief` + các endpoint P0 (dùng `dss_brief.decision_brief`), rồi V2/V4 nếu còn thời gian. Không mở X3 trước Checkpoint D.

Schema facts đã xác minh (06/11/2026):
- `data/processed/`: 5 CSV gồm dim_time, dim_location, dim_product, dim_seller, fact_delivery_sla.
- `cleaned_fact_orders.csv`: grain item; có seller_id, price, shipping_limit_date, promise_days, total_lead_days, handoff_slack_days, distance_km.
- `load_orders()` gộp về (order_id, route), route = seller_state->cust_state; loại stage âm/NaN.
