# QA BANK — 57 câu thầy có thể hỏi

> Mỗi câu trả lời ≤ 4 câu, kèm locator để mở code/báo cáo ngay.
> Nguyên tắc: **không bịa**. Nếu là đề xuất chưa làm → nói thẳng "chưa có trong repo".

## A. Thiết kế kho dữ liệu (9 câu)

### 1. Vì sao grain là 1 order item mà không phải 1 order?
Vì mỗi item có product, seller, freight riêng; gộp lên order sẽ mất chi tiết và không trả lời được "seller nào chậm". Fact giữ `order_id + order_item_id` làm PK, sau đó DSS mới gộp lại thành 1 dòng/(order, route) khi cần. `sql/create_tables.sql:26-52`; `etl/dss_models.py:27-33`.

### 2. Vì sao dùng star schema thay vì chuẩn hoá 3NF?
Truy vấn phân tích chủ yếu lọc theo thời gian/địa điểm/sản phẩm và tính tổng, nên 1 Fact + 3 Dim giảm join và dễ hiểu khi bảo vệ. Đây là lựa chọn thiết kế, không phải kết luận thực nghiệm. `sql/create_tables.sql:1-63`.

### 3. Vì sao Fact gọi là accumulating snapshot?
Vì một dòng Fact lưu nhiều mốc của **cùng một đơn**: mua, duyệt, giao carrier, giao khách, cam kết. Nhờ vậy tính được 3 chặng và `delay_days` ngay trên Fact. `etl/fact_delivery_sla.py:42-58`.

### 4. `payment_type` là gì trong mô hình?
Là **degenerate dimension**: chiều không có bảng riêng, nằm trực tiếp trong Fact. Mỗi đơn có thể nhiều payment, ETL chỉ giữ payment có `payment_value` lớn nhất. `sql/create_tables.sql:37-38`; `etl/fact_delivery_sla.py:94,110`.

### 5. Vì sao `location_id` là zip code prefix?
Dữ liệu gốc chỉ có zip prefix cho customer/seller; dùng nó làm khoá địa điểm là mức chi tiết cao nhất đáng tin. Dim_Location lưu thêm city/state/lat/lon để drill-down. `sql/create_tables.sql:10-17`; `etl/fact_delivery_sla.py:101-106`.

### 6. Vì sao `time_id` có dạng `YYYYMMDD`?
Vì nó vừa là khoá Dim_Time vừa mã hoá ngày mua, giúp sort/lọc theo năm-tháng-ngày dễ và tránh join phức tạp. `etl/fact_delivery_sla.py:61`; `sql/create_tables.sql:1-8`.

### 7. Một đơn có 2 seller thì Fact/DSS xử lý sao?
Fact có 2 nhóm item với 2 `seller_location_id`; `load_orders` gộp thành 2 dòng route cho cùng `order_id`. Vì vậy có **519 đơn nhiều tuyến** (tối đa 3), và số dòng order-route (**96.981**) lớn hơn số đơn (**96.455**). `etl/dss_models.py:30-33,34-47`; STATE (chạy thật).

### 8. Vì sao review và payment phải dedup trước khi merge?
Vì bảng gốc có nhiều dòng/đơn; merge thẳng sẽ nhân dòng Fact và làm sai mọi tỷ lệ. Review giữ bản mới nhất, payment giữ giá trị lớn nhất. `etl/fact_delivery_sla.py:64,94`.

### 9. `has_logistics_complaint` được tính thế nào?
Là `review_score <= 2` **và** comment chứa từ khoá logistics (atraso, demora, não recebi, transportadora...). Đây là cờ từ văn bản, không phải nhãn do người gán. `etl/fact_delivery_sla.py:65-91`.

## B. ETL (8 câu)

### 10. Lọc đơn thế nào trước khi tính?
Chỉ giữ `order_status == "delivered"` và drop các dòng thiếu 1 trong 5 mốc thời gian. Vì chưa giao thì không đo được trễ giao. `etl/fact_delivery_sla.py:41-52`.

### 11. Ba chặng tính từ mốc nào?
`approval` = duyệt − mua; `prep` = giao carrier − duyệt; `transit` = giao khách − giao carrier. Đơn vị ngày, chia `total_seconds()/86400`. `etl/fact_delivery_sla.py:54-56`.

