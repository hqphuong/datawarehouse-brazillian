# DSS Evaluation Results (Bước 9 / Giai đoạn 5)

> **Snapshot hiện hành:** dùng các kết quả từ lần tái tạo trong
> `reports/dss_eval_raw.txt` và `reports/CHECK_OUTPUT.txt`. Các bảng chi tiết
> tại mục 2–8 dưới đây được lưu từ lần đánh giá trước; chỉ Snapshot hiện hành
> ở đầu tài liệu là căn cứ cho số liệu hiện tại.

## Snapshot hiện hành

- Dữ liệu: 110.173 dòng cấp item; 96.981 đơn-tuyến trước lọc; 95.591 sau khi
  loại 1.390 đơn-tuyến có thời gian âm. Tỷ lệ trễ là 8,1556% theo đơn-tuyến và
  8,1950% theo đơn duy nhất trên 95.082 đơn.
- Kiểm tra gần nhất trong `reports/CHECK_OUTPUT.txt`: pytest 78/78, Django `dss analytics` 22/22; `regen_eval` bị bỏ qua do `-Quick`, nên snapshot này không xác nhận raw eval vừa được tái tạo.
- V4: `min_orders=30`, 19 kỳ; `min_orders=100`, 13 kỳ đủ điều kiện. Exact sign
  test (không tính hòa): DSS so 0 là 16/3, n=19, p một phía 0,00221 và hai phía
  0,00443; so prior 12/5, n=17, p=0,07173/0,14346; so through 12/4, n=16,
  p=0,03841/0,07681. Đây là tương quan hồi cứu; sign test giả định các tháng
  độc lập, nhưng tháng liền kề có thể tương quan nên p-value có thể lạc quan.

| So sánh V4 | Dương/âm | n | p một phía | p hai phía |
|---|---:|---:|---:|---:|
| DSS so với 0 | 16/3 | 19 | 0,00221 | 0,00443 |
| DSS so với prior | 12/5 | 17 | 0,07173 | 0,14346 |
| DSS so với through | 12/4 | 16 | 0,03841 | 0,07681 |
- Backtest min_orders=30: weighted diff +8,2826 pp, mean diff +7,2403 pp,
  flagged-weighted diff +10,4624 pp.
- V2: route-level bootstrap 500 lần, seed 42, q=0,50. CI 95% tỷ trọng trong
  tập đơn trễ: approval 1,5799% [1,0753%; 1,9991%], prep 15,1638%
  [10,6215%; 19,1531%], transit 69,9162% [56,4003%; 83,5136%], promise
  13,3402% [4,4096%; 23,1705%]. CI đo nhiễu lấy mẫu giữa tuyến tại q=0,50,
  không đo độ nhạy benchmark theo q; promise ≈1–13% qua q=0,25/0,50.
  Transit đứng đầu ở 165/226 tuyến có ít nhất một đơn trễ sau lọc stage âm
  (thống kê theo tuyến, không phải tần suất bootstrap cấp hệ thống). Ở cấp hệ
  thống, transit đứng đầu 500/500 lần bootstrap. Share không âm theo định nghĩa;
  CI mô tả nhiễu lấy mẫu, không phải kiểm định khác 0.
- S8: tại min_orders=100, năm cặp ngưỡng quanh mặc định cho 10–21 tuyến; bộ
  100/2,5/2,0 giữ lõi 6 tuyến. Toàn lưới cho 4–30 tuyến.
- Decision Brief: các tổng là top-N, có thể chồng lấn và không phải tổng đơn
  tránh được. Route = top 5 P25; payment = top 5 payment_type, approval-only,
  low-impact; promise = top 5 ô theo NET; seller = top 5 excess. Ba nhóm mẫu
  nhỏ MA→SP, PR→BA, SP→TO nằm trong 14 tuyến gắn cờ nhưng hiển thị “cần thêm
  dữ liệu”, không tính trùng. Không cộng/so sánh seller excess với đơn tránh
  được theo tuyến.

### Attribution: peer benchmark, Shapley và q

Approval benchmark theo `payment_type`, prep theo `weight_band`, transit theo
decile khoảng cách xuyên tuyến. `cause_share_*` là tỷ trọng trong tập đơn trễ.

| q | Approval | Prep | Transit | Promise |
|---|---:|---:|---:|---:|
| 0,25 | 2,5291% | 20,0765% | 76,3297% | 1,0646% |
| 0,50 | 1,5777% | 15,1488% | 69,8820% | 13,3915% |

q=0,75 không dùng vì benchmark chậm hơn actual, tạo phi âm và phân rã không
hợp lệ. Bad-review 54,16% ở đơn trễ so với 9,44% đúng hạn là association trong
cùng dữ liệu, không phải nguyên nhân.

### Promise calibration

130/1.157 ô đủ mẫu (83.104/95.591 đơn-tuyến); GROSS 3.751, trừ 884 đơn trễ mới
còn NET 2.867. Bảng 85/90/95% là mức phục vụ, không phải khuyến nghị đặt
promise; nếu đặt promise bằng `needed_days` thì ước tính lại nhãn trễ, không
rút ngắn thời gian giao. `tight` phản ánh so sánh với Q95, không xác nhận tính
khả thi.

### Feasible cut và seller

