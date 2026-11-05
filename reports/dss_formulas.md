# Công thức và giả định mô hình DSS

Nguồn: `etl/dss_models.py`, `etl/dss_eval.py`.  
Dữ liệu đầu vào: `data/processed/cleaned_fact_orders.csv` (~110 173 dòng ở cấp item; sau `load_orders()` gộp thành ~96 981 dòng ở cấp (đơn hàng, tuyến)).

---

## 0. Ký hiệu chung

| Ký hiệu | Ý nghĩa |
| --- | --- |
| $O$ | Toàn bộ tập dữ liệu (đơn hàng, tuyến) |
| $O_r$ | Tập con đơn hàng của tuyến $r$ |
| $N = \|O\|$ | Tổng số cặp (đơn, tuyến) |
| $N_r = \|O_r\|$ | Số đơn trên tuyến $r$ |
| $d_i$ | `delay_days` của đơn $i$ = ngày giao thực tế − ngày cam kết |
| $\mathbb{1}[d_i > 0]$ | 1 nếu đơn $i$ trễ, 0 nếu không |
| $a_i, p_i, t_i$ | `approval_time_days`, `seller_prep_time_days`, `carrier_transit_time_days` của đơn $i$ |

---

## 1. Tải và chuẩn bị dữ liệu — `load_orders()`

Fact có hạt ở cấp **item** (một đơn có thể nhiều item từ nhiều người bán ở nhiều bang). Hàm gộp về cấp **(đơn hàng, tuyến)**:

$$\text{route}_i = \text{seller\_state}_i \to \text{cust\_state}_i$$

Với mỗi cặp `(order_id, route)` là duy nhất, các cột số được tổng hợp như sau:

| Cột | Phương thức | Lý do |
| --- | --- | --- |
| `is_late` | `max` | Đơn được coi là trễ nếu bất kỳ item nào trễ |
| `delay_days` | `first` | Lấy giá trị của item đầu tiên (delay_days giống nhau trong 1 đơn) |
| `approval`, `prep`, `transit` | `first` | Thời gian giai đoạn không phụ thuộc item |
| `freight` | `sum` | Tổng phí vận chuyển |
| `n_items` | `count` | Số item trong đơn |

**Quy ước đơn trễ:**

$$\text{is\_late}_i = \mathbb{1}[d_i > 0]$$

Không dùng cột `is_late` trực tiếp từ CSV; cột này được tạo lại từ `delay_days > 0` để đảm bảo nhất quán.

---

## 2. Xếp hạng tuyến — `route_priority(O, red, amber, min_orders, top)`

**Tỷ lệ trễ toàn hệ thống:**

$$\bar{L} = \frac{\sum_{i \in O} \mathbb{1}[d_i > 0]}{N}$$

**Tỷ lệ trễ của tuyến $r$:**

$$L_r = \frac{\sum_{i \in O_r} \mathbb{1}[d_i > 0]}{N_r}$$

**Phân loại mức độ:**

$$\text{level}(r) = \begin{cases}
\text{red} & \text{nếu } L_r \geq \bar{L} \cdot \theta_{\text{red}} \\
\text{amber} & \text{nếu } \bar{L} \cdot \theta_{\text{amber}} \leq L_r < \bar{L} \cdot \theta_{\text{red}} \\
\text{ok} & \text{nếu } L_r < \bar{L} \cdot \theta_{\text{amber}}
\end{cases}$$

với $\theta_{\text{red}} = 2.0$, $\theta_{\text{amber}} = 1.5$ (mặc định).

Chỉ xét tuyến $r$ nếu $N_r \geq \text{min\_orders}$ (mặc định 100). Kết quả mặc định dùng **red-first** (`ensure_red=True`): trả tất cả tuyến đỏ trước, sắp giảm dần theo `late_orders`, rồi thêm tuyến vàng cho đủ `top` (chi tiết 2a).

**Tham số sản xuất mặc định:** `red=2.0, amber=1.5, min_orders=100, top=10, ensure_red=True`.

### 2a. Sắp xếp red-first (`ensure_red=True`)

Mặc định API trả về **tất cả tuyến đỏ trước** (sắp giảm dần theo `late_orders`), sau đó thêm tuyến vàng cho đủ `top`. Nếu số tuyến đỏ ≥ `top`, trả hết tuyến đỏ (nhiều hơn `top`) để không bỏ sót tuyến đỏ nào.