### 12. `delay_days` định nghĩa ra sao? Âm nghĩa là gì?
`delay_days` = giao khách − ngày cam kết. Dương = trễ, âm = giao sớm, 0 = đúng hạn; `is_late` chỉ là `delay_days > 0`. `etl/fact_delivery_sla.py:57-58`; `etl/dss_models.py:27-47`.

### 13. Vì sao có prep/transit âm? Có bỏ không?
Có **1.542** dòng prep âm và **50** dòng transit âm do dữ liệu mốc thời gian lệch (carrier cập nhật trước/duyệt muộn). Không bỏ, chỉ ghi nhận; báo cáo nói rõ vì bỏ sẽ làm thay đổi độ lớn excess. `reports/dss_results.md:316`.

### 14. Vì sao Fact có 110.173 dòng nhưng chỉ 96.455 đơn?
Vì grain là item và join với order_items; một đơn nhiều item sinh nhiều dòng. Đây là lý do phải nói rõ "tỷ lệ trễ theo grain nào" khi trích số. `etl/fact_delivery_sla.py:98`; STATE (chạy thật).

### 15. Vì sao `load_orders` gộp item lên order-route?
Vì DSS ra quyết định theo tuyến, không theo từng item; gộp để mỗi đơn chỉ đóng góp 1 phiếu cho tuyến. `etl/dss_models.py:27-33`.

### 16. Chạy ETL bằng lệnh nào?
`python etl\main.py` để chỉ transform ra CSV; thêm `--load` để nạp PostgreSQL. Script chạy lần lượt 3 dim rồi fact. `etl/main.py:19-24,49-54`; `reports/run_guide.md:48-56`.

### 17. Vì sao `migrate` không tạo 4 bảng DW?
Vì 4 bảng đó khai báo `managed = False` và được tạo bằng `sql/create_tables.sql`; `migrate` chỉ tạo bảng nội bộ Django + `dss_action_log`. `reports/run_guide.md:45-46`.

## C. Logic DSS (16 câu)

### 18. Vì sao chọn ngưỡng đỏ 2,0× và vàng 1,5×?
Đây là **quy ước dễ giải thích** ("gấp đôi / gấp rưỡi mức chung"), không phải kết quả tối ưu. Bảng độ nhạy cho thấy đổi ngưỡng làm số tuyến gắn cờ chạy **11–30**, nên phải nói rõ "14 tuyến" chỉ đúng với 100/2,0/1,5. `reports/dss_formulas.md:58-68`; `reports/dss_results.md:225-232`.

### 19. Vì sao dùng ngưỡng tương đối thay vì tuyệt đối (ví dụ 5%)?
Vì mức trễ nền thay đổi theo thời gian; ngưỡng tuyệt đối sẽ gắn cờ gần như mọi tuyến ở giai đoạn trễ cao. Ngưỡng tương đối giữ ý nghĩa "cao hơn mặt bằng chung". `etl/dss_models.py:119,130-134`.

### 20. `min_orders=100` lấy từ đâu?
Là ngưỡng chống kết luận từ mẫu quá nhỏ, chọn theo kinh nghiệm; backtest dùng 30 vì chia theo tháng, production vẫn 100 vì chạy full data. `etl/dss_models.py:94,129`; `reports/dss_results.md:119`.

### 21. Wilson interval để làm gì?
Tính khoảng tin cậy 95% cho tỷ lệ trễ của từng tuyến, không cho cận âm và ổn định khi `n` nhỏ. `etl/dss_models.py:79-90`.

### 22. Vì sao không dùng `p ± 1,96·√(p(1−p)/n)`?
Vì xấp xỉ chuẩn có thể cho cận âm hoặc vượt 1 khi `p` gần 0 và `n` nhỏ — đúng tình huống các tuyến 124–8.108 đơn. Wilson là lựa chọn an toàn hơn. `etl/dss_models.py:79-90`.

### 23. `low_sample` và `uncertain` khác nhau thế nào?
`low_sample` = dưới 200 đơn; `uncertain` = Wilson CI chứa ngưỡng phân loại. Hai cờ **độc lập**: PR→RJ có 994 đơn nhưng vẫn `uncertain=True`; cả hai chỉ cảnh báo, không đổi nhãn. `etl/dss_models.py:141-150`; `reports/dss_results.md:257,268`.

