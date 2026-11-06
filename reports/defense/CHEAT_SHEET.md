# CHEAT SHEET — Olist Logistics DSS

> Dùng khi bảo vệ. Mọi số dưới đây lấy từ lần chạy thật ngày **06/11/2026**.
> Quy tắc: gặp số lạ → mở `STATE.md` hoặc chạy one-liner ở cuối, **không đoán**.

## 1. Câu chuyện 5 câu

1. Olist giao trễ cam kết ở **8,07%** đơn; trễ không đều — một số tuyến `seller.state → customer.state` cao gấp 3 lần mức chung.
2. Nhóm xây kho dữ liệu hình sao từ 9 bảng CSV gốc, grain **1 dòng = 1 item**, Fact là *accumulating snapshot* đo 3 chặng: duyệt, seller chuẩn bị, vận chuyển.
3. Trên kho đó, DSS luật gồm 4 khối: **(1)** xếp hạng tuyến đỏ/vàng, **(2)** tìm chặng nghẽn, **(3)** mô phỏng what-if cắt ngày, **(4)** goal seek cam kết + ghi log hành động.
4. Kết quả được kiểm tra bằng **backtest một bước 19 kỳ** (16/19 kỳ tuyến gắn cờ trễ hơn, weighted **+8,14 pp**), bootstrap CI và độ nhạy ngưỡng.
5. Hệ thống là **mô phỏng theo luật**, không phải nhân quả và không dự báo bằng ML; điểm mạnh là giải thích được, điểm yếu là giả định cắt 1:1 và cỡ mẫu nhỏ ở vài tuyến.

## 2. Mười con số đầu bảng

| # | Số | Ý nghĩa | Locator |
|---|---|---|---|
| 1 | **99.441** đơn / **112.650** item gốc | dữ liệu nguồn | đếm raw; `etl/fact_delivery_sla.py:32-37` |
| 2 | **110.173** dòng Fact / **96.455** đơn | sau lọc `delivered` + dropna + inner join item | chạy thật; `etl/fact_delivery_sla.py:41,52,98` |
| 3 | **8,0727%** trễ (order-route) | tỷ lệ trễ chung | `STATE.md:15` |
| 4 | **16,1454%** đỏ / **12,1091%** vàng | ngưỡng = 2,0× và 1,5× mức chung | `STATE.md:15`; `reports/dss_formulas.md:58-64` |
| 5 | **14 tuyến** gắn cờ = **6 đỏ + 8 vàng** | toàn bộ tập gắn cờ | `STATE.md:17`; `reports/dss_results.md:253-266` |
| 6 | **10** | số dòng API `/routes` mặc định (`top=10`) | `backend/dss/views.py:60`; `dss_results.md:284` |
| 7 | **7/14** `uncertain`, **3/14** `low_sample` | cảnh báo thống kê / mẫu nhỏ | `STATE.md:17`; `dss_formulas.md:99` |
| 8 | **13/14** tuyến có `stage=transit` | chặng nghẽn theo excess | `reports/dss_results.md:247` |
| 9 | **16/19** kỳ, weighted **+8,14 pp** | backtest `min_orders=30` | `dss_results.md:47` |
| 10 | CI vs through **[−0,58; +2,35]** | **chứa 0 → không nói "vượt"** | `STATE.md:21`; `dss_results.md:208-216` |

**Số phụ đáng nhớ:** 3 chặng trung bình **0,43 / 2,79 / 9,32 ngày** (`dss_formulas.md:109`); tỷ lệ trễ theo grain: fact **7,9085%**, order **8,1126%**, order-route **8,0727%**; **519** đơn nhiều tuyến (tối đa 3), **408** tuyến; prep âm **1.542** dòng, transit âm **50** dòng; **11–30** tuyến khi đổi ngưỡng (`dss_results.md:225-232`).
**Goal seek:** SP→RJ **15** ngày, SP→BA **10**, SP→ES **9**; cut transit SP→BA **10**, SP→ES **9**, SP→RJ **None** (`STATE.md:21`; `dss_results.md:239-243`).
**Test:** **26 pytest / 16 Django** (`STATE.md:23`; `reports/dss_results.md:8,15`).

## 3. Ba câu bắt buộc phải nói khi bảo vệ

1. **"DSS không vượt baseline through có ý nghĩa thống kê"** — CI chứa 0 (`dss_results.md:208-216`). Chỉ được nói "cao hơn ~+0,8 pp theo điểm ước lượng".
2. **"What-if là mô phỏng, không phải nhân quả"** — giả định cắt 1 ngày lùi giao đúng 1 ngày, bỏ qua chi phí/năng lực (`dss_formulas.md:135-151`).
3. **"Chỉ tab DSS gọi API thật; Dashboard/OLAP/ETL là mock"** (`web/Olist_Logistics_DSS_v3.html:427`; `reports/run_guide.md:93-96`).

## 4. Những thứ **KHÔNG** được nói là đã có

Shapley / `dss_attrib` · benchmark theo decile khoảng cách / median · residual "promise too tight" · portfolio · seller scorecard · Decision Brief · AUC / time-split replay của ML · "4 tab đều live" · "nguyên nhân gốc là nhân quả" · "cắt transit giảm 2,09 pp trong thực tế".

## 5. Glossary (nói bằng lời của mình)

| Thuật ngữ | Nghĩa ngắn |
|---|---|
| **Grain** | Đơn vị nhỏ nhất của 1 dòng Fact: ở đây là **1 order item**. |
| **Star schema** | 1 bảng Fact ở giữa + các bảng Dim xung quanh; Dim_Time, Dim_Location, Dim_Product. |
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
print("rows", len(o), "orders", o.order_id.nunique())
print("overall %.4f%%" % (o.is_late.mean()*100))
rp = M.route_priority(o, top=10)
print("all", len(M.route_priority(o, top=10**6)), "api", len(rp),
      "red", int((rp.level=="red").sum()))
print(M.goal_seek_promise(o, "SP->BA"), M.goal_seek_cut(o, "SP->BA", "transit"))
'@ | .\backend\env\Scripts\python.exe -
```

Kỳ vọng: `rows 96981 orders 96455` · `overall 8.0727%` · `all 14 api 10 red 6` · `{'extra_days': 10, ...} 10.0`.