S4 dùng P25 làm mức cắt; P50 chỉ là tham chiếu. Có 71/406 tuyến đủ mẫu. Tại
SP→SP, nếu cắt prep 1 ngày thì ước tính 423 đơn tránh được; tăng đến 1,89067
ngày thêm 173. Với transit, 1 ngày ước tính 480; tăng đến 2 ngày thêm 235.
Lợi ích biên thay đổi theo mức cắt; CI hẹp phản ánh sampling noise, không phải
tính khả thi.

Seller scorecard chỉ dùng đơn single-seller: 94.580/95.082 đơn, 2.948 seller,
609 seller đủ mẫu. k=102 bao phủ 3.902/7.788 đơn trễ (50,10%). Khác biệt
seller có thể bị confound bởi route mix; seller excess không phải số đơn tránh
được theo tuyến.

### Hạn chế

Backtest là tương quan hồi cứu; không có ROI hay đối chứng can thiệp.
Simulation không phải counterfactual. Mỗi đơn có một carrier date; Wilson CI
giả định đơn độc lập. Các tháng liền kề trong V4 có thể tương quan, làm p-value
sign test lạc quan. CI của S4 chỉ mô tả sampling noise, không chứng minh tính
khả thi vận hành.

- **Hai góc nhìn tuyến:** Route Priority xếp theo tỷ lệ trễ; Decision Brief xếp tác động theo số đơn trong mô phỏng P25. SP→SP đứng đầu nhóm đơn tránh ước tính nhưng không thuộc 14 tuyến gắn cờ theo tỷ lệ. Câu trả lời mẫu: “Hai khối trả lời hai câu hỏi khác nhau: tỷ lệ rủi ro và quy mô tác động ước tính.”
- **Root Cause:** đã chuyển sang hiển thị tỷ trọng trong đơn trễ theo peer cho tuyến đang chọn ở q=0,5, kèm q=0,25 để xem độ nhạy; yêu cầu tối thiểu 100 đơn-tuyến. Nguồn là card “2. Giai đoạn nghẽn” và `/api/dss/attribution`; số so với trung bình hệ thống còn trong phần thu gọn, vẫn chưa chuẩn hoá khoảng cách. Đây là phân rã theo quy tắc, không phải nhân quả.
- **Scenario 1:1:** mô hình giả định ngày tiết kiệm ở một chặng chuyển tương ứng thành ngày giao sớm hơn, có chặn theo thời lượng chặng. Câu trả lời mẫu: “Nếu… thì ước tính theo giả định 1:1; chưa mô hình hoá buffer hoặc lịch carrier.”
- **Owner của route action:** trường owner là danh sách ghép từ ba đơn vị theo ba giai đoạn, không phải một chủ thể duy nhất. Câu trả lời mẫu: “Đây là đầu mối theo từng chặng; cần phân công một người chịu trách nhiệm khi triển khai.”
- **Các tab mock:** ETL Monitor chưa nối dữ liệu/API thật. Câu trả lời mẫu: “DSS, Dashboard, OLAP và Analytics đều dùng API thật; ETL Monitor là mock.”
- **Nút ghi nhận:** “Ghi nhận khuyến nghị” chỉ tạo bản ghi ActionLog, không thực thi thao tác vận hành. Câu trả lời mẫu: “Nút ghi nhật ký để theo dõi, không đổi promise hay điều phối tuyến.”

## 1) Test results
**Pytest (repo root):**
```bash
.\backend\env\Scripts\python.exe -m pytest -q
```
Result gần nhất: **78 passed** (xác nhận trong `reports/CHECK_OUTPUT.txt`; check dùng `-Quick`).

**Django API tests (dss app):**
```bash
cd backend
..\backend\env\Scripts\python.exe manage.py test dss analytics
```
Result gần nhất: **22 tests OK** cho `dss analytics`.

## 2) Backtest (tuyến gắn cờ kỳ t vs tỷ lệ trễ kỳ t+1)
**Method:** For each period `t` (from 2017 onward, `min_period_orders=500`), `route_priority` is run on data of period `t` with selected `min_orders`. Routes flagged as red/amber are compared against others in period `t+1`. Periods with no flags or too few flagged orders are recorded but not counted in `periods_evaluated`.

**Trục so sánh chính của backtest là baseline `through`** (dùng lịch sử đến hết kỳ `t`, cùng lượng thông tin với DSS); baseline `prior` chỉ là đối chứng phụ.

**Tested `min_orders` ∈ {30, 50, 100}:**

