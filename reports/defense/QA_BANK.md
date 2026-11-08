# QA BANK — 71 câu thầy có thể hỏi

> Mỗi câu trả lời ≤ 4 câu, kèm locator để mở code/báo cáo ngay.
> Nguyên tắc: **không bịa**. Nếu là đề xuất chưa làm → nói thẳng "chưa có trong repo".

## A. Thiết kế kho dữ liệu (9 câu)

### 1. Vì sao grain là 1 order item mà không phải 1 order?
Vì mỗi item có product, seller, freight riêng; gộp lên order sẽ mất chi tiết. Fact giữ `order_id + order_item_id` làm PK, sau đó DSS mới gộp lại thành 1 dòng/(order, route) khi cần. `sql/create_tables.sql`; `etl/dss_models.py`.

### 2. Vì sao dùng star schema thay vì chuẩn hoá 3NF?
Truy vấn phân tích chủ yếu lọc theo thời gian/địa điểm/sản phẩm và tính tổng, nên 1 Fact + 4 Dim dễ hiểu khi bảo vệ. Đây là lựa chọn thiết kế, không phải kết luận thực nghiệm. `sql/create_tables.sql`.

### 3. Vì sao Fact gọi là accumulating snapshot?
Vì một dòng Fact lưu nhiều mốc của **cùng một đơn**: mua, duyệt, giao carrier, giao khách, cam kết. Nhờ vậy tính được 3 chặng và `delay_days` ngay trên Fact. `etl/fact_delivery_sla.py:42-58`.

### 4. `payment_type` là gì trong mô hình?
Là **degenerate dimension**: chiều không có bảng riêng, nằm trực tiếp trong Fact. Mỗi đơn có thể nhiều payment, ETL chỉ giữ payment có `payment_value` lớn nhất. `sql/create_tables.sql:37-38`; `etl/fact_delivery_sla.py:94,110`.

### 5. Vì sao `location_id` là zip code prefix?
Dữ liệu gốc chỉ có zip prefix cho customer/seller; dùng nó làm khoá địa điểm là mức chi tiết cao nhất đáng tin. Dim_Location lưu thêm city/state/lat/lon để drill-down. `sql/create_tables.sql:10-17`; `etl/fact_delivery_sla.py:101-106`.

### 6. Vì sao `time_id` có dạng `YYYYMMDD`?
Vì nó vừa là khoá Dim_Time vừa mã hoá ngày mua, giúp sort/lọc theo năm-tháng-ngày dễ và tránh join phức tạp. `etl/fact_delivery_sla.py:61`; `sql/create_tables.sql:1-8`.

### 7. Một đơn có 2 seller thì Fact/DSS xử lý sao?
Fact có thể có nhiều seller theo item; `load_orders` gộp theo route. Raw eval ghi nhận **502** đơn nhiều seller bị loại khỏi seller scorecard; mẫu phân tích có 95.591 đơn-tuyến trên 95.082 đơn duy nhất. `reports/dss_eval_raw.txt`, mục Seller scorecard.

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
Có **1.361** đơn-tuyến prep âm và **29** transit âm; tổng **1.390** đơn-tuyến bị loại khỏi DSS. `reports/dss_eval_raw.txt`, mục Thời gian âm.

### 14. Vì sao Fact có 110.173 dòng nhưng chỉ 95.082 đơn duy nhất?
Vì grain là item; một đơn nhiều item sinh nhiều dòng. Fact có 21 cột theo DDL, còn raw eval ghi nhận 95.591 đơn-tuyến sau lọc. Nêu rõ grain khi trích tỷ lệ. `sql/create_tables.sql`; `reports/dss_eval_raw.txt`.

### 15. Vì sao `load_orders` gộp item lên đơn-tuyến (order-route)?
Vì DSS ra quyết định theo tuyến, không theo từng item; gộp để mỗi đơn chỉ đóng góp 1 phiếu cho tuyến. `etl/dss_models.py:27-33`.

### 16. Chạy ETL bằng lệnh nào?
`python etl\main.py` để chỉ transform ra CSV; thêm `--load` để nạp PostgreSQL. Script chạy lần lượt 3 dim rồi fact. `etl/main.py:19-24,49-54`; `reports/run_guide.md:48-56`.

### 17. Vì sao `migrate` không tạo 5 bảng DW?
Vì 5 bảng đó khai báo `managed = False` và được tạo bằng `sql/create_tables.sql`; `migrate` chỉ tạo bảng nội bộ Django + `dss_action_log`. `reports/run_guide.md`.

## C. Logic DSS (16 câu)

