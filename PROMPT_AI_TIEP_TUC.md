# Prompt bàn giao: AI mới tiếp tục phần DSS (dán toàn bộ khối bên dưới)

> Cách dùng: mở repo `Brazillian` bằng công cụ AI mới, đính kèm `DSS_HUONG_DAN.md` (nếu có) và dán khối này. AI cũ đã làm xong Giai đoạn 1, 2, 4, 5 và hết token ở bước chờ xác nhận.

```text
Bạn tiếp nhận một dự án dở dang từ AI khác (đã hết token). Hãy làm việc cẩn thận, KHÔNG làm lại những phần đã xong, KHÔNG bịa số liệu. Trả lời bằng tiếng Việt.

## 1. Dự án
Bài tập lớn môn Kho dữ liệu và Hệ hỗ trợ Quyết định (CO4031, HK261, hạn nộp 23:59 ngày 15/11/2026). Đề tài: DSS phân tích điểm nghẽn và tối ưu quy trình hoàn tất đơn hàng, dữ liệu Olist Brazilian E-Commerce. Người dùng DSS: Giám đốc Vận hành. DSS có 4 khối: (1) Route Priority, (2) Root Cause, (3) Scenario/What-if, (4) Recommendation & Action. Mô hình phân tích/mô phỏng hoàn toàn theo luật.

## 2. Môi trường và cấu trúc repo (Windows, PostgreSQL)
- Thư mục gốc: `Brazillian/`. Python: `.\backend\env\Scripts\python.exe`.
- `etl/` : script ETL (config.py, dim_*.py, fact_delivery_sla.py, load_data.py, stats_for_report.py) và phần DSS đã viết: `etl/dss_models.py`, `etl/dss_eval.py`.
- `data/processed/` : cleaned_fact_orders.csv (Fact: 110173 dòng, 96455 đơn; có `delay_days`, `has_logistics_complaint`; KHÔNG có `is_late`, quy ước đơn trễ = `delay_days > 0`), cleaned_dim_product/time/location.csv.
- `backend/` : Django (core/settings.py, core/urls.py). App `dss` (views.py, models.py `ActionLog` db_table `dss_action_log`, urls.py, tests.py, migrations/0001_initial.py) đã thêm vào project có sẵn. `backend/analytics/models.py` ánh xạ kho dữ liệu (managed=False).
- `web/Olist_Logistics_DSS_v3.html` : giao diện mẫu (React qua CDN). Hàm `DSS()` đã gọi API Django `http://localhost:8000/api/dss`; các tab Dashboard, OLAP, ETL Monitor vẫn dùng dữ liệu mẫu (do bạn trong nhóm làm Flask, chưa nối).
- `tests/` : test_dss_models.py, test_dss_eval.py, conftest.py. `reports/` : dss_results.md, dss_eval_raw.txt. `frontend/` : Vite starter, không dùng.