### min_orders=30
| period | next_period | flagged_routes | flagged_orders | other_orders | total_orders | flagged_late_rate | other_late_rate | diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 201701 | 201702 | 1 | 44 | 1601 | 1645 | 0.0227273 | 0.0324797 | -0.00975243 |
| 201702 | 201703 | 2 | 102 | 2446 | 2548 | 0.196078 | 0.0498774 | 0.146201 |
| 201703 | 201704 | 1 | 64 | 2248 | 2312 | 0.15625 | 0.0760676 | 0.0801824 |
| 201704 | 201705 | 4 | 323 | 3238 | 3561 | 0.0402477 | 0.0355158 | 0.00473193 |
| 201705 | 201706 | 4 | 1101 | 2045 | 3146 | 0.0472298 | 0.0337408 | 0.013489 |
| 201706 | 201707 | 4 | 278 | 3611 | 3889 | 0.0791367 | 0.0307394 | 0.0483973 |
| 201707 | 201708 | 6 | 368 | 3851 | 4219 | 0.0461957 | 0.0316801 | 0.0145156 |
| 201708 | 201709 | 5 | 425 | 3740 | 4165 | 0.0352941 | 0.0534759 | -0.0181818 |
| 201709 | 201710 | 5 | 339 | 4166 | 4505 | 0.129794 | 0.0463274 | 0.0834661 |
| 201710 | 201711 | 5 | 1121 | 6213 | 7334 | 0.283675 | 0.116852 | 0.166824 |
| 201711 | 201712 | 6 | 812 | 4720 | 5532 | 0.236453 | 0.0572034 | 0.17925 |
| 201712 | 201801 | 5 | 939 | 6183 | 7122 | 0.13525 | 0.0545043 | 0.080746 |
| 201801 | 201802 | 9 | 1230 | 5339 | 6569 | 0.335772 | 0.119123 | 0.216649 |
| 201802 | 201803 | 9 | 1306 | 5730 | 7036 | 0.3951 | 0.171379 | 0.223721 |
| 201803 | 201804 | 9 | 1155 | 5691 | 6846 | 0.125541 | 0.0379547 | 0.0875865 |
| 201804 | 201805 | 7 | 480 | 6308 | 6788 | 0.183333 | 0.0741915 | 0.109142 |
| 201805 | 201806 | 8 | 955 | 5182 | 6137 | 0.0198953 | 0.0123504 | 0.00754484 |
| 201806 | 201807 | 4 | 351 | 5848 | 6199 | 0.0569801 | 0.0437756 | 0.0132044 |
| 201807 | 201808 | 3 | 165 | 6243 | 6408 | 0.0121212 | 0.105398 | -0.0932768 |

**Summary lần chạy trước:** các chi tiết theo kỳ dưới đây đã được thay bằng
snapshot hiện hành ở đầu tài liệu.

**Công thức `weighted_diff` (bắt buộc ghi rõ):**
Gọi `d_t = flagged_late_rate(t+1) - other_late_rate(t+1)`.

- **Số chính — `weighted_diff`:**  
  `Σ(d_t × total_orders(t+1)) / Σ total_orders(t+1)`, trong đó  
  `total_orders(t+1) = flagged_orders(t+1) + other_orders(t+1)`.  
  Số lần chạy hiện hành (`min_orders=30`): **+0.0828261158 = +8,2826 pp**.
- **Cách thay thế — `weighted_diff_flagged`:**  
  `Σ(d_t × flagged_orders(t+1)) / Σ flagged_orders(t+1)`, trọng số là số đơn của **nhóm gắn cờ** ở kỳ t+1.  
  Số lần chạy hiện hành (`min_orders=30`): **+0.1046239 = +10,4624 pp**.
- **`mean_diff` hiện hành:** **+0.0724026 = +7,2403 pp**.

| min_orders | mean_diff | weighted_diff (total_orders) | weighted_diff_flagged |
| --- | --- | --- | --- |
| 30 (hiện hành) | 0.0724026 | 0.0828261158 | 0.1046239 |
| 50, 100 | — | — | — |

**Vì sao chọn `weighted_diff` (total_orders) làm số chính:** mỗi kỳ là một đơn vị so sánh; trọng số theo toàn bộ đơn của kỳ t+1 phản ánh độ lớn mẫu của cả hai nhóm. `weighted_diff_flagged` trả lời câu hỏi khác nên báo cáo song song. Hai ước lượng hồi cứu không phải hiệu quả can thiệp.

### min_orders=50
| period | next_period | flagged_routes | flagged_orders | other_orders | total_orders | flagged_late_rate | other_late_rate | diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 201701 | 201702 | 0 | 0 | 1645 | 1645 | — | 0.0322188 | — |
| 201702 | 201703 | 0 | 0 | 2548 | 2548 | — | 0.05573 | — |
| 201703 | 201704 | 1 | 64 | 2248 | 2312 | 0.15625 | 0.0760676 | 0.0801824 |
| 201704 | 201705 | 2 | 179 | 3382 | 3561 | 0.0446927 | 0.035482 | 0.00921077 |
| 201705 | 201706 | 3 | 1074 | 2072 | 3146 | 0.0465549 | 0.0342664 | 0.0122885 |
| 201706 | 201707 | 2 | 168 | 3721 | 3889 | 0.0535714 | 0.0333244 | 0.0202471 |
| 201707 | 201708 | 5 | 344 | 3875 | 4219 | 0.0494186 | 0.0314839 | 0.0179347 |
| 201708 | 201709 | 4 | 376 | 3789 | 4165 | 0.0345745 | 0.0533122 | -0.0187378 |
| 201709 | 201710 | 3 | 273 | 4232 | 4505 | 0.0989011 | 0.0496219 | 0.0492792 |
| 201710 | 201711 | 4 | 1073 | 6261 | 7334 | 0.287978 | 0.117393 | 0.170584 |
| 201711 | 201712 | 5 | 779 | 4753 | 5532 | 0.240051 | 0.0578582 | 0.182193 |
| 201712 | 201801 | 3 | 811 | 6311 | 7122 | 0.134402 | 0.056251 | 0.078151 |
| 201801 | 201802 | 7 | 1186 | 5383 | 6569 | 0.342327 | 0.11945 | 0.222877 |
| 201802 | 201803 | 6 | 1207 | 5829 | 7036 | 0.388567 | 0.176531 | 0.212036 |
| 201803 | 201804 | 6 | 1057 | 5789 | 6846 | 0.12772 | 0.0390396 | 0.0886804 |
| 201804 | 201805 | 4 | 399 | 6389 | 6788 | 0.185464 | 0.0754422 | 0.110021 |
| 201805 | 201806 | 6 | 880 | 5257 | 6137 | 0.0215909 | 0.0121742 | 0.00941667 |
| 201806 | 201807 | 3 | 315 | 5884 | 6199 | 0.0634921 | 0.0435078 | 0.0199842 |
| 201807 | 201808 | 2 | 133 | 6275 | 6408 | 0.0150376 | 0.104861 | -0.089823 |