### 18. Vì sao chọn ngưỡng đỏ 2,0× và vàng 1,5×?
Đây là **quy ước dễ giải thích** ("gấp đôi / gấp rưỡi mức chung"), không phải kết quả tối ưu. Ở min_orders=100, năm cặp ngưỡng quanh mặc định cho **10–21 tuyến**; 100/2,5/2,0 giữ lõi 6 tuyến. "14 tuyến" chỉ đúng với 100/2,0/1,5. `reports/dss_eval_raw.txt`, mục S8.

### 19. Vì sao dùng ngưỡng tương đối thay vì tuyệt đối (ví dụ 5%)?
Vì mức trễ nền thay đổi theo thời gian; ngưỡng tuyệt đối sẽ gắn cờ gần như mọi tuyến ở giai đoạn trễ cao. Ngưỡng tương đối giữ ý nghĩa "cao hơn mặt bằng chung". `etl/dss_models.py:119,130-134`.

### 20. `min_orders=100` lấy từ đâu?
Là ngưỡng chống kết luận từ mẫu quá nhỏ, chọn theo kinh nghiệm; backtest dùng 30 vì chia theo tháng, production vẫn 100 vì chạy full data. `etl/dss_models.py:94,129`; `reports/dss_results.md:119`.

### 21. Wilson interval để làm gì?
Tính khoảng tin cậy 95% cho tỷ lệ trễ của từng tuyến, không cho cận âm và ổn định khi `n` nhỏ. Cách tính không hiệu chỉnh phụ thuộc giữa đơn cùng tuyến/cụm nên mức bất định thực tế có thể lớn hơn. `etl/dss_models.py:79-90`.

### 22. Vì sao không dùng `p ± 1,96·√(p(1−p)/n)`?
Vì xấp xỉ chuẩn có thể cho cận âm hoặc vượt 1 khi `p` gần 0 và `n` nhỏ — đúng tình huống các tuyến 124–8.108 đơn. Wilson là lựa chọn an toàn hơn về miền giá trị, nhưng vẫn giả định các đơn độc lập và không xử lý clustering. `etl/dss_models.py:79-90`.

### 23. `low_sample` và `uncertain` khác nhau thế nào?
`low_sample` = dưới 200 đơn; `uncertain` = Wilson CI chứa ngưỡng phân loại. Hai cờ **độc lập**: PR→RJ có 994 đơn nhưng vẫn `uncertain=True`; Wilson giả định đơn độc lập nên không hiệu chỉnh clustering. `etl/dss_models.py:141-150`; `reports/dss_results.md:257,268`.

### 24. Red-first là gì và tại sao cần?
Là trả **tất cả tuyến đỏ trước** (sắp theo số đơn trễ), rồi mới thêm vàng cho đủ `top`; nếu số đỏ > `top` thì trả hết đỏ. Mục tiêu là không che tuyến đỏ chỉ vì giới hạn hiển thị. `etl/dss_models.py:101-105,152-166`.

### 25. Báo cáo nói 14 tuyến, API trả 10 — sai không?
Không sai: 14 là toàn bộ tập gắn cờ, 10 là mặc định hiển thị. Truyền `top=20` (hoặc lớn hơn) để lấy đủ. `backend/dss/views.py:58-66`; `reports/dss_results.md:284`.

### 26. Root cause hiện tại tính gì?
`excess[s] = mean(chặng s của tuyến) − mean(chặng s toàn hệ thống)`, chọn `argmax` làm `stage`; `has_bottleneck = max(excess) > 0`. `etl/dss_models.py:169-190`; `reports/dss_formulas.md:103-123`.

### 27. Vì sao transit chiếm phần lớn attribution?
Ở q=0,50 transit là 69,8820% tỷ trọng trong tập đơn trễ; V2 bootstrap route-level cho 69,9162%, CI 95% [56,4003%; 83,5136%]. Đây là phân rã mô tả, không phải tỷ lệ trễ hay quan hệ nhân quả. `reports/dss_eval_raw.txt`.

### 28. `excess_ratio` có sửa được phê bình đó không?
Không thể dùng excess_ratio để biến chẩn đoán mô tả thành nguyên nhân nhân quả; đây chỉ là cách chuẩn hoá một đại lượng excess khác.

### 29. Nếu median được dùng làm benchmark thì sao?
Benchmark dùng approval theo `payment_type`, prep theo `weight_band`, transit theo decile khoảng cách xuyên tuyến; nhóm thiếu mẫu/NA fallback median toàn cục cùng giai đoạn. Không nhầm fallback này với P50 tham chiếu của S4. `reports/dss_eval_raw.txt`.

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
Vì chia theo tháng thì mỗi tuyến ít đơn; min_orders=30 cho 19 kỳ đủ điều kiện, còn 100 chỉ có 13 kỳ đủ điều kiện. Production vẫn dùng 100 vì chạy full data. `reports/dss_eval_raw.txt`, mục backtest.

