# DEMO SCRIPT — 10 phút bảo vệ

> Mục tiêu: chứng minh **4 khối DSS chạy thật**, không sa vào chi tiết code.
> Nguyên tắc: mỗi phút có 1 hành động + 1 câu nói; không đọc số từ slide.

## 0. Checklist trước khi vào phòng (làm sớm 10 phút)

```powershell
# 1) Postgres đang chạy (cần cho tab Apply / log hành động)
Get-Service *postgres*

# 2) Server Django
.\backend\env\Scripts\python.exe backend\manage.py runserver 8000

# 3) API sống
Invoke-RestMethod "http://localhost:8000/api/dss/routes?top=10" | ConvertTo-Json -Depth 4

# 4) Mở UI
Start-Process "web\Olist_Logistics_DSS_v3.html"

# 5) Phòng xa: chạy test trước cho chắc
.\backend\env\Scripts\python.exe -m pytest -q
```

- [ ] Trình duyệt mở sẵn tab DSS, **đã bấm thử 1 tuyến** để chắc API trả dữ liệu.
- [ ] Tắt thông báo Windows/Telegram.
- [ ] Chuẩn bị **ảnh chụp + video 60s** trong `reports/defense/assets/` (nếu chưa có, tự chụp trước).
- [ ] Biết đường dẫn `CHEAT_SHEET.md` để mở khi bị hỏi số.

> **Rủi ro lớn:** UI tải React/Tailwind/Recharts từ **CDN** (`web/Olist_Logistics_DSS_v3.html:7-13`). Không có internet → trang trắng. Phải có phương án ảnh/video.

---

## 1. Timeline 10 phút

### 0:00–0:50 — Bài toán + 1 con số
**Nói:** "Olist giao trễ cam kết ở **8,07%** đơn. Trễ không rải đều: 14 tuyến vượt ngưỡng, tuyến xấu nhất **26,6%**. Nhóm em xây một DSS để trả lời 3 câu: tuyến nào cần xử lý, nghẽn ở đâu, và nếu can thiệp thì còn bao nhiêu trễ."
**Không nói:** "em dự báo đơn nào sẽ trễ" (không có ML).

### 0:50–2:00 — Kiến trúc 1 chiều
**Vẽ/vẽ tay:** `9 CSV → ETL → Star schema (Fact + 3 Dim) → DSS 4 khối → API Django → UI`.
**Nói:** "Fact grain 1 order item, 110.173 dòng, 96.455 đơn; DSS gộp lên 1 dòng/(order, route) = 96.981 dòng."
**Chỉ:** `sql/create_tables.sql:26-52`; `etl/fact_delivery_sla.py:54-58`.

### 2:00–3:10 — Kho dữ liệu & ETL (nếu thầy muốn)
**Chạy nhanh:**
```powershell
@'
import pandas as pd
f = pd.read_csv("data/processed/cleaned_fact_orders.csv")
print(len(f), f.order_id.nunique(), round((f.delay_days>0).mean()*100,4))
'@ | .\backend\env\Scripts\python.exe -
```
**Nói:** "110.173 dòng, 96.455 đơn, tỷ lệ trễ theo item 7,91%. Chỉ giữ đơn `delivered`, bỏ dòng thiếu mốc thời gian; 3 chặng tính từ 4 mốc."
**Chỉ:** `etl/fact_delivery_sla.py:41-58`.

### 3:10–5:00 — Khối 1: Route Priority (tab DSS)
**Click:** sidebar **DSS Action Center** → cột trái, bấm tuyến đỏ **SP→AL**.
**Nói:** "Tuyến đỏ = tỷ lệ trễ ≥ 2× mức chung; vàng ≥ 1,5×. Mặc định API trả 10 dòng nhưng **red-first**: nếu nhiều đỏ thì trả hết đỏ, không che."
**Chỉ trên màn hình:** `252 late of ... orders`, `[ci_low–ci_high]`, nhãn `ⓘ chưa chắc` / `⚠ mẫu nhỏ` nếu có.
**Câu chốt:** "Toàn bộ tập gắn cờ là **14 tuyến** (6 đỏ, 8 vàng); đây là 10 dòng hiển thị. `uncertain` 7/14, `low_sample` 3/14."

### 5:00–6:10 — Khối 2: Root cause
**Click:** cùng màn hình, nhìn card **2. Root Cause**.
**Nói:** "So trung bình từng chặng của tuyến với toàn hệ thống. SP→AL lệch transit **+12,5 ngày**, nên stage = transit."
**Tự nêu điểm yếu trước khi bị hỏi:** "Cách này gần như luôn chọn transit vì transit dài nhất — 13/14 tuyến. Bọn em biết và ghi rõ đây là chẩn đoán mô tả, không phải nhân quả."
**Chỉ:** `reports/dss_results.md:247`; `etl/dss_models.py:169-190`.