**Summary:** `periods_considered=19, periods_evaluated=17, periods_without_flags=2 (201701, 201702), higher_periods=15/17 (0.882), weighted_diff=0.07940, mean_diff=0.06909`

### min_orders=100
| period | next_period | flagged_routes | flagged_orders | other_orders | total_orders | flagged_late_rate | other_late_rate | diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 201701 | 201702 | 0 | 0 | 1645 | 1645 | — | 0.0322188 | — |
| 201702 | 201703 | 0 | 0 | 2548 | 2548 | — | 0.05573 | — |
| 201703 | 201704 | 0 | 0 | 2312 | 2312 | — | 0.0782872 | — |
| 201704 | 201705 | 0 | 0 | 3561 | 3561 | — | 0.035945 | — |
| 201705 | 201706 | 1 | 958 | 2188 | 3146 | 0.045929 | 0.035192 | 0.0107371 |
| 201706 | 201707 | 0 | 0 | 3889 | 3889 | — | 0.034199 | — |
| 201707 | 201708 | 1 | 100 | 4119 | 4219 | 0.04 | 0.0327749 | 0.00722505 |
| 201708 | 201709 | 1 | 180 | 3985 | 4165 | 0.0277778 | 0.0526976 | -0.0249198 |
| 201709 | 201710 | 2 | 213 | 4292 | 4505 | 0.103286 | 0.0500932 | 0.0531932 |
| 201710 | 201711 | 2 | 880 | 6454 | 7334 | 0.314773 | 0.118841 | 0.195932 |
| 201711 | 201712 | 3 | 669 | 4863 | 5532 | 0.255605 | 0.0598396 | 0.195766 |
| 201712 | 201801 | 2 | 736 | 6386 | 7122 | 0.133152 | 0.0573129 | 0.0758393 |
| 201801 | 201802 | 4 | 933 | 5636 | 6569 | 0.339764 | 0.129879 | 0.209885 |
| 201802 | 201803 | 5 | 1131 | 5905 | 7036 | 0.376658 | 0.181541 | 0.195117 |
| 201803 | 201804 | 3 | 830 | 6016 | 6846 | 0.120482 | 0.0433843 | 0.0770976 |
| 201804 | 201805 | 2 | 278 | 6510 | 6788 | 0.201439 | 0.0768049 | 0.124634 |
| 201805 | 201806 | 3 | 673 | 5464 | 6137 | 0.02526 | 0.0120791 | 0.013181 |
| 201806 | 201807 | 1 | 167 | 6032 | 6199 | 0.0598802 | 0.0440981 | 0.0157821 |
| 201807 | 201808 | 0 | 0 | 6408 | 6408 | — | 0.102996 | — |

**Summary:** `periods_considered=19, periods_evaluated=13, periods_without_flags=6, higher_periods=12/13 (0.923), weighted_diff=0.10006, mean_diff=0.08842`

**Selection for the backtest: `min_orders=30`.** In the current raw eval,
`min_orders=100` gives 13 eligible periods; `min_orders=30` gives 19, with the
flagged group higher in 16/19. The current weighted difference is +8,2826 pp.
The production default remains 100; the lower threshold is for retrospective
period-by-period evaluation.

**Where the backtest does NOT support the flag (reported explicitly):**
- `201701 -> 201702`: flagged group 2.27% vs rest 3.25% (`diff = -0.00975`, -0.98 pp).
- `201708 -> 201709`: flagged group 3.53% vs rest 5.35% (`diff = -0.01818`, -1.82 pp).
- `201807 -> 201808`: flagged group 1.21% vs rest 10.54% (`diff = -0.09328`, -9.33 pp). This last period is the clearest counterexample: the flagged group is small (165 orders) and next-month rates are volatile, so the one-step signal fails there. Overall 16/19 periods support the flag, but this is a monthly association, not a guarantee for every month.

### Baseline lịch sử — đối chứng phụ (prior)
**Cách làm baseline:** với mỗi kỳ `t`, tính tỷ lệ trễ gộp của từng tuyến trên **toàn bộ các kỳ trước `t`**; chỉ xét tuyến có ít nhất `min_orders` đơn trong kỳ `t` và có ít nhất một dòng lịch sử; xếp hạng theo tỷ lệ trễ lịch sử, phá hòa theo số đơn lịch sử rồi tên tuyến; chọn đúng **K tuyến** như DSS đã gắn cờ ở kỳ `t`. Sau đó so tỷ lệ trễ ở kỳ `t+1` giống hệt cách đánh giá DSS.