### 40. `weighted_diff` khác `mean_diff` thế nào?
`mean_diff` là trung bình cộng 19 kỳ; `weighted_diff` trọng số theo `total_orders` kỳ `t+1`. Hiện tại weighted là **+8,2826 pp**, mean **+7,2403 pp**, flagged-weighted **+10,4624 pp**. Đây là tương quan hồi cứu. `reports/dss_eval_raw.txt`, mục backtest.

### 41. Vì sao phải báo 3 phản ví dụ?
Vì "16/19" che mất kỳ chênh lệch âm; V4 hiện ghi 201701 **−0,983 pp**, 201708 **−1,802 pp**, 201807 **−9,400 pp**. Báo đủ để thấy kết quả không đồng nhất. `reports/dss_eval_raw.txt`, mục Sign test (V4).

### 42. CI vs through chứa 0 nghĩa là gì?
Nghĩa là **chưa đủ bằng chứng** DSS tốt hơn through; pair CI hiện tại là [−0,50; +2,52] pp. **Không được dùng chữ "vượt"**. `reports/dss_eval_raw.txt`, mục bootstrap.

### 43. Bootstrap pair và block khác nhau thế nào?
Pair resample theo từng kỳ; block 3 tháng circular giữ cấu trúc tự tương quan giữa các kỳ gần nhau. Cả hai đều cho vs through chứa 0. `etl/dss_eval.py:616-621,674-684`.

### 44. Threshold sensitivity chứng minh điều gì?
Chứng minh kết luận "14 tuyến" không bất biến: toàn lưới cho **4–30** tuyến; tại min_orders=100, năm cặp quanh mặc định cho **10–21**. Vì vậy luôn nói kèm bộ tham số. `reports/dss_eval_raw.txt`, mục S8.

### 45. Chỉ 19 kỳ thì CI có đáng tin?
Chỉ mang tính tham khảo; báo cáo đã ghi rõ. Circular block còn nối kỳ cuối với kỳ đầu, là xấp xỉ. `reports/dss_results.md:222`.

### 46. Vì sao dùng Wilson cho từng tuyến mà không dùng bootstrap?
Wilson có công thức đóng, nhanh cho 14 tuyến và phù hợp tỷ lệ nhị phân; bootstrap dùng cho hiệu số backtest phức tạp hơn. Wilson vẫn giả định đơn độc lập, còn bootstrap theo tuyến không loại bỏ mọi phụ thuộc. `etl/dss_models.py:79-90`; `etl/dss_eval.py:605-646`.

## E. "Sao không dùng ML?" / nhân quả (6 câu)

### 47. Sao không dùng ML để dự báo trễ?
Repo **đã từng có prototype ML nhưng đã gỡ hoàn toàn** (`af9249c`); hiện chỉ còn DSS luật. Lý do: dữ liệu lệch thời gian, tỷ lệ dương thấp, và mô hình hộp đen khó bảo vệ hơn luật giải thích được. `git log --oneline`; không còn `etl/dss_ml.py`, `data/models/`.

### 48. AUC của mô hình là bao nhiêu?
**Không có** — ML đã bị gỡ, `data/models/` không tồn tại, báo cáo không còn AUC. Đừng trích 0,66 hay 0,77; đó là số của phiên bản cũ. `git show --stat af9249c`.

### 49. Kết quả của em có phải nhân quả?
Không. Đây là chênh lệch mô tả + mô phỏng what-if; không có thử nghiệm hay biến công cụ. Chỉ được nói "liên quan", "nếu giả định..., thì...". `reports/dss_formulas.md:151`.

### 50. Shapley attribution đâu?
Đã triển khai attribution theo peer benchmark. Approval benchmark theo `payment_type`, prep theo `weight_band`, transit theo decile khoảng cách xuyên tuyến; kết quả `cause_share_*` là tỷ trọng trong tập đơn trễ. `reports/dss_eval_raw.txt`, mục Attribution.

### 51. Vì sao q=0,75 không được báo cáo?
Ở q=0,75 benchmark chậm hơn actual, tạo phi âm và phân rã không hợp lệ; độ nhạy chỉ dùng q=0,25 và q=0,50. `reports/dss_eval_raw.txt`, mục Attribution.