### 24. Red-first là gì và tại sao cần?
Là trả **tất cả tuyến đỏ trước** (sắp theo số đơn trễ), rồi mới thêm vàng cho đủ `top`; nếu số đỏ > `top` thì trả hết đỏ. Mục tiêu là không che tuyến đỏ chỉ vì giới hạn hiển thị. `etl/dss_models.py:101-105,152-166`.

### 25. Báo cáo nói 14 tuyến, API trả 10 — sai không?
Không sai: 14 là toàn bộ tập gắn cờ, 10 là mặc định hiển thị. Truyền `top=20` (hoặc lớn hơn) để lấy đủ. `backend/dss/views.py:58-66`; `reports/dss_results.md:284`.

### 26. Root cause hiện tại tính gì?
`excess[s] = mean(chặng s của tuyến) − mean(chặng s toàn hệ thống)`, chọn `argmax` làm `stage`; `has_bottleneck = max(excess) > 0`. `etl/dss_models.py:169-190`; `reports/dss_formulas.md:103-123`.

### 27. Vì sao nói root cause là tautology?
Vì transit trung bình ~9,3 ngày, dài hơn prep ~2,8 và approval ~0,43, nên `argmax` gần như luôn chọn transit. Thực tế **13/14 tuyến** có `stage=transit` — đúng nhưng ít thông tin. `reports/dss_results.md:247`; `reports/dss_formulas.md:109`.

### 28. `excess_ratio` có sửa được phê bình đó không?
Không: nó chỉ chia excess cho `|mean chặng|`, và **0/14 tuyến đổi stage**. Vì vậy không thể nói ratio làm root cause "công bằng" hơn. `reports/dss_results.md:247`; `reports/dss_formulas.md:125-129`.

### 29. Nếu median được dùng làm benchmark thì sao?
Repo **không dùng median**; hiện tại là mean. Median/P10 theo decile khoảng cách chỉ là **đề xuất chưa triển khai** — nói "chưa có trong repo", đừng nhận là đã làm. `etl/dss_models.py:176-179`.

### 30. Scenario giả định cốt lõi là gì?
Cắt `c_s` ngày ở chặng `s` làm giảm `delay_days` đúng `min(c_s, x_s)` ngày, tức giảm thời gian chuyển 1:1 sang ngày giao. Đây là giả định cơ học, bỏ qua buffer và chi phí. `reports/dss_formulas.md:135-151`; `etl/dss_models.py:193-210`.

### 31. Vì sao cắt 1 ngày approval thường ít tác dụng hơn 1 ngày transit?
Vì `min(c, x_s)`: approval trung bình chỉ 0,43 ngày nên "cắt 1" thường chỉ cắt được <1; transit ~9,3 ngày nên gần như luôn đủ 1. Đây **không phải** bằng chứng transit quan trọng hơn về nhân quả. `reports/dss_formulas.md:137-139,109`.

### 32. Vì sao `projected` không tuyến tính theo số ngày cắt?
Vì chỉ các đơn sát ngưỡng mới "lật" từ trễ sang không trễ; cắt thêm ngày sau đó ít đơn hơn. Vì vậy lợi ích biên giảm dần (SP→RJ: 14,20% → 12,33% → 10,88% khi cắt 1/3/5). `reports/dss_results.md:239-241`.

### 33. Promise và cut khác nhau ở đâu?
Promise kéo dài **cam kết** (đổi định nghĩa trễ, không đổi vận hành); cut giảm **thời gian thực** ở một chặng. Dưới giả định 1:1, cắt `c` ngày transit thường cho cùng kết quả với kéo cam kết `c` ngày. `etl/dss_models.py:236-250`; `reports/dss_results.md:318`.

### 34. Vì sao promise 10 ngày không phải "cải thiện dịch vụ"?
Vì khách vẫn nhận hàng muộn như cũ, chỉ ngày cam kết bị đẩy ra xa hơn. Đây là thay đổi kỳ vọng, có đánh đổi về cạnh tranh/trải nghiệm. `etl/dss_models.py:236-240`.

### 35. Vì sao `goal_seek_cut` cho SP→BA = 10 không khả thi?
Vì excess transit của tuyến chỉ **7,2034** ngày, cắt 10 vượt phần vượt thực tế; đồng thời 10 chạm trần `max_days=10` nên chỉ là biên của hàm. SP→ES cũng cần 9 trong khi excess chỉ **3,1144**. `reports/dss_results.md:317-318,240-243`.

