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

Chỉ xét tuyến $r$ nếu $N_r \geq \text{min\_orders}$ (mặc định 100). Kết quả sắp xếp giảm dần theo số đơn trễ, trả về `top` tuyến đầu.

**Tham số sản xuất mặc định:** `red=2.0, amber=1.5, min_orders=100, top=10`.

---

## 3. Phân tích nguyên nhân gốc — `root_cause(O, r)`

**Thời gian trung bình toàn hệ thống của giai đoạn $s$:**

$$\mu_s = \frac{1}{N} \sum_{i \in O} x_s^{(i)}, \quad s \in \{\text{approval}, \text{prep}, \text{transit}\}$$

**Phần vượt (excess) của tuyến $r$ so với hệ thống:**

$$e_s(r) = \bar{x}_s^{(r)} - \mu_s, \quad \text{với } \bar{x}_s^{(r)} = \frac{1}{N_r}\sum_{i \in O_r} x_s^{(i)}$$

**Giai đoạn nghẽn:**

$$s^*(r) = \arg\max_s \, e_s(r)$$

**Có nghẽn thực sự không:**

$$\text{has\_bottleneck}(r) = \mathbb{1}\!\left[\max_s e_s(r) > 0\right]$$

Nếu `has_bottleneck = False` thì tất cả giai đoạn của tuyến đều nằm dưới (hoặc bằng) mức trung bình hệ thống — tuyến không có nghẽn. `stage` vẫn trả về giai đoạn có $e_s$ lớn nhất (dù âm) để đảm bảo API luôn có trường `stage`.

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

Kỳ không có tuyến nào gắn cờ được ghi lại trong `periods` với `diff = NaN` và **không** tính vào `periods_evaluated`.

---

## 8. Giả định và hạn chế

### Giả định đã dùng

1. **Cắt giảm thời gian giai đoạn chuyển 1:1 sang ngày giao:** Giảm $c$ ngày ở bất kỳ giai đoạn nào làm ngày giao sớm hơn đúng $c$ ngày. Không mô hình hóa buffer, lịch cố định của carrier, hay hiệu ứng nghẽn cổ chai thực tế.

   **Hệ quả của giả định 1:1 đối với `transit_goal_cut` và `promise_days`:** Dưới giả định này, cắt $c$ ngày transit tương đương kéo dài cam kết $c$ ngày (trừ phần chặn bởi `transit_i < c`). Do đó `transit_goal_cut` (kết quả của `goal_seek_cut`) thường xấp xỉ `promise_days` (kết quả của `goal_seek_promise`). Ví dụ với SP->BA: cả hai đều cho 10 ngày. **Lưu ý quan trọng:** 10 ngày transit cut vượt quá excess transit trung bình của SP->BA (~7,2 ngày), nghĩa là yêu cầu cắt nhiều hơn tổng phần vượt mức — không phải phương án khả thi trong thực tế. `transit_goal_cut=10` chỉ là giới hạn trên trong lưới tìm kiếm, **không nên trình bày như phương án can thiệp cụ thể**.

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
| Backtest so sánh với baseline đơn giản — kết quả hỗn hợp | DSS tốt hơn 11/19 kỳ vs baseline "through"; CI vs through chứa 0 | Tín hiệu DSS có giá trị nhưng không vượt trội rõ rệt về mặt thống kê so với baseline dùng cùng thông tin |
| `goal_seek_cut` thường không đạt target trong 10 ngày | SP->RJ, SP->BA, SP->ES đều `None` | Với tuyến có transit excess lớn (>3 ngày), cắt đơn thuần một giai đoạn không đủ; cần kết hợp nhiều giai đoạn hoặc dùng `goal_seek_promise` |
| `risk_score` không phải xác suất đã hiệu chỉnh | Điểm TB 0,412 vs tỷ lệ trễ thật 5,98% | Không dùng ngưỡng tuyệt đối; chỉ dùng để xếp hạng ưu tiên rà soát |
| Không có ML trong mô hình DSS chính | Thiết kế chủ ý | Mô hình hoàn toàn theo luật (rule-based); dễ giải thích nhưng không học từ dữ liệu mới |

---

## 9. Tóm tắt tham số mặc định

| Hàm | Tham số | Giá trị mặc định | Ghi chú |
| --- | --- | --- | --- |
| `route_priority` | `red` | 2.0 | Bội số $\bar{L}$ để phân loại đỏ |
| `route_priority` | `amber` | 1.5 | Bội số $\bar{L}$ để phân loại vàng |
| `route_priority` | `min_orders` | 100 | Ngưỡng tối thiểu đơn trên tuyến |
| `route_priority` | `top` | 10 | Số tuyến trả về |
| `goal_seek_promise` | `target` | 0.05 | Tỷ lệ trễ mục tiêu (5%) |
| `goal_seek_cut` | `target` | 0.05 | Tỷ lệ trễ mục tiêu |
| `goal_seek_cut` | `step` | 0.5 | Bước tìm kiếm (ngày) |
| `goal_seek_cut` | `max_days` | 10 | Giới hạn tìm kiếm tối đa |
| `sensitivity` | `max_days` | 5 | Dải cắt giảm 0..5 ngày |
| `sensitivity` | `base_cut` | `None` (→ `{}`) | Mức cắt cố định của giai đoạn khác khi quét; `None` = tương thích ngược |
| `backtest` | `min_orders` | 30 | Cho đánh giá theo tháng (không phải sản xuất) |
| `backtest` | `min_period_orders` | 500 | Ngưỡng tối thiểu đơn trong kỳ |
| `backtest` | `start_year` | 2017 | Bỏ năm 2016 quá thưa |
