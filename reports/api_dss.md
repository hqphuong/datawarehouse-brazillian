# API DSS — Tài liệu endpoint Django

Backend: Django 6, chạy tại `http://127.0.0.1:8000/`.  
Prefix chung: `/api/dss/`.  
Tất cả response có `Content-Type: application/json`.  
NaN và Infinity trong kết quả Python được chuyển thành `null` trước khi trả về.

---

## Danh sách endpoint

| Method | Đường dẫn | Mô tả |
| --- | --- | --- |
| GET | `/api/dss/routes` | Danh sách tuyến đỏ/vàng kèm nguyên nhân gốc |
| GET | `/api/dss/scenario` | What-if: tỷ lệ trễ dự báo khi cắt thời gian giai đoạn |
| GET | `/api/dss/promise` | Goal seek: số ngày cần kéo dài cam kết giao hàng |
| GET/POST | `/api/dss/actions` | GET: lấy log hành động; POST: ghi hành động Apply |

---

## 1. GET `/api/dss/routes`

### Tham số query

| Tên | Kiểu | Bắt buộc | Mặc định | Mô tả |
| --- | --- | --- | --- | --- |
| `top` | int | Không | `10` | Số tuyến trả về (sắp xếp giảm dần theo số đơn trễ) |
| `year` | int hoặc `"all"` | Không | toàn bộ | Lọc theo năm mua hàng (ví dụ `2017`, `2018`). Bỏ qua hoặc `"all"` = toàn bộ dữ liệu |

### Response 200

Mảng các object, mỗi phần tử là một tuyến được gắn cờ đỏ hoặc vàng.

**Ví dụ: `GET /api/dss/routes?top=3`** (gọi thật lúc 2026-11-02T14:17, server đang chạy với dữ liệu đầy đủ)

```json
[
  {
    "route": "SP->RJ",
    "orders": 8108,
    "late_orders": 1263,
    "late_rate": 0.155772077,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": -0.03652954090613936,
        "prep": 0.21256978011707872,
        "transit": 3.602831324031545
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  },
  {
    "route": "SP->BA",
    "orders": 2295,
    "late_orders": 344,
    "late_rate": 0.1498910675,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": 0.06403229402743377,
        "prep": 0.017263710419470613,
        "transit": 7.203368835591151
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  },
  {
    "route": "SP->ES",
    "orders": 1459,
    "late_orders": 206,
    "late_rate": 0.1411925977,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": 0.021526475136161793,
        "prep": 0.09113281034664977,
        "transit": 3.1144191279304536
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  }
]
```

**Ví dụ: `GET /api/dss/routes?year=2018&top=3`**

```json
[
  {
    "route": "SP->RJ",
    "orders": 4128,
    "late_orders": 715,
    "late_rate": 0.1732073643,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": -0.0330078844315827,
        "prep": 0.1106178253377128,
        "transit": 4.680623336215499
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  },
  {
    "route": "SP->BA",
    "orders": 1262,
    "late_orders": 219,
    "late_rate": 0.1735340729,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": 0.05656705322263589,
        "prep": 0.08637883521584433,
        "transit": 7.565716131419084
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  },
  {
    "route": "SP->ES",
    "orders": 791,
    "late_orders": 142,
    "late_rate": 0.1795195954,
    "level": "amber",
    "root_cause": {
      "stage": "transit",
      "owner": "Đơn vị vận chuyển",
      "excess": {
        "approval": 0.008718393809480196,
        "prep": 0.04415984111078153,
        "transit": 4.075762412480266
      },
      "has_bottleneck": true,
      "recommendation": "Đánh giá lại đơn vị vận chuyển của tuyến hoặc điều chỉnh cam kết giao hàng."
    }
  }
]
```

### Trường response

| Trường | Kiểu | Mô tả |
| --- | --- | --- |
| `route` | string | Định danh tuyến: `"<bang người bán>-><bang khách>"` |
| `orders` | int | Số đơn hàng (unique order_id) trên tuyến |
| `late_orders` | int | Số đơn trễ (delay_days > 0) |
| `late_rate` | float | Tỷ lệ trễ = late_orders / orders |
| `level` | string | `"red"` hoặc `"amber"` |
| `root_cause.stage` | string | Giai đoạn nghẽn: `"approval"`, `"prep"`, hoặc `"transit"` |
| `root_cause.owner` | string | Bên chịu trách nhiệm giai đoạn nghẽn |
| `root_cause.excess` | object | Chênh lệch thời gian trung bình của tuyến so với toàn hệ thống (ngày) |
| `root_cause.has_bottleneck` | bool | `true` nếu ít nhất một giai đoạn vượt trung bình hệ thống |
| `root_cause.recommendation` | string | Khuyến nghị hành động |