$$\text{result} = \text{sort\_desc}(R_{\text{red}}) \;\|\; \text{sort\_desc}(R_{\text{amber}})\!\left[\,:\max(0,\,\text{top} - |R_{\text{red}}|)\right]$$

`ensure_red=False` dùng cho các bảng phân tích nội bộ (xếp thuần theo `late_orders`, cắt đúng `top`).

### 2b. Khoảng tin cậy Wilson 95% — `wilson_interval(k, n)`

$$\hat{p} = \frac{k}{n}, \quad z = 1{,}96$$

$$\text{ci\_low}, \text{ci\_high} = \frac{\hat{p} + \frac{z^2}{2n} \mp z\sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

(lấy dấu $-$ cho cận dưới, $+$ cho cận trên; kẹp về $[0,1]$.)

### 2c. Cờ `low_sample`

$$\text{low\_sample}(r) = \mathbb{1}\!\left[N_r < 200\right]$$

Chỉ là cảnh báo hiển thị — không đổi `level`, thứ tự, hay ngưỡng.

### 2d. Cờ `uncertain`

$$\text{uncertain}(r) = \begin{cases}
\mathbb{1}\!\left[\text{ci\_low}(r) < \bar{L} \cdot \theta_{\text{red}}\right] & \text{nếu level}(r) = \text{red} \\
\mathbb{1}\!\left[\text{ci\_low}(r) < \bar{L} \cdot \theta_{\text{amber}}\right] & \text{nếu level}(r) = \text{amber}
\end{cases}$$

Nghĩa: cận dưới Wilson của tuyến nằm **dưới ngưỡng phân loại** của chính nó → khoảng tin cậy **chứa** ngưỡng → nhãn đỏ/vàng chưa được xác nhận chắc chắn. Với dữ liệu hiện tại ($\bar{L} \approx 8{,}07\%$, ngưỡng đỏ ≈ 16,14%, ngưỡng vàng ≈ 12,11%): **7/14 tuyến gắn cờ** có `uncertain=True` (SP→PI, SP→SE, PR→BA, PR→RJ, SP→PA, SP→MS, SP→TO). Chỉ để hiển thị cảnh báo — không đổi `level`, thứ tự, `stage`, `has_bottleneck`; cờ **độc lập với `low_sample`** (có tuyến mẫu nhỏ nhưng `uncertain=False` và ngược lại).

**Lưu ý:** `uncertain` dùng $\bar{L}$ tính trên **toàn bộ dữ liệu** (~8,07%); không dùng tỷ lệ trễ của tập kiểm tra ML (~5,98%).

---

## 3. Phân tích nguyên nhân gốc — `root_cause(O, r)` và `excess_ratio`

**Thời gian trung bình toàn hệ thống của giai đoạn $s$:**

$$\mu_s = \frac{1}{N} \sum_{i \in O} x_s^{(i)}, \quad s \in \{\text{approval}, \text{prep}, \text{transit}\}$$

Với dữ liệu hiện tại: $\mu_{\text{approval}} \approx 0{,}43$ ngày, $\mu_{\text{prep}} \approx 2{,}79$ ngày, $\mu_{\text{transit}} \approx 9{,}32$ ngày.

**Phần vượt tuyệt đối (excess) của tuyến $r$:**

$$e_s(r) = \bar{x}_s^{(r)} - \mu_s, \quad \text{với } \bar{x}_s^{(r)} = \frac{1}{N_r}\sum_{i \in O_r} x_s^{(i)}$$

**Giai đoạn nghẽn** (xác định theo excess tuyệt đối):

$$s^*(r) = \arg\max_s \, e_s(r)$$

**Có nghẽn thực sự không:**

$$\text{has\_bottleneck}(r) = \mathbb{1}\!\left[\max_s e_s(r) > 0\right]$$

Nếu `has_bottleneck = False` thì tất cả giai đoạn của tuyến đều nằm dưới (hoặc bằng) mức trung bình hệ thống — tuyến không có nghẽn. `stage` vẫn trả về giai đoạn có $e_s$ lớn nhất (dù âm) để đảm bảo API luôn có trường `stage`.

**Excess ratio (chỉ tham khảo trong `top_routes_report`):**

$$\rho_s(r) = \frac{e_s(r)}{|\mu_s|}$$

Chuẩn hóa excess theo độ lớn trung bình hệ thống, cho phép so sánh tương đối giữa các giai đoạn khi $\mu_s$ chênh lệch lớn. Với 14 tuyến gắn cờ: `stage` theo $e_s$ và `stage` theo $\rho_s$ **trùng nhau ở tất cả 14 tuyến** (transit dẫn đầu ở 13/14; MA→SP có $e_{\text{prep}} = 2{,}10 > e_{\text{transit}} = 1{,}43$ và $\rho_{\text{prep}} = 0{,}75 > \rho_{\text{transit}} = 0{,}15$ → cũng prep). Tức **0/14 tuyến đổi stage**; SP→TO (transit 0,53 vs approval 0,38) và PR→BA (transit 0,91 vs approval 0,33) là hai tuyến sát nhất. `stage` và `has_bottleneck` trong DSS luôn xác định theo $e_s$ tuyệt đối; `excess_ratio` chỉ báo cáo để tham khảo, không đổi logic.

---

## 4. Kịch bản What-if — `scenario(O, r, cut)`

### Giả định cốt lõi: cắt giảm thời gian chuyển 1:1 sang ngày giao

Nếu cắt giảm $c_s$ ngày ở giai đoạn $s$, thời gian thực tế của đơn $i$ giảm đi $\min(c_s,\, x_s^{(i)})$ ngày (không thể cắt quá thời gian thực có). Độ trễ mới:

$$d_i' = d_i - \sum_{s} \min\!\left(\max(0, c_s),\, x_s^{(i)}\right)$$

$$\text{is\_late}'_i = \mathbb{1}[d_i' > 0]$$

