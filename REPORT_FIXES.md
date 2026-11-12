# REPORT_FIXES — sửa lời văn trong `main.pdf` (Phase 1)

Chỉ sửa **cách diễn đạt/định nghĩa** cho khớp code và dữ liệu thật. **Không đổi
bất kỳ con số nào** trong báo cáo. Mỗi mục ghi: vị trí, câu hiện tại, câu thay
thế, lý do.

## 2.2 — nhãn bên phụ trách

**Thêm** ngay sau đoạn bốn nhóm người dùng:

> Trong các khối hành động, nhãn “bên phụ trách” lấy từ một nguồn duy nhất
> (`OWNER` trong `etl/dss_models.py`): **Duyệt thanh toán** (approval),
> **Người bán** (prep), **Đơn vị vận chuyển** (transit). Decision Brief dùng
> thêm **Vận hành cam kết giao hàng** cho nhóm promise và
> **Đội dữ liệu / vận hành tuyến** cho nhóm cần thêm dữ liệu.

Lý do: code là nguồn chuẩn (C6); backend `/brief` trả `owner` và UI đọc trường
này, nên báo cáo không nên dùng nhãn khác.

## 3.2 — làm sạch city và zfill

Trong bảng “Vấn đề / Biểu hiện / Quy tắc xử lý”:

1. Dòng **“Trùng toạ độ theo zip”** — thay “lấy city phổ biến nhất” bằng:
   > Gộp theo zip: lấy trung bình lat/lng; **giữ city của dòng xuất hiện đầu
   > tiên** (khách trước, người bán sau), không lấy mode.
2. Dòng **“Tên thành phố không nhất quán”** — thay toàn bộ quy tắc bằng:
   > **Không chuẩn hoá city**; giữ nguyên giá trị gốc. City không tham gia
   > tính tuyến (chỉ dùng `seller_state`/`cust_state`) và không tham gia
   > `distance_km` (chỉ dùng lat/lng trung bình theo zip), nên bỏ dấu/hoa-thường
   > không làm đổi số liệu DSS.
3. Bổ sung ghi chú dưới bảng:
   > Trong 15.078 zip, chỉ 10 zip có city first-seen khác city mode; 3 giá trị
   > chứa ký tự ngoài ASCII; 0 giá trị có chữ hoa hoặc khoảng trắng đầu/cuối.
   > Vì vậy chuẩn hoá city chỉ đổi nhãn 10 dòng, không đổi tuyến hay khoảng cách.
4. Bổ sung vào dòng “Mã địa điểm mất số 0 đầu”:
   > Trước `zfill(5)` có kiểm tra `isna()`; giá trị thiếu bị chặn bằng lỗi rõ
   > ràng thay vì tạo chuỗi `"00nan"`.

Lý do: `etl/dim_location.py` dùng `drop_duplicates(keep="first")`; city không
được đọc bởi `load_orders()`/route/distance. `normalize_location_id()` đã thêm
guard NaN (C2, C3).

## 4.2.2 — `Dim_Time`

Dòng `Dim_Time` trong bảng chiều — thay:

> Sinh tự động từ ngày đặt hàng nhỏ nhất đến lớn nhất; `time_id` dạng `yyyymmdd`

bằng:

> Sinh từ **tập ngày đặt hàng quan sát được** trong `orders`: **612 ngày duy
> nhất**, không phải dải lịch liên tục từ min đến max; `time_id` dạng `yyyymmdd`.

Lý do: live `dim_time` có 612 dòng, đúng bằng số ngày có đơn (C1).

## 5.1 — owner và nguồn dữ liệu của backend

1. Thay câu “quản lý dữ liệu là kho PostgreSQL; …” bằng:
   > Quản lý dữ liệu là kho PostgreSQL, nhưng backend DSS hiện **đọc 5 tệp CSV
   > đã làm sạch** trong `data/processed` (không truy vấn PostgreSQL);
   > PostgreSQL lưu kho và bảng log hành động. Đây là sai lệch có chủ đích,
   > giữ nguyên để khớp các số liệu đã kiểm chứng (C10).
2. Thêm câu về nhãn phụ trách (giống §2.2 ở trên).

Lý do: `etl/dss_models.load_orders()` đọc CSV; ORM chỉ dùng cho
`dss_action_log`. Code `OWNER` là chuẩn (C6, C10).

## 5.3 — công thức phần vượt benchmark

Thay câu:

> Giai đoạn được chuẩn hoá: `t̃s = min(ts, bs)`.

bằng:

> Phần vượt benchmark: `e_s = t_s − b_s` (**giữ dấu**; không cắt ở 0 và không
> dùng `t̃s = min(t_s, b_s)`). Hàm `v(S)` dùng `e_s`, vì vậy `φ_s` **có thể
> âm** khi giai đoạn `s` ngắn hơn benchmark. Bất biến vẫn là
> `late_actual = late_benchmark + Σφ_s`.

Thay câu về residual:

> Phần chưa giải thích được là `residual_promise`: đơn vẫn trễ khi cả ba giai
> đoạn đã chuẩn hoá (liên quan tới ngày cam kết).