### Mã lỗi

| HTTP | Khi nào | Ví dụ body |
| --- | --- | --- |
| 400 | `year` không phải số nguyên | `{"error": "year phải là số nguyên, ví dụ 2017 hoặc 2018"}` |
| 400 | `top` không phải số nguyên dương | `{"error": "top phải là số nguyên dương"}` |

---

## 2. GET `/api/dss/scenario`

What-if: tính tỷ lệ trễ dự báo nếu cắt giảm thời gian từng giai đoạn của một tuyến.

### Tham số query

| Tên | Kiểu | Bắt buộc | Mặc định | Mô tả |
| --- | --- | --- | --- | --- |
| `route` | string | **Có** | — | Tuyến cần phân tích, ví dụ `"SP->RJ"` |
| `approval` | float | Không | `0` | Số ngày cắt giảm giai đoạn duyệt |
| `prep` | float | Không | `0` | Số ngày cắt giảm giai đoạn người bán chuẩn bị |
| `transit` | float | Không | `0` | Số ngày cắt giảm giai đoạn vận chuyển |
| `year` | int hoặc `"all"` | Không | toàn bộ | Lọc theo năm (giống `/routes`) |

### Response 200

**Ví dụ: `GET /api/dss/scenario?route=SP->RJ`** (không cắt)

```json
{
  "orders": 8108,
  "baseline": 0.15577207696102616,
  "projected": 0.15577207696102616,
  "avoided": 0,
  "bottleneck": "transit",
  "has_bottleneck": true,
  "series": [
    {"cut": 0, "projected": 0.15577207696102616},
    {"cut": 1, "projected": 0.1419585594474593},
    {"cut": 2, "projected": 0.13159842131228416},
    {"cut": 3, "projected": 0.123334977799704},
    {"cut": 4, "projected": 0.11642821904292057},
    {"cut": 5, "projected": 0.10878145041933893}
  ]
}
```

**Ví dụ: `GET /api/dss/scenario?route=SP->RJ&prep=5`** (cắt 5 ngày prep)

```json
{
  "orders": 8108,
  "baseline": 0.15577207696102616,
  "projected": 0.12987173162308832,
  "avoided": 210,
  "bottleneck": "transit",
  "has_bottleneck": true,
  "series": [
    {"cut": 0, "projected": 0.15577207696102616},
    {"cut": 1, "projected": 0.1419585594474593},
    {"cut": 2, "projected": 0.13159842131228416},
    {"cut": 3, "projected": 0.123334977799704},
    {"cut": 4, "projected": 0.11642821904292057},
    {"cut": 5, "projected": 0.10878145041933893}
  ]
}
```

> Lưu ý: `series` luôn tính theo giai đoạn **bottleneck** (ở đây là `transit`), không theo giai đoạn được cắt trong tham số. Tham số `prep=5` ảnh hưởng `projected` và `avoided`, nhưng `series` vẫn là sensitivity của `transit`.

### Trường response

| Trường | Kiểu | Mô tả |
| --- | --- | --- |
| `orders` | int | Số đơn trên tuyến |
| `baseline` | float | Tỷ lệ trễ hiện tại |
| `projected` | float | Tỷ lệ trễ dự báo sau khi cắt |
| `avoided` | int | Số đơn trễ tránh được |
| `bottleneck` | string | Giai đoạn nghẽn (`approval`/`prep`/`transit`) |
| `has_bottleneck` | bool | Có nghẽn thực sự không |
| `series` | array | Độ nhạy của `bottleneck`: `[{"cut": 0..5, "projected": float}]` |

### Mã lỗi

| HTTP | Khi nào | Ví dụ body |
| --- | --- | --- |
| 400 | Thiếu `route` | `{"error": "thiếu tham số route"}` |
| 400 | Tuyến không tồn tại trong dữ liệu | `{"error": "không có dữ liệu cho tuyến XX->YY"}` |
| 400 | `approval`/`prep`/`transit`/`year` không phải số | `{"error": "approval/prep/transit/year phải là số hợp lệ"}` |