### 36. `base_cut` trong sensitivity để làm gì?
Giữ mức cắt hiện tại của các chặng **khác** khi quét chặng bottleneck, để điểm `series[0]` khớp đúng `projected` đang xem. Nếu không có, đường cong sẽ lệch bối cảnh. `etl/dss_models.py:213-233`; `backend/dss/views.py:88-97`.

## D. Thống kê & đánh giá (10 câu)

### 37. Backtest làm gì?
Chạy `route_priority` trên riêng dữ liệu kỳ `t`, rồi so tỷ lệ trễ nhóm gắn cờ với phần còn lại ở kỳ `t+1`. Đây là kiểm tra tín hiệu một bước, không phải triển khai thật. `etl/dss_eval.py:91-127`.

### 38. Vì sao chia theo thời gian thay vì random?
Vì dữ liệu là chuỗi thời gian; chia random sẽ để thông tin tương lai rò vào quá khứ. Cách làm là train/test theo kỳ liền kề. `etl/dss_eval.py:101-107`.

### 39. Vì sao backtest dùng `min_orders=30`?
Vì chia theo tháng thì mỗi tuyến ít đơn; 100 làm 6/19 kỳ không có cờ, 50 làm 2 kỳ. Production vẫn dùng 100 vì chạy full data. `reports/dss_results.md:119`.

### 40. `weighted_diff` khác `mean_diff` thế nào?
`mean_diff` là trung bình cộng 19 kỳ; `weighted_diff` trọng số theo `total_orders` kỳ `t+1` để kỳ lớn không bị kỳ nhỏ chi phối. Số chính là weighted **+8,14 pp**, mean **+7,13 pp**. `reports/dss_results.md:47-67`.

### 41. Vì sao phải báo 3 phản ví dụ?
Vì "16/19" che mất việc có kỳ tín hiệu đảo chiều; 201701 **−0,98 pp**, 201708 **−1,82 pp**, 201807 **−9,33 pp**. Báo đủ để thấy kết luận không đồng nhất. `reports/dss_results.md:121-124`.

### 42. CI vs through chứa 0 nghĩa là gì?
Nghĩa là chưa đủ bằng chứng nói DSS khác through; chỉ được nói "cao hơn ~+0,8 pp theo điểm ước lượng, không có ý nghĩa thống kê". **Không được dùng chữ "vượt"**. `reports/dss_results.md:208-216,218`.

### 43. Bootstrap pair và block khác nhau thế nào?
Pair resample theo từng kỳ; block 3 tháng circular giữ cấu trúc tự tương quan giữa các kỳ gần nhau. Cả hai đều cho vs through chứa 0. `etl/dss_eval.py:616-621,674-684`.

### 44. Threshold sensitivity chứng minh điều gì?
Chứng minh kết luận "14 tuyến" không bất biến: 50/1,5/1,25 cho **30** tuyến; 200/2,0/1,5 cho **11**. Vì vậy luôn nói kèm bộ tham số. `reports/dss_results.md:225-232`.

### 45. Chỉ 19 kỳ thì CI có đáng tin?
Chỉ mang tính tham khảo; báo cáo đã ghi rõ. Circular block còn nối kỳ cuối với kỳ đầu, là xấp xỉ. `reports/dss_results.md:222`.

### 46. Vì sao dùng Wilson cho từng tuyến mà không dùng bootstrap?
Wilson có công thức đóng, nhanh cho 14 tuyến và phù hợp tỷ lệ nhị phân; bootstrap dùng cho hiệu số backtest phức tạp hơn. Hai mục đích khác nhau. `etl/dss_models.py:79-90`; `etl/dss_eval.py:605-646`.

## E. "Sao không dùng ML?" / nhân quả (6 câu)

### 47. Sao không dùng ML để dự báo trễ?
Repo **đã từng có prototype ML nhưng đã gỡ hoàn toàn** (`af9249c`); hiện chỉ còn DSS luật. Lý do: dữ liệu lệch thời gian, tỷ lệ dương thấp, và mô hình hộp đen khó bảo vệ hơn luật giải thích được. `git log --oneline`; không còn `etl/dss_ml.py`, `data/models/`.

