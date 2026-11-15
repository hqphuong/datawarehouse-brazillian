# FINAL G4

## Trạng thái

| Bước | Trạng thái | Evidence |
|---|---|---|
| A1 | done | `backend/dss/views.py`, `backend/dss/urls.py`; `reports/CHECK_OUTPUT.txt` (Django 22/22) |
| U1 | done | `web/Olist_Logistics_DSS_v3.html`; ảnh người dùng 08/11 và wording fixes |
| V1 | dropped | Ngoài phạm vi theo quyết định; không triển khai AUC rank-based |
| V2 | done | `reports/dss_eval_raw.txt`, “Bootstrap route-level (V2)”: transit đứng đầu cấp hệ thống 500/500 |
| V3 | dropped | Ngoài phạm vi theo quyết định; không triển khai time-split replay |
| V4 | done | `reports/dss_eval_raw.txt`, “Sign test (V4)”; giả định độc lập tháng được ghi rõ |
| U2 | dropped | Theo phạm vi, Dashboard/OLAP/ETL không nối API và vẫn là mock |
| X1 | done | `reports/dss_formulas.md`, `reports/dss_results.md` |
| X2 | done | `reports/defense/CHEAT_SHEET.md`, `QA_BANK.md` (71 câu), `DEMO_SCRIPT.md` |
| X3 | done | `README.md`, `reports/run_guide.md`, `TOM_TAT_DU_AN.md`, defense files |

## Số liệu và kiểm chứng

- Check gần nhất: pytest 78/78, Django 22/22; `regen_eval` skipped do `-Quick`. Xem `reports/CHECK_OUTPUT.txt`.
- V2: 165/226 là tỷ lệ tuyến có transit đứng đầu trong tập tuyến có `late>0`; khác với transit rank #1 cấp hệ thống ở 500/500 bootstrap reps. q=0,5 transit share 69,9162%, CI 95% [56,4003%; 83,5136%]. CI là nhiễu lấy mẫu giữa tuyến, không đo độ nhạy benchmark. Promise share khoảng 1–13% giữa q=0,25/0,5.
- V4: `min_orders=30` có 19 kỳ; `min_orders=100` có 13 kỳ đủ điều kiện. So through có 12 dấu dương/4 âm trên 16 kỳ không hòa; đây là tương quan hồi cứu.
- Decision Brief tách thứ hạng theo tỷ lệ khỏi tác động theo số đơn; các nhóm top-N có thể chồng lấn, không cộng thành đơn tránh được.

## Deviation / giới hạn còn mở

- Metadata cấu trúc (Fact 21 cột, 5 bảng/CSV) được đối chiếu từ DDL/ETL, không phải raw eval.
- `regen_eval` chưa được chạy trong check gần nhất vì `-Quick`; user cần chạy `.\scripts\check.ps1 -Quick` để kiểm tra các chỉnh sửa hiện tại.
- Wilson CI giả định đơn độc lập; đơn cùng tuyến/cụm có thể phụ thuộc.
- S4 CI mô tả sampling noise, không chứng minh mức cắt khả thi; scenario dựa giả định 1:1, không phải phản thực nghiệm.
- V1, V3, U2 được drop/deferred theo phạm vi, không được trình bày là đã triển khai.

## Điểm yếu cần nói thẳng

1. Backtest và bad-review uplift là tương quan; tháng liền kề có thể tương quan nên p-value sign test có thể lạc quan.
2. Promise chỉ đổi định nghĩa trễ, không rút ngắn thời gian giao; chưa có ROI/cost model.
3. Root Cause card so với trung bình hệ thống, chưa chuẩn hoá theo khoảng cách; peer attribution có ở API nhưng UI chưa dùng.
4. Route action owner là danh sách ghép của ba đơn vị; nút ghi nhận chỉ tạo ActionLog, không thực thi.
5. Dashboard/OLAP/ETL Monitor là mock; chỉ tab DSS gọi API thật.