| period | dss_diff | baseline_diff |
| --- | --- | --- |
| 201701 | -0.00975243 | -0.00975243 |
| 201702 | 0.146201 | -0.015126 |
| 201703 | 0.0801824 | 0.0826964 |
| 201704 | 0.00473193 | 0.0125922 |
| 201705 | 0.013489 | -0.00433873 |
| 201706 | 0.0483973 | 0.000311621 |
| 201707 | 0.0145156 | -0.014294 |
| 201708 | -0.0181818 | 0.0667443 |
| 201709 | 0.0834661 | 0.037871 |
| 201710 | 0.166824 | 0.0322649 |
| 201711 | 0.17925 | 0.0263887 |
| 201712 | 0.080746 | 0.0736042 |
| 201801 | 0.216649 | 0.216696 |
| 201802 | 0.223721 | 0.230465 |
| 201803 | 0.0875865 | 0.0753414 |
| 201804 | 0.109142 | 0.0545356 |
| 201805 | 0.00754484 | 0.0108234 |
| 201806 | 0.0132044 | -0.00599853 |
| 201807 | -0.0932768 | -0.0714562 |

**Kết quả baseline (`min_orders=30`, hiện hành; chi tiết theo kỳ cũ ở trên không đồng bộ):**
- prior: 13/19 kỳ có nhóm gắn cờ trễ hơn; weighted diff **+5,23 pp**, mean
  **+4,22 pp**, flagged-weighted **+6,46 pp**.
- through: 14/19 kỳ; weighted diff **+7,37 pp**, mean **+5,93 pp**,
  flagged-weighted **+9,68 pp**.
- DSS: 16/19 kỳ; weighted diff **+8,28 pp**, mean **+7,24 pp**,
  flagged-weighted **+10,46 pp**.

**Kết luận hiện hành:** cặp từng kỳ DSS-vs-prior là 12 kỳ DSS cao hơn, 5 kỳ prior
cao hơn và 2 hòa; DSS-vs-through là 12/4/3. Điểm ước lượng cao hơn không đủ để
khẳng định DSS tốt hơn mọi baseline ở mọi kỳ.

**Lưu ý các kỳ gần như hòa:** trong danh sách baseline "prior" tốt hơn DSS, hai kỳ `201801` và `201805` chênh lệch rất nhỏ, gần như hòa:
- `201801`: baseline `0.216696` vs DSS `0.216649` — lệch **~0.005 điểm %**.
- `201805`: baseline `0.010823` (1.08%) vs DSS `0.007545` (0.75%) — lệch **~0.33 điểm %**.
Các kỳ còn lại baseline tốt hơn rõ hơn: `201703`, `201704`, `201708`, `201802`, `201807`.

### Baseline lịch sử — so sánh chính (through)
Ngoài biến thể "prior" (chỉ các kỳ **trước** `t`), báo cáo thêm biến thể "through": xếp hạng tuyến theo tỷ lệ trễ gộp của lịch sử **đến hết kỳ `t`** (gồm cả kỳ `t`, tức cùng lượng thông tin DSS nhìn thấy). Cách chọn K tuyến, điều kiện `min_orders` trong kỳ `t`, cách phá hòa và cách đánh giá ở kỳ `t+1` giữ nguyên.

**Bảng từng kỳ (through):**

| period | dss_diff | baseline_through_diff |
| --- | --- | --- |
| 201701 | -0.009752 | -0.009752 |
| 201702 | 0.146201 | -0.022295 |
| 201703 | 0.080182 | 0.080182 |
| 201704 | 0.004732 | 0.004732 |
| 201705 | 0.013489 | -0.004339 |
| 201706 | 0.048397 | 0.012381 |
| 201707 | 0.014516 | 0.005754 |
| 201708 | -0.018182 | 0.061628 |
| 201709 | 0.083466 | 0.077632 |
| 201710 | 0.166824 | 0.163537 |
| 201711 | 0.179250 | 0.164539 |
| 201712 | 0.080746 | 0.073604 |
| 201801 | 0.216649 | 0.216696 |
| 201802 | 0.223721 | 0.240231 |
| 201803 | 0.087586 | 0.080302 |
| 201804 | 0.109142 | 0.055259 |
| 201805 | 0.007545 | 0.010823 |
| 201806 | 0.013204 | -0.005999 |
| 201807 | -0.093277 | -0.071456 |

| Biến thể baseline | Cờ trễ hơn nhóm còn lại | mean_diff | weighted (tổng đơn t+1) | weighted (đơn nhóm cờ) | DSS tốt hơn | Baseline tốt hơn | Hòa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **prior** (chỉ kỳ trước `t`) | 13/19 | +4.22 pp | +5.23 pp | +6.46 pp | 12 | 5 | 2 |
| **through** (đến hết kỳ `t`) | 14/19 | **+5.93 pp** | **+7.37 pp** | **+9.68 pp** | **12** | **4** | **3** |
| DSS (tham chiếu) | 16/19 | +7.24 pp | +8.28 pp | +10.46 pp | — | — | — |

**Kết luận hiện hành cho biến thể "through":** điểm ước lượng của DSS cao hơn,
nhưng CI pair và block đều chứa 0; đây là **chưa đủ bằng chứng** DSS tốt hơn
through. Sign test kiểm tra hướng chênh lệch theo kỳ, không phải độ lớn hay hiệu
quả nhân quả. Through là so sánh chính vì dùng thông tin đến hết kỳ `t`.

### Bootstrap CI (n_boot=10 000, seed=42, trọng số=total_orders)

Khoảng tin cậy bootstrap 95% (đơn vị: điểm phần trăm, pp) cho `weighted_diff` và các so sánh baseline. **So sánh chính là "vs through"** (baseline through cùng lượng thông tin với DSS).