### 48. AUC của mô hình là bao nhiêu?
**Không có** — ML đã bị gỡ, `data/models/` không tồn tại, báo cáo không còn AUC. Đừng trích 0,66 hay 0,77; đó là số của phiên bản cũ. `git show --stat af9249c`.

### 49. Kết quả của em có phải nhân quả?
Không. Đây là chênh lệch mô tả + mô phỏng what-if; không có thử nghiệm hay biến công cụ. Chỉ được nói "liên quan", "nếu giả định..., thì...". `reports/dss_formulas.md:151`.

### 50. Shapley attribution đâu?
**Chưa có trong repo.** Không có `dss_attrib`, không có benchmark/residual như bản v2 mô tả; nếu bị hỏi phải nói "đề xuất, chưa triển khai". `reports/DSS_V2_PROMPT.md` (yêu cầu) vs grep `shapley|dss_attrib` không kết quả.

### 51. Residual "promise too tight" là gì, em tính chưa?
Khái niệm: residual = ngày giao thực tế − ngày cam kết; residual dương hệ thống nghĩa là cam kết quá chặt. Repo **chưa** tính phân rã này; chỉ có `goal_seek_promise` dựa trên phân vị `delay_days`. `etl/dss_models.py:236-240`.

### 52. Nếu có thêm dữ liệu seller_id trong Fact thì sao?
Fact hiện chưa có `seller_id`, nên root cause chỉ xuống được mức **giai đoạn**, không chỉ ra seller cụ thể. Đây là hạn chế đã ghi trong hướng dẫn. `DSS_HUONG_DAN.md:416`.

## F. Hạn chế & tính trung thực (5 câu)

### 53. Điểm yếu lớn nhất của đồ án?
Root cause gần như tautology (13/14 transit) và what-if bỏ qua khả thi/chi phí. Ngoài ra `vs through` không có ý nghĩa thống kê. `reports/dss_results.md:247,208-216`; `reports/dss_formulas.md:151`.

### 54. Điều gì sẽ bác bỏ kết luận của em?
Nếu tín hiệu gắn cờ không còn khi đổi `min_orders`/ngưỡng, hoặc các kỳ sau đảo chiều mạnh như 201807, hoặc dữ liệu bị drift theo mùa. Bảng sensitivity và 3 phản ví dụ chính là các kiểm tra đó. `reports/dss_results.md:225-232,121-124`.

### 55. Số nào hay bị trích sai nhất?
"14 tuyến" (thực tế API mặc định 10), "8,07%" (đúng cho order-route; fact là 7,91%, order là 8,11%), và "cắt transit giảm 2,09 pp" (đó là mô phỏng, không phải nhân quả). `STATE.md:15`; `reports/dss_results.md:239-241`.

### 56. Tab nào là thật, tab nào mock?
Chỉ **DSS Action Center** gọi API Django thật; Dashboard, OLAP, ETL Monitor là mock tĩnh. Nói rõ trước khi thầy bấm. `web/Olist_Logistics_DSS_v3.html:427`; `reports/run_guide.md:93-96`.

### 57. Nếu thầy yêu cầu chạy lại ngay bây giờ?
Chạy `python etl\main.py` (nếu cần tái tạo CSV), `pytest -q`, `manage.py test dss`, rồi one-liner trong `CHEAT_SHEET.md`. Kỳ vọng 26/16 test và `overall 8.0727%`. `reports/run_guide.md:104-134`.

## G. Đóng góp nhóm — điền trước khi bảo vệ

> Phần này **CHƯA XÁC MINH** trong repo; mình không biết ai làm gì. Điền theo thực tế, mỗi người kèm 1 bằng chứng (commit/file).

| Thành viên | Phần phụ trách | Bằng chứng nên nêu |
|---|---|---|
| (điền) | DW/DDL + ETL | `sql/create_tables.sql`, `etl/*.py` |
| (điền) | DSS model + đánh giá | `etl/dss_models.py`, `etl/dss_eval.py` |
| (điền) | API + UI | `backend/dss/views.py`, `web/*.html` |
| (điền) | Báo cáo/slide | `reports/*.md` |

**Câu chốt an toàn:** "Phần em nắm chắc nhất là …; phần … do bạn … phụ trách, em có đọc nhưng không phải người viết chính."