### 52. Seller scorecard có chứng minh seller gây trễ không?
Không. Scorecard chỉ dùng đơn single-seller; khác biệt có thể do route mix và thành phần đơn. Đây là liên hệ, không phải quy kết nguyên nhân. `reports/dss_eval_raw.txt`, mục Seller scorecard.

## F. Hạn chế & tính trung thực (5 câu)

### 53. Điểm yếu lớn nhất của đồ án?
Ước lượng có thể bị confound bởi route mix, what-if bỏ qua khả thi/chi phí, và CI so với through chứa 0 nên chưa đủ bằng chứng DSS tốt hơn. `reports/dss_eval_raw.txt`, mục V2/V4.

### 54. Điều gì sẽ bác bỏ kết luận của em?
Nếu tín hiệu gắn cờ không còn khi đổi `min_orders`/ngưỡng, hoặc các kỳ sau đảo chiều mạnh như 201807, hoặc dữ liệu bị drift theo mùa. Bảng sensitivity và 3 phản ví dụ chính là các kiểm tra đó. `reports/dss_results.md:225-232,121-124`.

### 55. Số nào hay bị trích sai nhất?
"14 tuyến" (API `/routes` mặc định trả tối đa 10), tỷ lệ trễ **8,1556% theo đơn-tuyến** so với **8,1950% theo đơn duy nhất**, và GROSS so với NET của promise. Mô phỏng chỉ nói "nếu… thì ước tính". `reports/dss_eval_raw.txt`.

### 56. Tab nào là thật, tab nào mock?
Chỉ **DSS Action Center** gọi API Django thật; Dashboard, OLAP, ETL Monitor là mock tĩnh. Nói rõ trước khi thầy bấm. `web/Olist_Logistics_DSS_v3.html:427`; `reports/run_guide.md:93-96`.

### 57. Nếu thầy yêu cầu chạy lại ngay bây giờ?
Chạy `.\scripts\check.ps1`; nếu muốn bỏ qua tái tạo raw eval thì thêm `-Quick`. Check gần nhất có 78 pytest, 22 Django tests; `regen_eval` bị bỏ qua vì lần đó dùng `-Quick`. `reports/CHECK_OUTPUT.txt`.

### 58. Shapley attribution dùng benchmark peer nào?
Approval benchmark theo `payment_type`, prep theo `weight_band`, transit theo decile khoảng cách xuyên tuyến; kết quả Shapley là tỷ trọng trong tập đơn trễ. Fallback dùng median toàn cục của cùng giai đoạn khi peer thiếu mẫu/NA. `reports/dss_eval_raw.txt`, mục Attribution.

### 59. Vì sao q=0,75 không được báo cáo?
Ở q=0,75 benchmark chậm hơn actual, tạo phi âm và phân rã không hợp lệ; độ nhạy chỉ báo cáo q=0,25 và q=0,50. `reports/dss_eval_raw.txt`, mục Attribution.

### 60. S3 GROSS 3.751 và NET 2.867 khác nhau thế nào?
GROSS là số đơn-tuyến được phân loại lại là đúng hạn trước khi trừ 884 đơn trễ mới; NET là 2.867. Đây là đổi định nghĩa trễ, không rút ngắn thời gian giao. `reports/dss_eval_raw.txt`, mục Promise calibration.

### 61. CI hẹp của S4 có nghĩa là mức cắt khả thi không?
Không. CI của S4 phản ánh sampling noise quanh mô phỏng; CI hẹp không chứng minh tính khả thi vận hành hay nguồn lực để cắt thời gian. S4 dùng P25 làm mức cắt; P50 chỉ là tham chiếu. `reports/dss_eval_raw.txt`, mục S4.

### 62. Seller scorecard có chứng minh seller gây trễ không?
Không. Scorecard chỉ dùng đơn single-seller; khác biệt có thể do route mix và thành phần đơn. Đây là liên hệ, không phải quy kết nguyên nhân. Seller excess cũng khác tập/ý nghĩa với route-avoidable, không cộng hay so sánh. `reports/dss_eval_raw.txt`, mục Seller scorecard.

### 63. Sign test vs through nói gì, và vì sao vẫn “chưa đủ bằng chứng”?
Sign test có 12 dấu dương, 4 âm, n=16; p một phía 0,03841, hai phía 0,07681. Nó đếm hướng chênh lệch theo kỳ, không đo độ lớn; bootstrap CI vs through chứa 0, nên chưa đủ bằng chứng DSS tốt hơn through. Phép thử giả định các tháng độc lập, trong khi tháng liền kề có thể tương quan nên p-value có thể lạc quan. `reports/dss_eval_raw.txt`, mục Sign test (V4).