Hai loại bootstrap:
- **Pair bootstrap**: lấy mẫu có hoàn lại theo kỳ (đơn vị = một kỳ).
- **Block bootstrap** (khối 3 tháng, circular): tính đến tự tương quan giữa các kỳ gần nhau.

| Loại bootstrap | vs 0 (DSS > 0) | vs prior | vs through *(so sánh chính)* |
| --- | --- | --- | --- |
| Pair (resample kỳ) | [+3,77; +12,55] pp | [+0,52; +5,92] pp | [−0,50; +2,52] pp |
| Block (khối 3 tháng, circular) | [+2,08; +13,46] pp | [+0,69; +6,29] pp | [−0,30; +2,35] pp |

**Đọc CI:**
- Nếu CI chứa 0, kết luận là **chưa đủ bằng chứng** về chênh lệch.
- **vs through:** pair CI hiện hành `[−0.50; +2.52]` và block CI `[−0.30; +2.35]` chứa 0; chưa đủ bằng chứng DSS tốt hơn through.

**Quy tắc báo cáo:** với CI chứa 0, dùng “chưa đủ bằng chứng”; không diễn giải thành DSS vượt baseline.

**Cảnh báo 19 kỳ:** chỉ có 19 kỳ nên CI chỉ mang tính tham khảo; circular block nối kỳ cuối với kỳ đầu.

## 3) Threshold sensitivity (full year data)
| min_orders | red | amber | flagged_routes | red_routes | amber_routes |
| --- | --- | --- | --- | --- | --- |
| 50 | 2.0 | 1.5 | 21 | 7 | 14 |
| 50 | 2.5 | 1.5 | 21 | 4 | 17 |
| 100 | 2.0 | 1.5 | 14 | 6 | 8 |
| 100 | 2.5 | 2.0 | 6 | 3 | 3 |

## 4) Top 3 routes (including SP->RJ)
Bảng này dùng chế độ chi tiết `ensure_red=False` (xếp thuần theo `late_orders`, đúng 3 dòng) để giữ top 3 lịch sử. Danh sách cảnh báo mặc định của `route_priority`/API dùng red-first: trả **tất cả tuyến đỏ trước** (sắp `late_orders` giảm dần), rồi vàng cho đủ `top`.

| route | orders | late_orders | late_rate | level | stage | has_bottleneck | excess_approval | approval_cut_1 | approval_cut_3 | approval_cut_5 | approval_goal_cut | excess_prep | prep_cut_1 | prep_cut_3 | prep_cut_5 | prep_goal_cut | excess_transit | transit_cut_1 | transit_cut_3 | transit_cut_5 | transit_goal_cut | promise_days | promise_late_after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP->RJ | 8108 | 1263 | 0.155772 | amber | transit | True | -0.036530 | 0.152195 | 0.151332 | 0.151332 | — | 0.212570 | 0.143809 | 0.134558 | 0.129872 | — | 3.602831 | 0.141959 | 0.123335 | 0.108781 | — | 15 | 0.046621 |
| SP->BA | 2295 | 344 | 0.149891 | amber | transit | True | 0.064032 | 0.144227 | 0.143355 | 0.142484 | — | 0.017264 | 0.132898 | 0.118954 | 0.113290 | — | 7.203369 | 0.128976 | 0.105447 | 0.086275 | 10 | 10 | 0.047059 |
| SP->ES | 1459 | 206 | 0.141193 | amber | transit | True | 0.021526 | 0.137080 | 0.135024 | 0.135024 | — | 0.091133 | 0.126114 | 0.111720 | 0.108293 | — | 3.114419 | 0.122687 | 0.097327 | 0.078821 | 9 | 9 | 0.044551 |

**Notes:** `goal_seek_cut` returns `None` if target not reached within `max_days=10` (step 0.5). Trong 3 tuyến top, chỉ SP->RJ không đạt 5% ở cả approval/prep/transit với mức cắt ≤10 ngày; SP->BA đạt ở 10 ngày, SP->ES đạt ở 9 ngày. `goal_seek_promise` khớp kiểm tra trước đó.

**Ghi chú cột `late_rate`:** đây là `late_orders / orders` của chính tuyến (ví dụ SP->RJ: 1263/8108 = 0,155772), **không phải** baseline lịch sử hay baseline hệ thống.

**Cột `excess_ratio_<stage>` (tham khảo):** excess tuyệt đối chuẩn hóa theo `|mean_sys|` của từng giai đoạn. Với mean hệ thống: approval ≈ 0,43 ngày, prep ≈ 2,79 ngày, transit ≈ 9,32 ngày. Với 14 tuyến gắn cờ (bảng 4b), **0/14 tuyến có `stage` khác nhau giữa excess tuyệt đối và excess_ratio**: transit dẫn đầu ở 13/14, còn MA->SP là prep ở cả hai cách. `excess_transit` thực tế nằm trong **1,43–12,54 ngày**. `SP->TO` và `PR->BA` là hai tuyến sát nhất. `stage` và `has_bottleneck` trong DSS vẫn xác định theo excess tuyệt đối.

### 4b) Bảng 14 tuyến gắn cờ và đối chiếu excess_ratio (dữ liệu chạy thực tế)