### 6:10–7:25 — Khối 3 + 4: Scenario & Promise
**Click:** kéo slider **Cut Transit** từ 0 → 1 → 5 ở card **3. Scenario**.
**Nói:** "Đây là mô phỏng: cắt 1 ngày transit thì tỷ lệ trễ dự báo giảm; càng về sau lợi ích biên càng nhỏ vì chỉ đơn sát ngưỡng mới lật."
**Click:** card **4. Recommendation & Action**, kéo **Target late rate** về 5%.
**Nói:** "Goal seek: SP→RJ cần kéo cam kết **15 ngày** để còn 4,66% trễ. Nhưng đây là kéo dài **cam kết**, không phải giao nhanh hơn; và cắt 10 ngày transit của SP→BA vượt excess thực tế nên không khả thi."
**Chỉ:** `reports/dss_results.md:317-318,239-243`.

### 7:25–8:05 — Hành động & log
**Click:** nút **Apply**.
**Nói:** "Hành động được ghi xuống DB thật (`dss_action_log`), GET trả 50 bản gần nhất — đây là phần duy nhất cần PostgreSQL."
**Chỉ:** toast + dòng log mới; `backend/dss/views.py:123-148`.

### 8:05–9:05 — Đánh giá: 1 phút
**Nói 3 câu, không mở bảng:**
1. "Backtest một bước: **16/19 kỳ** nhóm gắn cờ trễ hơn, weighted **+8,14 pp**."
2. "Nhưng so baseline `through` — cùng lượng thông tin — CI **chứa 0**, nên em **không** nói DSS vượt baseline."
3. "Đổi ngưỡng cho **11–30 tuyến**, nên '14' luôn nói kèm 100/2,0/1,5."
**Chỉ:** `reports/dss_results.md:47,208-216,225-232`.

### 9:05–10:00 — Hạn chế + kết
**Nói:** "Ba hạn chế: root cause tautology; what-if giả định cắt 1:1, bỏ qua chi phí; backtest 19 kỳ và 3 kỳ đảo chiều. Hướng tiếp theo là benchmark theo khoảng cách/P10 và thêm `seller_id` vào Fact — **hiện chưa làm**."
**Kết:** "Vì vậy em trình bày đây là **DSS luật, giải thích được, có kiểm chứng bước đầu**, không phải mô hình nhân quả hay dự báo."

---

## 2. Nếu demo lỗi — nói gì, làm gì

| Sự cố | Xử lý ngay | Câu nói |
|---|---|---|
| Trang trắng / mất style | Mất CDN → mở ảnh chụp | "UI load React từ CDN, phòng này chặn mạng; em có ảnh chụp luồng chạy." |
| `listError: Không tải được...` | Kiểm tra server: `Get-NetTCPConnection -LocalPort 8000`; chạy lại `runserver 8000` | "Django chưa lên, em khởi động lại 10 giây." |
| Port 8000 bận | `netstat -ano \| findstr :8000` → đổi `runserver 8001`, sửa `DSS_API` **không kịp** → dùng ảnh | "Có process khác giữ cổng, em dùng bản ghi hình." |
| Postgres tắt (Apply lỗi) | Bỏ qua Apply, chỉ GET 3 endpoint kia | "3 endpoint đọc CSV vẫn chạy; log hành động cần DB nên em xem log đã lưu." |
| API trả 400 | Đọc `error` trên UI, sửa tham số | "Thiếu `route`/`target` ngoài 0..1 — API validate và trả message." |
| Bị hỏi số không nhớ | Mở `CHEAT_SHEET.md` | "Em có bảng số kèm locator, thầy cho em tra 5 giây." |

**Câu cứu khi bí:** "Phần này em chưa xác minh trong repo, em không muốn đoán — em xin phép tra lại và trả lời sau."

---

## 3. Tuyệt đối tránh

- "Cả 4 tab đều nối API" → **sai**, chỉ DSS.
- "Shapley/benchmark/residual/portfolio/scorecard/Decision Brief" → **chưa có**.
- "AUC 0,66/0,77" → ML **đã gỡ**, số cũ.
- "Cắt transit giảm 2,09 pp" như tác động thật → chỉ là **mô phỏng**.
- "DSS vượt baseline through" → CI **chứa 0**.
- "Cắt 10 ngày là giải pháp" → vượt excess, chạm trần hàm.
- "Nguyên nhân gốc là transit do vận chuyển kém" → mới là **chênh lệch mô tả**.

---

## 4. Câu mở đầu & kết đã thuộc lòng

**Mở:** "Em xin trình bày 10 phút: 2 phút kiến trúc, 5 phút demo 4 khối, 2 phút đánh giá, 1 phút hạn chế."

**Kết:** "Tóm lại: kho dữ liệu hình sao tái lập được, DSS luật giải thích được, có backtest và CI; điều em **không** claim là nhân quả, dự báo ML, hay vượt baseline có ý nghĩa thống kê."
