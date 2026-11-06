# STATE (cập nhật sau mỗi việc; cập nhật 06/11/2026)

## Quy tắc

- Tiếng Việt, ngắn. Không bịa số: số lấy từ lệnh chạy thật. Mô hình hoàn toàn theo luật và mô phỏng, chủ ý để dễ giải thích. Không sửa report/ (LaTeX) khi chưa được nói.
- Một việc mỗi lượt; xong thì dừng. Không `git add -A`. Chạy test trúng đích, full suite chỉ ở cuối.

## Số đã kiểm chứng (Checkpoint A, nguồn `reports/dss_eval_raw.txt`)

- Tỷ lệ trễ order-route 8,1556%; order-level (unique order_id) 8,1950% trên 95.082 đơn.
- 96.981 order-route trước lọc; loại 1.390 (1,4333%): prep<0=1.361, transit<0=29, NaN=0.
- 14 tuyến gắn cờ ở min_orders=100 / red 2,0 / amber 1,5 (6 đỏ, 8 vàng); GMV 13.043.202,42.
- Backtest min_orders=30: 16/19 kỳ DSS cao hơn baseline; 201807→201808 n=162, diff −9,40 pp.
- Bootstrap pair (seed 42): vs 0 [+3,77; +12,55] pp; vs prior [+0,52; +5,92]; vs through [−0,50; +2,52] (chứa 0, không nói "vượt through").
- Test 06/11/2026: **38 pytest passed**, **16 Django tests OK**.

## Đã xong (THẬT, kiểm 06/11/2026)

- Checkpoint A: H1–H15 trong `reports/dss_defect_ledger.md`; F1–F9, D1–D2 `done` trong `reports/dss_requirements.md`.
- DB reload đủ 5 bảng: Dim_Time 612, Dim_Location 15.078, Dim_Product 32.951, Dim_Seller 3.095, Fact_Delivery_SLA 110.173; 0 orphan FK.
- Fact 21 cột: thêm seller_id, price, shipping_limit_date, promise_days, total_lead_days, handoff_slack_days, distance_km; weight_band qcut 4 lúc chạy.
- Base DSS hiện có: `route_priority`, `root_cause`, `scenario`, `sensitivity`, `goal_seek_promise`, `goal_seek_cut`, Wilson/red-first/uncertain, bootstrap CI, excess_ratio.
- Chỉ tab DSS gọi API thật; Dashboard/OLAP/ETL vẫn mock (`web/Olist_Logistics_DSS_v3.html:427`, `reports/run_guide.md:93-96`).
- Đã gỡ ML.

## CHƯA có trong repo (đừng dạy/đừng nói là đã có)

`dss_attrib` (Shapley/benchmark/residual), portfolio, promise calibration, seller scorecard, Decision Brief, AUC/time-split/replay, các badge UI v2.

## Còn lại

- UI còn chữ "đơn-tuyến" (F4 → U1).
- Wilson CI giả định đơn độc lập; V2 xử lý route-level.
- `PROMPT_AI_TIEP_TUC.md` đang bị xoá ở worktree (chưa stage) — người dùng quyết định.
- 6 huy hiệu giao diện (checkpoint E).

## DSS optimize progress

Branch: `dss-v2` (tag `before-optimize` tại 32a34ca). Deadline 15/11/2026 23:59 — còn 9 ngày.

- [x] F1 [x] F2 [x] F3 [x] F4 [x] F5 [x] F6 [x] F7 [x] F8 [x] F9
- [x] D1 [x] D2
- [ ] S1 [ ] S2 [ ] S3 [ ] S4 [ ] S5 [ ] S6 [ ] S7 [ ] S8
- [ ] V1 [ ] V2 [ ] V3 [ ] V4
- [ ] A1 [ ] U1 [ ] U2
- [ ] X1 [ ] X2

NEXT: Checkpoint B (S1, S2) — chờ duyệt G1.

Schema facts đã xác minh (06/11/2026):
- `data/processed/`: 5 CSV gồm dim_time, dim_location, dim_product, dim_seller, fact_delivery_sla.
- `cleaned_fact_orders.csv`: grain item; có seller_id, price, shipping_limit_date, promise_days, total_lead_days, handoff_slack_days, distance_km.
- `load_orders()` gộp về (order_id, route), route = seller_state->cust_state; loại stage âm/NaN.