| route | orders | late_rate | level | uncertain | stage | stage_ratio | excess_ratio_approval | excess_ratio_prep | excess_ratio_transit | stage_ratio_diff |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP->RJ | 8108 | 0.155772 | amber | False | transit | transit | -0.085257 | 0.076098 | 0.386731 | False |
| SP->BA | 2295 | 0.149891 | amber | False | transit | transit | 0.149446 | 0.006180 | 0.773215 | False |
| SP->ES | 1459 | 0.141193 | amber | False | transit | transit | 0.050241 | 0.032625 | 0.334304 | False |
| SP->CE | 960 | 0.153125 | amber | False | transit | transit | 0.080156 | 0.022212 | 0.925852 | False |
| PR->RJ | 994 | 0.135815 | amber | True | transit | transit | -0.150790 | 0.117551 | 0.466981 | False |
| SP->MA | 490 | 0.214286 | red | False | transit | transit | 0.256042 | 0.060059 | 0.994681 | False |
| SP->PA | 679 | 0.129602 | amber | True | transit | transit | 0.210558 | 0.028633 | 1.137656 | False |
| SP->MS | 476 | 0.147059 | amber | True | transit | transit | 0.061916 | -0.013493 | 0.369004 | False |
| SP->AL | 252 | 0.265873 | red | False | transit | transit | 0.253804 | -0.024793 | 1.346363 | False |
| SP->PI | 328 | 0.182927 | red | True | transit | transit | -0.026525 | 0.063883 | 0.818214 | False |
| SP->SE | 207 | 0.164251 | red | True | transit | transit | 0.065008 | 0.105685 | 0.909007 | False |
| MA->SP | 124 | 0.250000 | red | False | prep | prep | 0.053883 | 0.751767 | 0.153713 | False |
| SP->TO | 198 | 0.126263 | amber | True | transit | transit | 0.383015 | 0.029653 | 0.532953 | False |
| PR->BA | 145 | 0.165517 | red | True | transit | transit | 0.328144 | 0.268178 | 0.909366 | False |

Trong 14 tuyến, **7/14 có `uncertain=True`**: SP->PI, SP->SE, PR->BA, PR->RJ, SP->PA, SP->MS, SP->TO. Cờ này không đổi `level`, thứ tự, `stage` hay `has_bottleneck`.

**Vì sao `transit_goal_cut` của SP->BA (10) và SP->ES (9) trùng `promise_days`?** Không phải lỗi cột. `goal_seek_cut` tìm `x` nhỏ nhất trên lưới 0,5 sao cho `scenario` ≤ 5%; `goal_seek_promise` lấy `ceil(quantile(0,95))`. Với SP->BA, cả hai cho 10 và projected trùng `promise_late_after` (0,047059). Với SP->ES, cả hai cho 9 nhưng projected là 0,045922, khác `promise_late_after` 0,044551 vì `scenario` chặn mức cắt bởi transit thực tế của từng đơn. Trùng số là do cùng ngưỡng đuôi, không phải copy nhầm.

### 4a) Wilson 95% và cờ mẫu nhỏ cho 6 tuyến đỏ
`route_priority`/`/api/dss/routes` trả thêm `ci_low`, `ci_high` (Wilson 95%) và `low_sample` (`orders < 200`); **không đổi nhãn đỏ/vàng và ngưỡng**. Wilson giả định đơn độc lập và không hiệu chỉnh clustering, nên CI có thể hẹp hơn bất định thực tế. UI hiển thị dạng `late_rate [ci_low–ci_high]` kèm cảnh báo mẫu nhỏ.

| route | orders | late_orders | late_rate | ci_low | ci_high | low_sample |
| --- | --- | --- | --- | --- | --- | --- |
| SP->AL | 252 | 67 | 26.5873% | 21.5138% | 32.3639% | False |
| MA->SP | 124 | 31 | 25.0000% | 18.2075% | 33.2949% | True |
| SP->MA | 490 | 105 | 21.4286% | 18.0250% | 25.2767% | False |
| SP->PI | 328 | 60 | 18.2927% | 14.4839% | 22.8356% | False |
| PR->BA | 145 | 24 | 16.5517% | 11.3822% | 23.4478% | True |
| SP->SE | 207 | 34 | 16.4251% | 11.9984% | 22.0753% | False |

Top mặc định 10 dòng hiện chứa đủ **6 tuyến đỏ** (SP->MA, SP->AL, SP->PI, SP->SE, MA->SP, PR->BA), sau đó 4 tuyến vàng; không còn che `SP->SE`, `MA->SP`, `PR->BA`.

## 5) Impact of negative times (detailed table from previous run)
**Current raw-eval counts are at đơn-tuyến grain:** 1.361 prep-negative,
29 transit-negative, 1.390 with either negative; all 1.390 were removed from
the DSS sample. Fact-level totals were not emitted in the current raw eval.

**Current model-level count (1 row = đơn-tuyến):** 1.390 removed from 96.981
before filtering; 95.591 remain.

**Comparison for top 3 routes (clean = drop rows where `prep>=0 and transit>=0`; system means also change):**
| route | removed_rows | orders_keep | orders_drop | baseline_keep | baseline_drop | stage_keep | stage_drop | has_bottleneck_keep | has_bottleneck_drop | excess_approval_keep | excess_approval_drop | excess_prep_keep | excess_prep_drop | excess_transit_keep | excess_transit_drop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP->RJ | 92 | 8108 | 8016 | 0.155772 | 0.157061 | transit | transit | True | True | -0.036530 | -0.031929 | 0.212570 | 0.204748 | 3.602831 | 3.619521 |
| SP->BA | 28 | 2295 | 2267 | 0.149891 | 0.149978 | transit | transit | True | True | 0.064032 | 0.064307 | 0.017264 | 0.013544 | 7.203369 | 7.169286 |
| SP->ES | 16 | 1459 | 1443 | 0.141193 | 0.142065 | transit | transit | True | True | 0.021526 | 0.026753 | 0.091133 | 0.084861 | 3.114419 | 3.102322 |