### 64. Bootstrap V2 lấy mẫu gì?
Lấy mẫu lại tuyến 500 lần với seed 42 ở q=0,50; CI là bất định lấy mẫu giữa tuyến của tỷ trọng nguyên nhân trong tổng tập đơn trễ, không đo độ nhạy benchmark theo q. Promise share khoảng 1–13% khi đổi q=0,25/0,50. Transit xếp #1 theo tuyến ở 165/226 tuyến có ít nhất một đơn trễ sau lọc stage âm; ở cấp hệ thống đứng đầu 500/500 lần bootstrap. `reports/dss_eval_raw.txt`, mục Bootstrap route-level (V2).

### 65. Bao nhiêu tuyến được gắn cờ ở cấu hình mặc định?
14 tuyến tại min_orders=100, red=2,0, amber=1,5; 6 đỏ và 8 vàng. MA→SP, PR→BA, SP→TO vẫn hiện “cần thêm dữ liệu” và không tính trùng vào ưu tiên chính. `reports/dss_eval_raw.txt`, mục S7/S8.

### 66. Vì sao có hai cách nhìn tuyến, và SP→SP đứng đầu đơn tránh được nhưng không nằm trong 14 tuyến gắn cờ?
`route_priority` xếp theo tỷ lệ trễ, còn Decision Brief xếp tác động theo số đơn trong mô phỏng P25. Vì vậy SP→SP có thể đứng đầu theo số đơn tránh ước tính mà không thuộc nhóm 14 tuyến có tỷ lệ trễ cao theo ngưỡng. Đây là hai câu hỏi khác nhau, không phải mâu thuẫn. `reports/dss_eval_raw.txt`, mục S4/S8.

### 67. Root Cause card có dùng peer benchmark theo khoảng cách không?
Không. Thẻ hiện so với trung bình toàn hệ thống, chưa chuẩn hoá theo khoảng cách; `/api/dss/attribution` có phân tích peer-based nhưng UI chưa nối endpoint đó. Cần trình bày rõ đây là hai khối khác nhau. `etl/dss_models.py::root_cause`; `backend/dss/views.py`; `web/Olist_Logistics_DSS_v3.html`.

### 68. Scenario có giả định thời gian cắt chuyển 1:1 sang ngày giao không?
Có, đây là giả định 1:1: nếu… thì ước tính ngày giao sớm hơn tương ứng, có chặn theo thời lượng từng chặng. Thực tế có thể có buffer hoặc lịch carrier, nên kết quả không phải phản thực nghiệm. `etl/dss_models.py::scenario`; `reports/dss_formulas.md`, mục 4.

### 69. Ai chịu trách nhiệm cho một route action?
Brief hiện ghép owner của ba giai đoạn thành danh sách; đó không phải một cá nhân/đơn vị duy nhất chịu trách nhiệm cho toàn tuyến. Cần phân công vận hành cụ thể trước khi dùng ngoài demo. `etl/dss_brief.py::_route_actions`; `reports/dss_eval_raw.txt`, mục Decision Brief.

### 70. Dashboard, OLAP và ETL Monitor có dùng dữ liệu thật không?
Không. Chỉ tab DSS nối API; Dashboard, OLAP và ETL Monitor vẫn là mock. Nên nói rõ trước khi trình diễn. `web/Olist_Logistics_DSS_v3.html`; `reports/run_guide.md`.

### 71. Nút “Ghi nhận khuyến nghị” có thực thi hành động không?
Không. Nút chỉ ghi bản ghi vào ActionLog; nó không thay đổi promise, tuyến, seller hay quy trình giao hàng. `backend/dss/views.py` (`/api/dss/actions`); `backend/dss/models.py::ActionLog`.

## G. Đóng góp nhóm — điền trước khi bảo vệ

> Phần này **CHƯA XÁC MINH** trong repo; mình không biết ai làm gì. Điền theo thực tế, mỗi người kèm 1 bằng chứng (commit/file).

| Thành viên | Phần phụ trách | Bằng chứng nên nêu |
|---|---|---|
| (điền) | DW/DDL + ETL | `sql/create_tables.sql`, `etl/*.py` |
| (điền) | DSS model + đánh giá | `etl/dss_models.py`, `etl/dss_eval.py` |
| (điền) | API + UI | `backend/dss/views.py`, `web/*.html` |
| (điền) | Báo cáo/slide | `reports/*.md` |

**Câu chốt an toàn:** "Phần em nắm chắc nhất là …; phần … do bạn … phụ trách, em có đọc nhưng không phải người viết chính."
