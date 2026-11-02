# Prompt giao cho AI lập trình (Claude Code / Cursor / Copilot)

> Cách dùng: mở repo của nhóm bằng công cụ AI, đính kèm file `DSS_HUONG_DAN.md` và `Olist_Logistics_DSS_v3.html`, rồi dán toàn bộ phần trong khung dưới đây. Nên yêu cầu AI làm từng giai đoạn và dừng lại báo cáo sau mỗi giai đoạn.

---

```text
Bạn là kỹ sư dữ liệu/backend hỗ trợ nhóm sinh viên hoàn thiện phần DSS (Decision Support System) của bài tập lớn môn Kho dữ liệu và Hệ hỗ trợ Quyết định (CO4031).

## 1. Bối cảnh
- Đề tài: DSS phân tích điểm nghẽn và tối ưu quy trình hoàn tất đơn hàng, dữ liệu Olist Brazilian E-Commerce (Kaggle).
- Kho dữ liệu dạng star schema đã có (xuất ra CSV bởi các script ETL trong gói `etl/`, import `from .config import PROCESSED_DIR`; chạy bằng `python -m etl.<script>`; CSDL đích là PostgreSQL, cấu hình trong `.env` và `etl/config.py`):
  - `cleaned_fact_orders.csv` (Fact_Delivery_SLA; hạt = 1 item của 1 đơn đã giao): order_id, order_item_id, product_id, customer_location_id, seller_location_id, time_id, payment_type, approval_time_days, seller_prep_time_days, carrier_transit_time_days, freight_value, review_score, delay_days, has_logistics_complaint  (KHÔNG có cột is_late; đơn trễ khi delay_days > 0)
  - `cleaned_dim_product.csv` (product_id, category_name_english, weight_g, volume_cm3)
  - `cleaned_dim_time.csv` (time_id dạng yyyymmdd, full_date, month, year, quarter, day_of_week)
  - `cleaned_dim_location.csv` (location_id = mã zip prefix dạng số, zip_code_prefix, city, state, latitude, longitude)
- Người dùng DSS: Giám đốc Vận hành. DSS có 4 khối: (1) Route Priority, (2) Root Cause, (3) Scenario/What-if, (4) Recommendation & Action.
- Giao diện mẫu: `Olist_Logistics_DSS_v3.html` (React qua CDN, hiện dùng dữ liệu mẫu `DS_ORD`).
- Hướng dẫn chi tiết, code mẫu và tiêu chí: `DSS_HUONG_DAN.md`. Đây là đặc tả chính; làm theo đúng thứ tự các bước.

## 2. Việc cần làm (làm tuần tự, dừng lại báo cáo sau mỗi giai đoạn)

### Giai đoạn 1 – Dữ liệu (Bước 1–2 trong hướng dẫn)
1. Khảo sát repo, nêu ngắn gọn cấu trúc thực tế và các điểm lệch so với hướng dẫn trước khi sửa.
2. Fact đã có `delay_days`; KHÔNG sửa ETL. Kiểm tra: `delay_days` không rỗng, cùng giá trị cho mọi item của một đơn, khóa ngoại hợp lệ. Kết quả kỳ vọng trên dữ liệu hiện có: 110 173 dòng, 96 455 đơn, tỷ lệ trễ theo đơn khoảng 8,07%, 0 khóa ngoại lỗi, `seller_prep_time_days` âm ở 1 542 dòng, `carrier_transit_time_days` âm ở 50 dòng. Nếu số liệu khác nhiều, báo lại.
3. Quy ước: `is_late` = `delay_days > 0`, suy ra trong `load_orders`.

### Giai đoạn 2 – Model Base và kiểm thử (Bước 3–5)
1. Tạo `etl/dss_models.py` theo code mẫu: `load_orders`, `route_priority`, `root_cause`, `scenario`, `sensitivity`, `goal_seek_promise`, `goal_seek_cut`, bảng luật `RULES`. Có docstring tiếng Việt ngắn.
2. Tạo `tests/test_dss_models.py` (pytest) theo hướng dẫn; chạy và sửa đến khi qua hết.
3. Chạy mô hình trên dữ liệu thật, in ra top tuyến và số tuyến đỏ/vàng. Nếu danh sách quá ngắn/dài (ngoài khoảng 3–10 tuyến; trên dữ liệu thật mặc định `min_orders=100`, `red=2,0`, `amber=1,5` cho 6 đỏ và 8 vàng), đề xuất giá trị `red`, `amber`, `min_orders` phù hợp kèm bằng chứng số liệu, KHÔNG tự đổi âm thầm.

### Giai đoạn 3 – Mô hình dự báo (Bước 6, tuỳ chọn – làm nếu giai đoạn 1–2 xong)
1. Tạo `etl/dss_ml.py`: so sánh Logistic Regression và Random Forest dự báo `is_late`.
2. Chỉ dùng đặc trưng biết trước khi giao hàng; cấm dùng `transit`, `delay_days`, `review_score`, `is_late` làm đặc trưng. Chia train/test theo thời gian.
3. In Accuracy, Precision, Recall, F1, Confusion Matrix, ROC-AUC trên tập kiểm tra.

### Giai đoạn 4 – API và giao diện (Bước 7–8)
1. Backend DSS dùng **Django** (OLAP/Dashboard/ETL Monitor do người khác làm bằng Flask, KHÔNG sửa phần Flask). Tạo project Django ở thư mục gốc repo (`manage.py`, `dss_project/`, app `dss/`) theo Bước 7 của hướng dẫn: `GET /api/dss/routes`, `GET /api/dss/scenario`, `GET /api/dss/promise`, `GET|POST /api/dss/actions` (ghi model `ActionLog` trong SQLite riêng của Django, không đụng kho dữ liệu), và `GET /api/dss/at-risk` nếu có mô hình ML. Bật CORS (django-cors-headers). Logic mô hình chỉ nằm trong `etl/dss_models.py`; view chỉ nhận tham số, gọi hàm, trả JSON. Chạy được bằng `python manage.py runserver 8000`.
2. Sửa hàm `DSS()` trong file HTML để gọi API thay cho dữ liệu mẫu; giữ nguyên bố cục 4 khối và các tab khác (Dashboard, OLAP). Bổ sung xử lý trạng thái đang tải và lỗi kết nối. Xoá `DS_ORD` và các hàm `ds*` chỉ sau khi giao diện chạy được bằng API.
3. Hướng dẫn chạy thử: các lệnh cụ thể để khởi động API và mở giao diện.

### Giai đoạn 5 – Đánh giá (Bước 9)
1. Viết hàm `backtest` theo hướng dẫn; chạy và thu kết quả.
2. Tạo `reports/dss_results.md` gồm: kết quả test, bảng backtest (tuyến gắn cờ vs còn lại), bảng chỉ số ML (nếu có), các tham số đã chọn và lý do, các hạn chế quan sát được.

## 3. Quy tắc bắt buộc
- Không bịa số liệu. Mọi con số trong báo cáo/giao diện phải đến từ dữ liệu thật hoặc được gắn nhãn rõ là dữ liệu mẫu.
- Không thay đổi các phần ngoài phạm vi (ETL của dim_*, tab Dashboard/OLAP) trừ khi cần thiết và phải nêu rõ.
- Bám theo phong cách code hiện có (import tương đối `.config`, chú thích tiếng Việt, tên biến tiếng Anh).
- Mỗi hàm mô hình phải kiểm thử được độc lập, không phụ thuộc giao diện.
- Cắt giảm thời gian trong `scenario` không được vượt giá trị thực tế của đơn (đã xử lý bằng `np.minimum`).
- Nếu gặp điểm mơ hồ (ví dụ tên cột khác, thiếu dữ liệu), hỏi lại hoặc nêu giả định rõ ràng thay vì tự quyết im lặng.
- Không cài thêm thư viện ngoài danh sách: pandas, numpy, scikit-learn, django, django-cors-headers, pytest.

## 4. Tiêu chí hoàn thành
- [ ] Các kiểm tra dữ liệu ở Giai đoạn 1 đạt; `is_late` suy ra từ `delay_days > 0` khớp 100%.
- [ ] `pytest -q` qua toàn bộ.
- [ ] Với tuyến hàng đầu: `scenario` cắt 0 ngày cho `projected == baseline`; cắt nhiều hơn không làm tỷ lệ trễ tăng; `goal_seek_promise` đạt `late_after <= target`.
- [ ] API Django chạy ở cổng 8000 và trả đúng JSON cho các endpoint DSS, giao diện lấy dữ liệu qua API và hiển thị đúng 4 khối.
- [ ] `reports/dss_results.md` có đủ số liệu đánh giá.
- [ ] Không còn dữ liệu mẫu cứng trong `DSS()` (hoặc được gắn nhãn rõ nếu giữ làm chế độ demo).

## 5. Cách báo cáo sau mỗi giai đoạn
Trả lời ngắn gọn: (1) đã làm gì, (2) file nào đã tạo/sửa (kèm đoạn diff với file hiện có), (3) lệnh đã chạy và kết quả chính, (4) điểm cần nhóm quyết định. Sau đó dừng và chờ xác nhận trước khi sang giai đoạn tiếp theo.
```

---

## Gợi ý dùng prompt hiệu quả

- Dán phần trong khung cho giai đoạn 1, chờ AI báo cáo, rồi mới nói "tiếp tục giai đoạn 2". Làm theo từng giai đoạn giúp bạn kiểm tra được kết quả và hiểu code trước khi đi tiếp.
- Sau Giai đoạn 2, bạn nên tự đọc `dss_models.py` và giải thích được từng hàm; giảng viên có thể hỏi trong buổi thuyết trình.
- Quyết định các tham số (`red`, `amber`, `min_orders`, mục tiêu 5%) là việc của nhóm, AI chỉ đề xuất dựa trên dữ liệu.
- Sau khi AI xong, quay lại đây để mình cập nhật Chương 4, 5, 6, 7 của báo cáo LaTeX theo kết quả thực tế.
