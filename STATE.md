\# STATE (cập nhật sau mỗi việc; cập nhật 06/11/2026)



\## Quy tắc

\- Tiếng Việt, ngắn. Không bịa số: số lấy từ lệnh chạy thật. Mô hình hoàn toàn theo luật và mô phỏng, chủ ý để dễ giải thích. Không sửa report/ (LaTeX) khi chưa được nói.

\- Một việc mỗi lượt; xong thì dừng. Không git add -A. Chạy test trúng đích, full suite chỉ ở cuối.



\## Số đã kiểm chứng

\- Tỷ lệ trễ chung 8,0727%; ngưỡng đỏ 16,1454%, vàng 12,1091%.

\- 14 tuyến gắn cờ (6 đỏ, 8 vàng); API mặc định trả 10; `uncertain` 7/14; `low\_sample` 3/14.

\- transit excess của 14 tuyến: 1,43 (MA->SP) đến 12,54 (SP->AL) ngày. excess\_ratio: 0/14 tuyến đổi stage (chờ bảng chi tiết).

\- goal\_seek\_cut: SP->BA=10, SP->ES=9, SP->RJ=None. Bootstrap (pair, trọng số total\_orders): vs 0 \[+3,68;+12,40], vs prior \[+0,45;+5,79], vs through \[−0,58;+2,35] (chứa 0, không dùng chữ "vượt").

\- Test (chạy lại 06/11/2026, sau khi gỡ ML): **26 pytest passed**, **16 Django tests OK** (khớp `reports/dss_results.md:8,15`). Số 34/23 là trước khi gỡ ML — không dùng nữa.



\## Đã xong

Việc 1 (test uncertain), việc 2 (bảng 14 tuyến), base\_cut, bootstrap, Wilson/red-first/uncertain trong code. Đã gỡ hoàn toàn phần dự báo; chỉ còn DSS luật.

## Tiến độ dạy học (DSS_V2_PROMPT)

- Đã dạy Lesson 0–8; quiz 0–3 đã chấm, quiz 4–8 người học bỏ qua bằng "tiếp".
- CP1 (phase 0–2), CP2 (3–4), CP3 (5–6), CP4 (7–8): nội dung đã dạy đủ; test + commit đóng CP thực hiện 06/11/2026.
- Đã xác minh lại: chỉ tab DSS gọi API thật; Dashboard/OLAP/ETL vẫn mock (`web/Olist_Logistics_DSS_v3.html:427`, `reports/run_guide.md:93-96`).
- Các phần v2 **chưa có trong repo** (đừng dạy như đã có): Shapley/`dss_attrib`, benchmark theo khoảng cách, residual/promise-tight, portfolio, seller scorecard, Decision Brief, AUC/time-split (ML đã gỡ).



\## Còn lại

- Lesson 9 + bộ `reports/defense/` (CHEAT_SHEET, QA_BANK, DEMO_SCRIPT).
- 6 huy hiệu giao diện (chờ tôi).
- `README.md:24` còn ghi "chưa có API endpoint" — cần sửa.
- `PROMPT_AI_TIEP_TUC.md` đang bị xoá ở worktree (chưa stage) — người dùng quyết định.