**Tỷ lệ trễ dự báo:**

$$L_r' = \frac{\sum_{i \in O_r} \mathbb{1}[d_i' > 0]}{N_r}$$

**Số đơn trễ tránh được:**

$$\Delta = \sum_{i \in O_r}\left(\mathbb{1}[d_i > 0] - \mathbb{1}[d_i' > 0]\right)$$

**Giả định quan trọng:** giảm 1 ngày ở bất kỳ giai đoạn nào đều dịch chuyển ngày giao thực tế sớm hơn 1 ngày (chuỗi các giai đoạn không trùng nhau, không có buffer). Trong thực tế, tiết kiệm thời gian chuẩn bị không phải lúc nào cũng chuyển thẳng sang ngày giao (người bán có thể giữ hàng thêm, carrier có lịch cố định, ...).

### Phân tích độ nhạy — `sensitivity(O, r, stage, max_days=5, base_cut=None)`

Tính $L_r'$ khi $c_s \in \{0, 1, 2, \ldots, \text{max\_days}\}$ cho một giai đoạn $s$ duy nhất, trong khi giữ cố định mức cắt của các giai đoạn khác.

**Tham số `base_cut`:** dict các mức cắt cố định của giai đoạn *khác* $s$ (ví dụ `{"prep": 2}` khi quét `transit`). Nếu `base_cut=None` (mặc định), các giai đoạn còn lại được đặt về 0 — hành vi giống phiên bản cũ.

Với bước quét $x$:

$$L_r'(x) = \text{projected}\!\left(O, r,\ \{s: x\} \cup \text{base\_cut}\right)$$

**Tính nhất quán với `projected`:** khi view Django nhận `approval`, `prep`, `transit` từ query string, `base_cut` được đặt thành `{k: v for k, v in \text{cut}.items() if k \neq s^*}` (loại bỏ giai đoạn bottleneck $s^*$ ra khỏi base). Vì vậy với mức quét $x = c_{s^*}$ (mức cắt hiện tại của bottleneck):

$$\text{series}[c_{s^*}].\text{projected} = \text{projected}(O, r, \text{cut})$$

Điều này đảm bảo điểm tương ứng trên đường cong độ nhạy luôn khớp với giá trị `projected` trả về trong cùng response.

---

## 5. Goal Seek cam kết — `goal_seek_promise(O, r, target)`

Tìm số ngày cần kéo dài cam kết giao hàng để tỷ lệ trễ (theo định nghĩa mới) ≤ `target`.

**Ý tưởng:** kéo dài cam kết $x$ ngày tương đương với giảm `delay_days` của toàn bộ đơn đi $x$ ngày:

$$d_i^{(x)} = d_i - x$$

$$L_r^{(x)} = \frac{\sum_{i \in O_r} \mathbb{1}[d_i - x > 0]}{N_r}$$

**Giải bằng phân vị:** $L_r^{(x)} = P(d_i > x)$, vì vậy:

$$x^* = \max\!\left(0,\, \lceil Q_{1-\alpha}(d_i^{(r)}) \rceil\right), \quad \text{với } Q_{1-\alpha} = \text{quantile}(1 - \text{target})$$

```python
x = max(0, math.ceil(d.delay_days.quantile(1 - target)))
```

Lưu ý: $x^*$ là số nguyên (ngày); `late_after` được tính lại từ $x^*$ thực tế (có thể < target một chút).

---

## 6. Goal Seek cắt giảm — `goal_seek_cut(O, r, stage, target, step=0.5, max_days=10)`

Tìm mức cắt tối thiểu $c^*$ ở giai đoạn $s$ để $L_r'(c) \leq \text{target}$.

**Thuật toán:** tìm kiếm tuyến tính với bước $0.5$ ngày:

$$c^* = \min\{c \in \{0, 0.5, 1.0, \ldots, \text{max\_days}\} : L_r'(c) \leq \text{target}\}$$

Trả về `None` nếu không có $c \leq \text{max\_days}$ nào đạt được target.

---

## 7. Backtest — `backtest(O, min_orders, start_year, min_period_orders)`

### Thiết lập

- Phân tổng thể theo tháng: $O_t$ = tập đơn thuộc kỳ $t$ (YYYYMM).
- Với mỗi cặp kỳ liên tiếp $(t, t+1)$:
  1. Chạy `route_priority` trên $O_t$ → tập tuyến gắn cờ $R_t$.
  2. Chia $O_{t+1}$ thành hai nhóm: đơn thuộc tuyến trong $R_t$ (nhóm **flagged**) và phần còn lại (nhóm **other**).
  3. Tính tỷ lệ trễ của hai nhóm.

### Chỉ số chính

$$\text{diff}_t = L_{\text{flagged},\,t+1} - L_{\text{other},\,t+1}$$

$$\overline{\text{diff}}_{\text{mean}} = \frac{1}{|T|} \sum_{t \in T} \text{diff}_t$$

$$\overline{\text{diff}}_{\text{weighted}} = \frac{\sum_{t \in T} \text{diff}_t \cdot N_{t+1}}{\sum_{t \in T} N_{t+1}}$$

với $T$ = tập kỳ có thể so sánh (có ít nhất một tuyến gắn cờ **và** có đơn gắn cờ ở kỳ $t+1$), $N_{t+1}$ = tổng số đơn kỳ $t+1$ (trọng số).

**Chú thích trọng số `weighted_diff`:** trọng số $= N_{t+1} = |\,O_{t+1}|$ (tổng số đơn kỳ $t+1$, không phân biệt nhóm). Lý do: kỳ có nhiều đơn hơn → ước lượng $L$ chính xác hơn → đáng được trọng số cao hơn. Cách thay thế (trọng số = số đơn nhóm flagged) cho +10.32 pp; xem `dss_results.md` mục A1 để so sánh.

### Lọc kỳ

| Điều kiện bỏ qua kỳ $t$ | Lý do |
| --- | --- |
| $t < \text{start\_year} \times 100$ | Năm 2016 có quá ít đơn |
| $t+1 \notin$ tập tháng trong dữ liệu | Không có kỳ tiếp theo |
| $\|O_t\| < \text{min\_period\_orders}$ hoặc $\|O_{t+1}\| < \text{min\_period\_orders}$ | Mẫu quá nhỏ để ước lượng tỷ lệ trễ tin cậy |

### 7b. Bootstrap CI — `bootstrap_ci(frame, n_boot, seed, alpha, weight_col)`

Ước lượng khoảng tin cậy 95% cho `weighted_diff` và các hiệu số so với baseline bằng hai loại bootstrap:

**Pair bootstrap** (lấy mẫu có hoàn lại theo kỳ, đơn vị = một kỳ $t$):

$$\hat{\delta}^{*(b)} = \frac{\sum_{t \in T^{*(b)}} \text{diff}_t \cdot N_{t+1}}{\sum_{t \in T^{*(b)}} N_{t+1}}, \quad b = 1,\ldots,B$$

**Block bootstrap** (circular, block_size = 3 tháng, để tính tự tương quan giữa các kỳ liền kề):

Chọn $\lceil |T|/3 \rceil$ vị trí bắt đầu ngẫu nhiên, mỗi block lấy 3 kỳ liên tiếp; vì là circular nên kỳ cuối được nối với kỳ đầu. Cắt bớt về đúng $|T|$ kỳ rồi tính `weighted_diff` trên mẫu đó.

**CI 95%** (percentile method): $[\hat{\delta}^{*}_{0{,}025},\, \hat{\delta}^{*}_{0{,}975}]$.

Tham số cố định: $B = 10\,000$, seed = 42, weight\_col = `total_orders`. Kết quả báo cáo theo **đơn vị điểm phần trăm (pp)**.

Bootstrap so sánh DSS với **0**, với **prior** và với **through**; **through là so sánh chính** (baseline through dùng cùng lượng thông tin với DSS). Kết quả pair bootstrap:

| So sánh | CI 95% (pp) | Kết luận |
| --- | --- | --- |
| vs 0 | [+3,68; +12,40] | Không chứa 0 → có thể nói "vượt 0" |
| vs prior | [+0,45; +5,79] | Không chứa 0 → có thể nói "vượt prior" |
| vs through (chính) | [−0,58; +2,35] | Chứa 0 → không dùng chữ "vượt" |

Chỉ dùng chữ "vượt" khi CI không chứa 0.

Kỳ không có tuyến nào gắn cờ được ghi lại trong `periods` với `diff = NaN` và **không** tính vào `periods_evaluated`.

---

## 8. Giả định và hạn chế

### Giả định đã dùng

1. **Cắt giảm thời gian giai đoạn chuyển 1:1 sang ngày giao:** Giảm $c$ ngày ở bất kỳ giai đoạn nào làm ngày giao sớm hơn đúng $c$ ngày. Không mô hình hóa buffer, lịch cố định của carrier, hay hiệu ứng nghẽn cổ chai thực tế.

   **Hệ quả của giả định 1:1 đối với `transit_goal_cut` và `promise_days`:** Dưới giả định này, cắt $c$ ngày transit tương đương kéo dài cam kết $c$ ngày (trừ phần chặn bởi `transit_i < c`). Do đó `transit_goal_cut` (kết quả của `goal_seek_cut`) thường xấp xỉ `promise_days` (kết quả của `goal_seek_promise`). Ví dụ với SP->BA: cả hai đều cho 10 ngày. **Lưu ý quan trọng:** **SP->BA:** mức cắt tối thiểu theo giả định 1:1 là 10 ngày, trùng biên `max_days=10`. **SP->ES:** 9 ngày, gần biên nhưng chưa chạm. Cả hai đều vượt xa excess transit của tuyến (SP->BA ~7,2 ngày; SP->ES ~3,1 ngày), nên không nên trình bày như phương án khả thi.

2. **Tuyến = (bang người bán → bang khách hàng):** Bỏ qua sự khác biệt giữa các thành phố, mã bưu điện, hay carrier cụ thể trong cùng một tuyến.

3. **Một đơn có thể xuất hiện ở nhiều tuyến** nếu có item từ nhiều bang khác nhau. Trong thực tế đây là ~519 đơn (~0.5%).

4. **Tỷ lệ trễ là chỉ số duy nhất:** Không mô hình hóa chi phí, doanh thu, hay tác động chuỗi cung ứng.

5. **Backtest là quan hệ liên quan, không phải nhân quả:** Việc gắn cờ ở kỳ $t$ có tương quan với tỷ lệ trễ cao ở kỳ $t+1$ (16/19 kỳ), nhưng không chứng minh rằng can thiệp vào tuyến đó sẽ giảm trễ.

6. **Mô hình tĩnh:** Dữ liệu huấn luyện và đánh giá đều từ cùng một bộ dữ liệu lịch sử (Olist 2016–2018); mô hình không tự cập nhật khi có dữ liệu mới.

### Hạn chế đã quan sát

> **⚠️ Nhãn cảnh báo giao diện:**
> - Tab **Dashboard**, **OLAP**, **ETL Monitor** trong `web/Olist_Logistics_DSS_v3.html` hiển thị **dữ liệu mẫu** (mock data, Flask, chưa nối Django). Số liệu trên các tab đó **không phản ánh dữ liệu Olist thực tế**.
> - Khối **At-Risk** hiển thị **điểm nguy cơ (`risk_score`)** — điểm xếp hạng từ mô hình ML chưa hiệu chỉnh, **không phải xác suất trễ thực tế**. Điểm trung bình ~0,412 trong khi tỷ lệ trễ thật chỉ ~5,98% (miscalibrated). Dùng để **xếp thứ tự ưu tiên rà soát**, không dùng làm ngưỡng tuyệt đối.

| Hạn chế | Số liệu | Ảnh hưởng |
| --- | --- | --- |
| `seller_prep_time_days` âm | 1 542 dòng (cấp fact) | Có thể là lỗi dữ liệu (timestamp ngược); loại bỏ không đổi kết luận nghẽn nhưng thay đổi độ lớn excess một chút |
| `carrier_transit_time_days` âm | 50 dòng | Tương tự trên |
| `review_score` rỗng | 827 dòng | Không ảnh hưởng mô hình chính (không dùng review score); ảnh hưởng cột `has_logistics_complaint` |
| Backtest so sánh với baseline đơn giản — kết quả hỗn hợp | DSS tốt hơn 11/19 kỳ vs baseline "through"; **pair CI vs through = [−0,58; +2,35] pp chứa 0** (điểm ước lượng +0,8 pp) | Tín hiệu DSS có giá trị nhưng không vượt trội rõ rệt về mặt thống kê so với baseline dùng cùng thông tin |
| `goal_seek_cut` (transit, target=5%) với 3 tuyến top | SP→BA = 10 ngày, SP→ES = 9 ngày; chỉ SP→RJ = None | **SP→BA:** mức cắt tối thiểu theo giả định 1:1 là 10 ngày, trùng biên `max_days=10`. **SP→ES:** 9 ngày, gần biên nhưng chưa chạm. Cả hai đều vượt xa excess transit của tuyến (SP→BA ~7,2 ngày; SP→ES ~3,1 ngày) — không nên trình bày như phương án khả thi |
| `risk_score` trong khối At-Risk không phải xác suất đã hiệu chỉnh | Điểm TB ~0,412 trong khi tỷ lệ trễ thật ~5,98% (tập kiểm tra ML, khác $\bar{L} \approx 8{,}07\%$ toàn bộ data) | Khối at-risk dùng để xếp hạng ưu tiên rà soát; không dùng `risk_score` làm ngưỡng tuyệt đối |
| DSS chính rule-based; ML chỉ ở khối At-Risk | Thiết kế chủ ý | 4 khối DSS chính không dùng ML; khối At-Risk endpoint `/api/dss/at-risk` dùng mô hình ML riêng (`late_risk.joblib`) |

---

## 9. Tóm tắt tham số mặc định

| Hàm | Tham số | Giá trị mặc định | Ghi chú |
| --- | --- | --- | --- |
| `route_priority` | `red` | 2.0 | Bội số $\bar{L}$ để phân loại đỏ |
| `route_priority` | `amber` | 1.5 | Bội số $\bar{L}$ để phân loại vàng |
| `route_priority` | `min_orders` | 100 | Ngưỡng tối thiểu đơn trên tuyến |
| `route_priority` | `top` | 10 | Số tuyến trả về |
| `route_priority` | `ensure_red` | `True` | Red-first: trả tất cả tuyến đỏ trước; `False` xếp thuần theo `late_orders` và cắt đúng `top` |
| `goal_seek_promise` | `target` | 0.05 | Tỷ lệ trễ mục tiêu (5%) |
| `goal_seek_cut` | `target` | 0.05 | Tỷ lệ trễ mục tiêu |
| `goal_seek_cut` | `step` | 0.5 | Bước tìm kiếm (ngày) |
| `goal_seek_cut` | `max_days` | 10 | Giới hạn tìm kiếm tối đa |
| `sensitivity` | `max_days` | 5 | Dải cắt giảm 0..5 ngày |
| `sensitivity` | `base_cut` | `None` (→ `{}`) | Mức cắt cố định của giai đoạn khác khi quét; `None` = tương thích ngược |
| `backtest` | `min_orders` | 30 | Cho đánh giá theo tháng (không phải sản xuất) |
| `backtest` | `min_period_orders` | 500 | Ngưỡng tối thiểu đơn trong kỳ |
| `backtest` | `start_year` | 2017 | Bỏ năm 2016 quá thưa |