bằng:

> Phần chưa giải thích được là `residual_promise = v(∅) = late_benchmark`: đơn
> vẫn trễ khi **cả ba giai đoạn đạt benchmark** (liên quan ngày cam kết).
> `residual_promise_days` là số ngày cam kết vượt benchmark, không phải `φ`.

Lý do: `_shapley_orders()` dùng `excess = actual − benchmark` có dấu. Không đổi
số nào (C5).

## 6.3 — CSV, DDL và bảng log

Thay đoạn:

> Bốn bảng chiều và bảng fact tạo bằng `sql/create_tables.sql` (Phụ lục A);
> Django ánh xạ chúng với `managed=False` và tạo thêm bảng `dss_action_log` để
> ghi hành động. Backend nạp dữ liệu một lần khi khởi động (khoảng 97 000 dòng
> CSV, 5–10 giây).

bằng:

> Bốn bảng chiều và bảng fact tạo bằng `sql/create_tables.sql` (Phụ lục A) và
> được nạp vào PostgreSQL bằng ETL. Django ánh xạ 5 bảng với `managed=False`
> để tham chiếu, và dùng bảng `dss_action_log` (DDL nằm trong
> `sql/create_tables.sql`) để ghi hành động. Các endpoint DSS **đọc trực tiếp
> 5 CSV đã làm sạch** trong `data/processed` khi khởi động (khoảng 97 000 dòng
> CSV, 5–10 giây), **không truy vấn PostgreSQL**; đây là sai lệch có chủ đích
> (C10).

Lý do: code thật đọc CSV; bảng log vẫn qua `detail` (C4). Ghi chú thêm: bảng
`fact_delivery_sla` live có cột thừa `handoff_slack_days` không dùng và không có
trong Phụ lục A — xem mục “Phụ lục A” bên dưới.

## 6.4 / 7.1 — vì sao bộ lọc năm chỉ có 2017 và 2018

Thêm một câu ngay sau “bộ lọc năm (tất cả, 2017, 2018)” ở §6.4:

> Bộ lọc không mở 2016 vì cả năm 2016 chỉ có **263 đơn (265 đơn-tuyến)** tập
> trung ở tháng 10/2016, và **0 tuyến đạt `min_orders=100`** (cao nhất là
> SP→SP với 59 đơn), nên `route_priority` không thể xếp hạng hay gắn cờ năm
> 2016.

Lý do: `etl/dss_eval.py:155,166,197` đã loại 2016 khỏi backtest với ghi chú
“quá ít đơn”; §7.2 của báo cáo cũng đã nêu “Q1 chỉ trả lời được theo bộ lọc năm
2017/2018”. Không đổi số nào.

## Phụ lục A — DDL

1. **Không thêm** `handoff_slack_days` (xem mục C10 bên dưới).
2. Ghi chú schema thực tế: bảng `fact_delivery_sla` trong PostgreSQL live **có thêm
   một cột thừa không dùng** `handoff_slack_days double precision`, cột này
   **không có trong Phụ lục A** và không có trong ETL/CSV/model. Đây là cột tồn
   dư từ phiên bản trước, không hàm nào đọc; giữ nguyên, không thêm vào Phụ lục A.
3. Nếu muốn Phụ lục A khớp `sql/create_tables.sql`, thêm sau
   `Fact_Delivery_SLA`:

```sql
CREATE TABLE dss_action_log (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    action VARCHAR(40) NOT NULL,
    route VARCHAR(20) NOT NULL,
    level VARCHAR(10) NOT NULL,
    detail TEXT NOT NULL
);
```

`dss_action_log` là bảng ứng dụng, không thuộc 5 bảng kho.

## C10 — `handoff_slack_days` là gì?

- **Định nghĩa cũ:** `order_delivered_carrier_date − shipping_limit_date`
  (ngày), tính ở cấp item rồi lấy **max** ở cấp đơn.
- **Nơi từng định nghĩa:** ETL `etl/fact_delivery_sla.py`, DDL
  `sql/create_tables.sql`, model fact.
- **Hiện trạng:** đã bị xoá khỏi ETL/DDL/model ở commit `2ca725d`
  (“drop unused handoff_slack_days”). Không có trong CSV, code, hay Phụ lục A.
  Chỉ còn **cột vật lý cũ** `fact_delivery_sla.handoff_slack_days` trong
  PostgreSQL live; không hàm nào đọc cột này.
- **Phụ lục A:** **không** chứa `handoff_slack_days`; giữ nguyên như vậy.
- **Đề xuất:** không đưa cột này trở lại. Việc drop cột live (nếu muốn) để
  thành câu hỏi riêng, không làm trong Phase 1.

## C4 — DDL `dss_action_log`

Giữ nguyên contract live/code: `id, created_at, action, route, level, detail`.
`sql/create_tables.sql` đã được bổ sung DDL khớp live. Không đổi tên cột, không
thêm `status`/`note`; nếu sau này cần `status` thì thêm **cột mới** với default
`'recorded'` (chưa làm).
