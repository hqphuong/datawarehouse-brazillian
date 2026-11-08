# CHEAT SHEET — Olist Logistics DSS

> Dùng khi bảo vệ. Các kết quả hiện hành lấy từ `reports/dss_eval_raw.txt` và
> `reports/CHECK_OUTPUT.txt`; không dùng số ở bản ghi cũ.

## 1. Câu chuyện 5 câu

1. Tỷ lệ trễ là **8,1556% theo đơn-tuyến** và **8,1950% theo đơn duy nhất**; hai mẫu số khác nhau.
2. Nhóm xây kho dữ liệu hình sao từ 9 bảng CSV gốc, grain **1 dòng = 1 item**, Fact là *accumulating snapshot* đo 3 chặng: duyệt, seller chuẩn bị, vận chuyển.
3. DSS có các khối route priority, attribution/Shapley, promise calibration, feasible cut, seller scorecard/portfolio, low-sample, threshold sensitivity và Decision Brief.
4. V4: **16/19 kỳ** nhóm gắn cờ cao hơn kỳ sau; weighted diff **+8,2826 pp**. Đây là tương quan hồi cứu.
5. Hệ thống là **mô phỏng theo luật**, không phải nhân quả và không dự báo bằng ML; simulation không phải counterfactual.

## 2. Mười con số đầu bảng

| # | Số | Ý nghĩa | Locator |
|---|---|---|---|
| 1 | **110.173** dòng item | input Fact của raw eval | `reports/dss_eval_raw.txt` |
| 2 | **96.981 → 95.591** đơn-tuyến | trước/sau lọc 1.390 thời gian âm | `reports/dss_eval_raw.txt`, mục Thời gian âm |
| 3 | **8,1556% / 8,1950%** | tỷ lệ trễ theo đơn-tuyến / đơn duy nhất (95.082 đơn) | `reports/dss_eval_raw.txt` |
| 4 | **100 / 2,0 / 1,5** | min_orders / red / amber mặc định | `reports/dss_eval_raw.txt`, mục S8 |
| 5 | **14 tuyến: 6 đỏ + 8 vàng** | cờ mặc định; không phải tổng ổn định qua mọi ngưỡng | `reports/dss_eval_raw.txt` |
| 6 | **9 endpoint DSS** | 4 endpoint cũ + brief, attribution, promise-policy, sellers, portfolio | `reports/api_dss.md` |
| 7 | **3.751 GROSS / 2.867 NET** | Promise calibration; có 884 đơn trễ mới | `reports/dss_eval_raw.txt`, mục S3 |
| 8 | q=0,50: transit **69,9162%** | tỷ trọng trong tập đơn trễ; V2 CI 95% [56,4003%; 83,5136%] | `reports/dss_eval_raw.txt` |
| 9 | **16/19**, weighted **+8,2826 pp** | backtest `min_orders=30` | `reports/dss_eval_raw.txt` |
| 10 | CI vs through **[−0,50; +2,52] pp** | chứa 0 → **chưa đủ bằng chứng** | `reports/dss_eval_raw.txt`, mục bootstrap |

**Schema:** 5 bảng DW, 5 CSV ETL, Fact `Fact_Delivery_SLA` có 21 cột theo DDL.
**Số phụ:** S3 có 130/1.157 ô đủ mẫu (83.104/95.591 đơn-tuyến); S4 top-10 là
2.878, còn S3 NET toàn bộ ô là 2.867 — khác tập nên không đối chiếu như cùng
một tổng. S8 tại min_orders=100 dao động 10–21 tuyến qua năm cặp ngưỡng; bộ
100/2,5/2,0 giữ lõi 6.
**Test:** **77 pytest / 22 Django**, regen eval pass (`reports/CHECK_OUTPUT.txt`).

## 3. Ba câu bắt buộc phải nói khi bảo vệ

1. **"Chưa đủ bằng chứng DSS tốt hơn through"** — CI chứa 0 (`reports/dss_eval_raw.txt`, mục bootstrap).
2. **"What-if là mô phỏng, không phải nhân quả"** — nếu giả định cắt thời gian thì ước tính lại nhãn trễ; bỏ qua chi phí/năng lực.
3. **"Chỉ tab DSS gọi API thật; Dashboard/OLAP/ETL là mock"** (`web/Olist_Logistics_DSS_v3.html:427`; `reports/run_guide.md:93-96`).

## 4. Những thứ **KHÔNG** được nói là đã có

Kết quả what-if là tác động thực tế · seller excess là đơn tránh được theo tuyến · "4 tab đều live" · AUC / time-split replay của ML · "nguyên nhân gốc là nhân quả".

## 5. Glossary (nói bằng lời của mình)

| Thuật ngữ | Nghĩa ngắn |
|---|---|
| **Grain** | Đơn vị nhỏ nhất của 1 dòng Fact: ở đây là **1 order item**. |
| **Star schema** | 1 bảng Fact ở giữa + 4 bảng Dim: Time, Location, Product, Seller. |
| **Accumulating snapshot** | Fact ghi các mốc thời gian của cùng một đơn (mua → duyệt → giao carrier → giao khách). |
| **Degenerate dimension** | Chiều không có bảng riêng, nằm ngay trong Fact: `payment_type`. |
| **Late rate** | Tỷ lệ đơn có `delay_days > 0` (giao sau ngày cam kết). |
| **Excess** | `mean(chặng của tuyến) − mean(chặng toàn hệ thống)`, đơn vị ngày. |
| **Wilson CI** | Khoảng tin cậy 95% cho tỷ lệ, không cho cận âm, ổn định khi `n` nhỏ. |
| **uncertain** | Wilson CI chứa ngưỡng phân loại → nhãn đỏ/vàng chưa được CI xác nhận. |
| **low_sample** | Tuyến có `< 200` đơn; chỉ cảnh báo, **không** đổi nhãn. |
| **Red-first** | Trả hết tuyến đỏ trước, rồi vàng cho đủ `top`; không che tuyến đỏ. |
| **Scenario / sensitivity** | Mô phỏng cắt `c` ngày ở một chặng / quét `c = 0..5`. |
| **Goal seek** | Tìm đầu vào nhỏ nhất đạt mục tiêu (kéo cam kết hoặc cắt ngày). |
| **Backtest** | Chạy mô hình trên kỳ `t`, đo tỷ lệ trễ nhóm gắn cờ ở kỳ `t+1`. |
| **Bootstrap CI** | Lấy mẫu lại có hoàn lại để ước lượng khoảng tin cậy; block 3 tháng xử lý tự tương quan. |

## 6. One-liner tự kiểm chứng (không cần server)

```powershell
@'
from etl import dss_models as M
o = M.load_orders()
print("order_route_rows", len(o), "unique_orders", o.order_id.nunique())
print("overall %.4f%%" % (o.is_late.mean()*100))
rp = M.route_priority(o, top=10)
print("all", len(M.route_priority(o, top=10**6)), "api", len(rp),
      "red", int((rp.level=="red").sum()))
print(M.goal_seek_promise(o, "SP->BA"), M.goal_seek_cut(o, "SP->BA", "transit"))
'@ | .\backend\env\Scripts\python.exe -
```

Kết quả lần kiểm tra hiện hành: pytest 77/77, Django 22/22, regen eval pass.