## 3. Những gì ĐÃ XONG (đã được kiểm chứng độc lập, đừng làm lại)
- Model Base `etl/dss_models.py`: load_orders (1 dòng = 1 (order_id, route), route = "bang người bán->bang khách"), route_priority, root_cause (có `has_bottleneck`), scenario, sensitivity, goal_seek_promise, goal_seek_cut, RULES.
- API Django: GET /api/dss/routes, /scenario, /promise; GET|POST /api/dss/actions. NaN→null, route thiếu/không tồn tại → 400. 13 test Django qua.
- Giao diện DSS nối API: debounce 250ms, trạng thái tải/lỗi, Apply ghi log thật.
- Đánh giá (Giai đoạn 5): `etl/dss_eval.py`, `reports/dss_results.md`. 18 pytest qua.
- Đã làm thêm: giải thích `weighted_diff` (+8,14 điểm % chính, +10,32 phụ); tài liệu `reports/api_dss.md`, `run_guide.md`, `dss_formulas.md`; sửa `sensitivity` có tham số `base_cut` (điểm chuỗi độ nhạy khớp `projected`).
- Kết quả đã kiểm chứng trên dữ liệu thật (dùng để đối chiếu nếu cần):
  - Tỷ lệ trễ theo đơn 8,07%; 96981 dòng (đơn, tuyến); 519 đơn nhiều tuyến; 72 tuyến ≥100 đơn.
  - route_priority mặc định (min_orders=100, red=2.0, amber=1.5): 14 tuyến (6 đỏ, 8 vàng); top=10 mặc định. Top 3 theo số đơn trễ: SP->RJ (8108 đơn, 15,58%), SP->BA (2295, 14,99%), SP->ES (1459, 14,12%), cả ba mức vàng.
  - SP->RJ: nghẽn ở transit (excess duyệt −0,04, chuẩn bị +0,21, vận chuyển +3,60 ngày); cắt chuẩn bị 0/1/2/3/5 ngày → 15,58/14,38/13,74/13,46/12,99%; goal_seek_promise(5%) = 15 ngày (late_after 4,66%); goal_seek_cut không đạt trong 10 ngày. SP->BA: promise 10 ngày, cắt transit 10 ngày; SP->ES: promise 9 ngày, cắt transit 9 ngày.
  - SP->SP: 30617 đơn, 6,22%, has_bottleneck = False.
  - Độ nhạy ngưỡng: (min_orders, red, amber) = (50,2,1.5)→22 tuyến; (50,1.5,1.25)→30 (22 đỏ/8 vàng); (100,2,1.5)→14; (100,1.5,1.25)→21; (200,2,1.5)→11 (4/7); (200,1.5,1.25)→16.
  - Backtest theo tháng (min_orders=30, từ 2017): 19 kỳ, nhóm gắn cờ trễ hơn ở 16/19 kỳ, chênh lệch trung bình không trọng số +7,13 điểm %; 3 kỳ không ủng hộ: 201702, 201709, 201808. min_orders=100 chỉ đánh giá được 13/19 kỳ.
  - Dữ liệu: seller_prep_time_days âm 1542 dòng, carrier_transit_time_days âm 50 dòng, review_score rỗng 827 dòng; loại các dòng âm không đổi kết luận nghẽn (SP->RJ transit excess 3,603→3,620).

## 4. Việc còn lại
Mọi việc bắt buộc của DSS đã xong (Giai đoạn 1, 2, 4, 5, tài liệu, sửa độ nhạy). Việc tiếp theo do nhóm chỉ định ở cuối prompt này; baseline đơn giản cho backtest đã quyết định bỏ qua. Nếu không có yêu cầu cụ thể: chỉ chạy lại `pytest -q` và `manage.py test dss`, báo kết quả, rồi dừng.

## 5. Quy tắc bắt buộc
- Đọc trạng thái hiện tại trước (git status/diff, reports/dss_results.md, tests) và nêu ngắn gọn điểm nào lệch so với mô tả ở mục 2–3 trước khi làm.
- KHÔNG sửa: phần Flask (OLAP/Dashboard của người khác), `backend/analytics/models.py`, `frontend/`, các script ETL, và không đổi giao diện trừ khi phát hiện lỗi (báo trước). KHÔNG commit/push git trừ khi được yêu cầu.
- Mọi con số phải đến từ lần chạy thật kèm lệnh đã chạy; nếu kết quả khác mục 3, báo chênh lệch thay vì chỉnh cho khớp.
- Không cài thêm thư viện ngoài pandas, numpy, django, django-cors-headers, pytest, psycopg2-binary.
- Nếu gặp điểm mơ hồ, hỏi lại hoặc nêu giả định rõ ràng.

## 6. Cách báo cáo sau mỗi mục
Trả lời ngắn gọn 4 phần: (1) đã làm gì, (2) file tạo/sửa (kèm diff nếu sửa file có sẵn), (3) lệnh đã chạy và kết quả chính, (4) điểm cần nhóm quyết định. Rồi dừng, chờ xác nhận.
```

## Ghi chú cho nhóm
- Nếu AI mới làm xong mục A–C, gửi `reports/dss_results.md`, `reports/api_dss.md`, `reports/dss_formulas.md` và ảnh chụp tab DSS để cập nhật báo cáo LaTeX (mục 5.2, Chương 6, 7, bảng chuẩn đầu ra).
- Phần kiểm tra giao diện bằng mắt (SP→RJ đứng đầu, thanh trượt giảm dần, Apply ghi log) vẫn do nhóm tự làm, vì AI không mở được trình duyệt.
