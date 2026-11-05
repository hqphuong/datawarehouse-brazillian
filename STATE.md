\# STATE (cập nhật sau mỗi việc; cập nhật 05/11/2026)



\## Quy tắc

\- Tiếng Việt, ngắn. Không bịa số: số lấy từ lệnh chạy thật. Không đổi ML. Không sửa report/ (LaTeX) khi chưa được nói.

\- Một việc mỗi lượt; xong thì dừng. Không git add -A. Chạy test trúng đích, full suite chỉ ở cuối.



\## Số đã kiểm chứng

\- Tỷ lệ trễ chung 8,0727%; ngưỡng đỏ 16,1454%, vàng 12,1091% (không dùng 5,98%, là của tập test ML).

\- 14 tuyến gắn cờ (6 đỏ, 8 vàng); API mặc định trả 10; `uncertain` 7/14; `low\_sample` 3/14.

\- transit excess của 14 tuyến: 1,43 (MA->SP) đến 12,54 (SP->AL) ngày. excess\_ratio: 0/14 tuyến đổi stage (chờ bảng chi tiết).

\- goal\_seek\_cut: SP->BA=10, SP->ES=9, SP->RJ=None. Bootstrap (pair, trọng số total\_orders): vs 0 \[+3,68;+12,40], vs prior \[+0,45;+5,79], vs through \[−0,58;+2,35] (chứa 0, không dùng chữ "vượt").

\- Test: 34 pytest, 23 Django.



\## Đã xong

Việc 1 (test uncertain), việc 2 (bảng 14 tuyến), base\_cut, bootstrap, Wilson/red-first/uncertain trong code.



\## Còn lại

5 api\_dss.md → 3 dss\_formulas.md → 4 dss\_results.md → 6 huy hiệu giao diện (chờ tôi) → 7 nhãn mẫu/risk score → 8 test cuối + hỏi dss\_ml\_results.md.