---

## 3. GET `/api/dss/promise`

Goal seek: tìm số ngày cần kéo dài cam kết giao hàng để tỷ lệ trễ ≤ target.

### Tham số query

| Tên | Kiểu | Bắt buộc | Mặc định | Mô tả |
| --- | --- | --- | --- | --- |
| `route` | string | **Có** | — | Tuyến cần tính |
| `target` | float | Không | `0.05` | Tỷ lệ trễ mục tiêu (0..1) |
| `year` | int hoặc `"all"` | Không | toàn bộ | Lọc theo năm |

### Response 200

**Ví dụ: `GET /api/dss/promise?route=SP->RJ&target=0.05`**

```json
{
  "extra_days": 15,
  "late_after": 0.04662062160828811
}
```

Ý nghĩa: cần kéo dài cam kết thêm **15 ngày**, khi đó tỷ lệ trễ theo định nghĩa mới còn **4.66%** (≤ 5%).

### Trường response

| Trường | Kiểu | Mô tả |
| --- | --- | --- |
| `extra_days` | int | Số ngày cần cộng thêm vào cam kết giao hàng |
| `late_after` | float | Tỷ lệ trễ ước tính sau khi áp dụng `extra_days` |

### Mã lỗi

| HTTP | Khi nào | Ví dụ body |
| --- | --- | --- |
| 400 | Thiếu `route` | `{"error": "thiếu tham số route"}` |
| 400 | Tuyến không tồn tại | `{"error": "không có dữ liệu cho tuyến XX->YY"}` |
| 400 | `target` ngoài khoảng 0..1 | `{"error": "target phải nằm trong khoảng 0..1 (ví dụ 0.05)"}` |

---

## 4. GET|POST `/api/dss/actions`

Ghi và đọc log các hành động người dùng bấm **Apply** trong giao diện.

### POST — Ghi hành động

**Request body** (JSON):

```json
{
  "action": "extend_promise",
  "route": "SP->RJ",
  "level": "amber",
  "extra_days": 15
}
```

Các trường `action` và `route` bị cắt ở 40 và 20 ký tự. Bất kỳ trường thêm nào đều được lưu vào `detail` (text JSON).

**Response 200:**

```json
{"ok": true}
```

**Ví dụ thực tế** (gọi lúc 2026-11-02T14:17):

```bash
POST /api/dss/actions
Content-Type: application/json

{"action": "extend_promise", "route": "SP->RJ", "level": "amber", "extra_days": 15}
```

Response: `{"ok": true}`

### GET — Lấy log

Trả về tối đa 50 hành động gần nhất (sắp xếp `created_at` giảm dần).

**Ví dụ sau POST ở trên:**

```json
[
  {
    "created_at": "2026-11-02T14:17:36.305Z",
    "action": "extend_promise",
    "route": "SP->RJ",
    "level": "amber",
    "detail": "{\"action\": \"extend_promise\", \"route\": \"SP->RJ\", \"level\": \"amber\", \"extra_days\": 15}"
  }
]
```

### Mã lỗi

| HTTP | Khi nào | Ví dụ body |
| --- | --- | --- |
| 400 | POST body không phải JSON hợp lệ | `{"error": "JSON không hợp lệ"}` |
| 400 | POST body là JSON nhưng không phải object | `{"error": "JSON phải là một object"}` |

---

## Tóm tắt mã lỗi chung

Tất cả lỗi trả về dạng:

```json
{"error": "<mô tả lỗi tiếng Việt>"}
```

| HTTP | Ý nghĩa chung |
| --- | --- |
| 200 | Thành công |
| 400 | Tham số thiếu, sai kiểu, hoặc không tồn tại trong dữ liệu |
| 405 | Method không đúng (ví dụ POST vào endpoint chỉ nhận GET) |

---

## Ghi chú kỹ thuật

- Dữ liệu (`cleaned_fact_orders.csv` + 3 Dim CSV) được nạp **một lần** khi module `dss.views` được import; không truy vấn DB theo request.
- Bảng `dss_action_log` trong PostgreSQL lưu log hành động; cần chạy `manage.py migrate` trước khi dùng POST.
- CORS được bật cho toàn bộ origin (`CORS_ALLOW_ALL_ORIGINS = True`) để giao diện `web/` mở bằng `file://` vẫn gọi được API.
- Lệnh khởi động: xem `reports/run_guide.md`.