**Conclusion:** Removing negative-time rows changes magnitudes of excess slightly but **does not change bottleneck identification** (all three remain transit bottleneck) in this dataset. The values look plausible as data quality artifacts (small fraction of rows). The model as written treats stage times as given; filtering is a data-cleaning choice but the core diagnosis holds.

## 6) Parameters chosen and rationale
- **route_priority production defaults kept:** `red=2.0, amber=1.5, min_orders=100, top=10`, với `ensure_red=True` (red-first) để không che tuyến đỏ.
- **Backtest min_orders = 30:** dùng riêng cho đánh giá theo kỳ. Với 100, chỉ
  13 kỳ đủ điều kiện; với 30 có 19 kỳ, trong đó 16 kỳ nhóm gắn cờ cao hơn.
  Weighted diff hiện hành là +8,2826 pp. Đây là tương quan hồi cứu.
- **Backtest window:** start from 2017 (drop 2016 sparse months), require `min_period_orders>=500` in t and t+1, use next calendar month.
- **Baseline lịch sử (đối chứng):** through là so sánh chính, prior là đối chứng phụ. Số hiện hành ở Snapshot đầu tài liệu thay thế các thống kê baseline cũ trong bảng chi tiết.
- **Top routes:** bảng chi tiết top 3 (`ensure_red=False`) vẫn là SP->RJ/BA/ES, đều có bottleneck transit. Danh sách cảnh báo mặc định (`route_priority()` top 10) trả đủ 6 tuyến đỏ trước rồi 4 tuyến vàng, không còn che `SP->SE`, `MA->SP`, `PR->BA`.

## 7) Limitations observed
- **Early months sparse:** 2016 has tiny counts; several periods have 0 flagged routes when using stricter `min_orders` (e.g. 201701-201704 at 100). Backtest explicitly excludes/marks these.
- **Monthly granularity limits sample size:** even with `min_orders=30` we get small flagged sets in some months.
- **Thời gian giai đoạn âm:** 1.390 đơn-tuyến bị loại (prep âm 1.361,
  transit âm 29).
- **`goal_seek_cut` chỉ đạt 5% ở mức trần 10 ngày với SP->BA:** bảng top 3 cho thấy SP->BA đạt 4,71% khi cắt transit đúng 10 ngày (`max_days=10`), còn SP->ES đạt ở 9 ngày. Vì vậy không nên nói "cắt giai đoạn không đủ" tuyệt đối; đúng hơn là "chỉ đủ ở biên 10 ngày, cần kiểm chứng thêm vì đây là giới hạn của hàm".
- **`transit_goal_cut` ≈ `promise_days` là hệ quả của giả định 1:1.** `goal_seek_cut` tìm `c` sao cho `scenario(cut=c)["projected"] ≤ 5%`; `goal_seek_promise` tìm `x` sao cho `P(delay_days > x) ≤ 5%`. Dưới giả định cắt 1:1 (`delay_days_new = delay_days - min(c, transit)`), cắt `c` ngày transit tương đương kéo dài cam kết `c` ngày — trừ phần chặn bởi thời gian transit thực tế của từng đơn (khi `c > transit_i`, chỉ cắt được đúng `transit_i` ngày). Đây là lý do `transit_goal_cut` (SP->BA=10) gần trùng `promise_days` (SP->BA=10). **Hệ quả quan trọng:** cắt 10 ngày transit của SP->BA vượt quá mức trung bình excess transit của tuyến (7,2 ngày), tức là yêu cầu cắt **nhiều hơn tổng excess** — không nên trình bày như phương án khả thi trong thực tế. `goal_seek_cut(SP->BA, "transit") = 10` là **mức cắt tối thiểu theo giả định 1:1, trùng biên `max_days=10`**, không phải phương án can thiệp cụ thể. SP->ES cắt 9 ngày — gần biên nhưng chưa chạm, và vẫn vượt xa excess transit ~3,1 ngày. Nếu muốn đạt 5% thực sự với SP->BA, cần kết hợp cắt nhiều giai đoạn hoặc dùng `goal_seek_promise`.
- **Baseline lịch sử chỉ là đối chứng đơn giản:** bảng baseline chi tiết lưu kết quả lần chạy trước; dùng các số prior/through trong Snapshot hiện hành.
- **Bootstrap CI vs through chứa 0:** Pair CI `[−0.50; +2.52]` và Block CI
  `[−0.30; +2.35]` đều chứa 0 — chưa đủ bằng chứng DSS tốt hơn through.
- **Model is descriptive/what-if:** Backtest shows flagged routes tend to have higher late rate in next period (supportive in most evaluated periods) but is not a causal proof.

## 8) Reproduction

The current user-run check is `.\scripts\check.ps1`; add `-Quick` to skip
raw-eval regeneration. See `reports/run_guide.md`. The old commands and file
list from Giai đoạn 5 have been retired; they are not a record of the Phase 1/2
changes.
No Django/giao diện files modified.
