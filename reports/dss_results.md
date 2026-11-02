# DSS Evaluation Results (Bước 9 / Giai đoạn 5)

## 1) Test results
**Pytest (repo root):**
```bash
.\backend\env\Scripts\python.exe -m pytest -q
```
Result: **16 passed in 4.87s** (includes existing model tests, new `tests/test_dss_eval.py`).

**Django API tests (dss app):**
```bash
cd backend
..\backend\env\Scripts\python.exe manage.py test dss -v 2
```
Result: **12 tests OK**.

## 2) Backtest (tuyến gắn cờ kỳ t vs tỷ lệ trễ kỳ t+1)
**Method:** For each period `t` (from 2017 onward, `min_period_orders=500`), `route_priority` is run on data of period `t` with selected `min_orders`. Routes flagged as red/amber are compared against others in period `t+1`. Periods with no flags or too few flagged orders are recorded but not counted in `periods_evaluated`.

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

**Summary:** `periods_considered=19, periods_evaluated=19, periods_without_flags=0, higher_periods=16/19 (0.842), weighted_diff=0.08138, mean_diff=0.07129`

**Giải thích công thức `weighted_diff` (bổ sung A1):**

Hai cách tính đã được kiểm tra độc lập (`.\backend\env\Scripts\python.exe -c "..."`):

| Cách | Công thức | Kết quả |
| --- | --- | --- |
| **Cách 1 (số chính)** | `np.average(diff, weights=total_orders)` — trọng số = **tổng số đơn kỳ t+1** | **+8.14 pp** |
| Cách 2 (tham khảo) | `np.average(diff, weights=flagged_orders)` — trọng số = **số đơn thuộc nhóm gắn cờ ở kỳ t+1** | +10.32 pp |
| Không trọng số | `diff.mean()` | +7.13 pp |

`total_orders = flagged_orders + other_orders` (toàn bộ đơn của kỳ t+1, không phân biệt nhóm).

**Cách 1 là số chính** vì:
- Trung lập hơn: kỳ nào có nhiều đơn hơn thì ước lượng tỷ lệ trễ chính xác hơn, nên nên được đặt trọng số cao hơn.
- Cách 2 phụ thuộc vào số tuyến được gắn cờ ở mỗi kỳ — kỳ nhiều tuyến gắn cờ → flagged_orders lớn → trọng số cao hơn, có thể gây nhiễu.
- Cách 1 (8.14 pp) và Cách 2 (10.32 pp) cùng chiều và cùng kết luận (nhóm gắn cờ trễ hơn đáng kể); Cách 1 bảo thủ hơn nên phù hợp để báo cáo.

`weighted_diff_flagged` đã được thêm vào `summary` trong `etl/dss_eval.py` để dễ đối chiếu.

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

**Selection for the monthly backtest: `min_orders=30`.** Reason: the data is split by month, so `min_orders=100` leaves **6 of 19** periods with no flagged routes at all (only 13 periods can be evaluated), and `min_orders=50` leaves 2 periods unevaluable. `min_orders=30` still leaves a meaningful minimum sample (30 orders per route per month) while covering **19/19** periods; the flagged group has a higher next-period late rate in **16/19** periods, with a weighted difference of **+0.0814** (8.14 percentage points). This makes the backtest more representative across the year instead of only the high-volume months. The production `route_priority` keeps its default `min_orders=100` because it runs on the full (not monthly) dataset and deliberately avoids small-route noise; the lower threshold is only for the monthly backtest.

**Where the backtest does NOT support the flag (reported explicitly):**
- `201701 -> 201702`: flagged group 2.27% vs rest 3.25% (`diff = -0.00975`, -0.98 pp).
- `201708 -> 201709`: flagged group 3.53% vs rest 5.35% (`diff = -0.01818`, -1.82 pp).
- `201807 -> 201808`: flagged group 1.21% vs rest 10.54% (`diff = -0.09328`, -9.33 pp). This last period is the clearest counterexample: the flagged group is small (165 orders) and next-month rates are volatile, so the one-step signal fails there. Overall 16/19 periods support the flag, but this is a monthly association, not a guarantee for every month.

## 3) Threshold sensitivity (full year data)
| min_orders | red | amber | flagged_routes | red_routes | amber_routes |
| --- | --- | --- | --- | --- | --- |
| 50 | 2.0 | 1.5 | 22 | 7 | 15 |
| 50 | 1.5 | 1.25 | 30 | 22 | 8 |
| 100 | 2.0 | 1.5 | 14 | 6 | 8 |
| 100 | 1.5 | 1.25 | 21 | 14 | 7 |
| 200 | 2.0 | 1.5 | 11 | 4 | 7 |
| 200 | 1.5 | 1.25 | 16 | 11 | 5 |

## 4) Top 3 routes (including SP->RJ)
All from `route_priority` (default params).

| route | orders | late_orders | baseline | level | stage | has_bottleneck | excess_approval | approval_cut_1 | approval_cut_3 | approval_cut_5 | approval_goal_cut | excess_prep | prep_cut_1 | prep_cut_3 | prep_cut_5 | prep_goal_cut | excess_transit | transit_cut_1 | transit_cut_3 | transit_cut_5 | transit_goal_cut | promise_days | promise_late_after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP->RJ | 8108 | 1263 | 0.155772 | amber | transit | True | -0.036530 | 0.152195 | 0.151332 | 0.151332 | — | 0.212570 | 0.143809 | 0.134558 | 0.129872 | — | 3.602831 | 0.141959 | 0.123335 | 0.108781 | — | 15 | 0.046621 |
| SP->BA | 2295 | 344 | 0.149891 | amber | transit | True | 0.064032 | 0.144227 | 0.143355 | 0.142484 | — | 0.017264 | 0.132898 | 0.118954 | 0.113290 | — | 7.203369 | 0.128976 | 0.105447 | 0.086275 | 10 | 10 | 0.047059 |
| SP->ES | 1459 | 206 | 0.141193 | amber | transit | True | 0.021526 | 0.137080 | 0.135024 | 0.135024 | — | 0.091133 | 0.126114 | 0.111720 | 0.108293 | — | 3.114419 | 0.122687 | 0.097327 | 0.078821 | 9 | 9 | 0.044551 |

**Notes:** `goal_seek_cut` returns `None` if target not reached within `max_days=10` (step 0.5). For SP->RJ/approval/prep/transit none reached 5% with cuts <=10 (consistent with transit bottleneck being large). `goal_seek_promise` matches earlier verification.

## 5) Impact of negative times
**Fact-level counts (from `cleaned_fact_orders.csv`):**
- `seller_prep_time_days` negative: **1542** rows
- `carrier_transit_time_days` negative: **50** rows
- `approval_time_days` negative: **0**
- either prep/transit negative: **1592** (0 overlap where both negative)

**At model level (1 row = (order_id, route), grouped):**
- Rows with any negative (prep<0 or transit<0): **1390** out of **96981** (removed if filtered)
- `prep<0`: **1361**, `transit<0`: **29**

**Comparison for top 3 routes (clean = drop rows where `prep>=0 and transit>=0`; system means also change):**
| route | removed_rows | orders_keep | orders_drop | baseline_keep | baseline_drop | stage_keep | stage_drop | has_bottleneck_keep | has_bottleneck_drop | excess_approval_keep | excess_approval_drop | excess_prep_keep | excess_prep_drop | excess_transit_keep | excess_transit_drop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SP->RJ | 92 | 8108 | 8016 | 0.155772 | 0.157061 | transit | transit | True | True | -0.036530 | -0.031929 | 0.212570 | 0.204748 | 3.602831 | 3.619521 |
| SP->BA | 28 | 2295 | 2267 | 0.149891 | 0.149978 | transit | transit | True | True | 0.064032 | 0.064307 | 0.017264 | 0.013544 | 7.203369 | 7.169286 |
| SP->ES | 16 | 1459 | 1443 | 0.141193 | 0.142065 | transit | transit | True | True | 0.021526 | 0.026753 | 0.091133 | 0.084861 | 3.114419 | 3.102322 |

**Conclusion:** Removing negative-time rows changes magnitudes of excess slightly but **does not change bottleneck identification** (all three remain transit bottleneck) in this dataset. The values look plausible as data quality artifacts (small fraction of rows). The model as written treats stage times as given; filtering is a data-cleaning choice but the core diagnosis holds.

## 6) Parameters chosen and rationale
- **route_priority production defaults kept:** `red=2.0, amber=1.5, min_orders=100, top=10` (per group decision).
- **Backtest min_orders = 30:** chosen for monthly evaluation only. At `min_orders=100`, 6/19 periods have no flagged route (only 13 evaluable); at 50, 2/19. `30` gives 19/19 coverage while still requiring at least 30 orders per route per month; 16/19 periods flagged group has higher next-period late rate, weighted +8.14 pp. The production default remains 100 because it runs on the full dataset.
- **Backtest window:** start from 2017 (drop 2016 sparse months), require `min_period_orders>=500` in t and t+1, use next calendar month.
- **Top routes:** default `route_priority` gives SP->RJ/BA/ES as top three (all flagged) with transit bottleneck.

## 7) Limitations observed
- **Early months sparse:** 2016 has tiny counts; several periods have 0 flagged routes when using stricter `min_orders` (e.g. 201701-201704 at 100). Backtest explicitly excludes/marks these.
- **Monthly granularity limits sample size:** even with `min_orders=30` we get small flagged sets in some months.
- **Negative stage times exist:** ~1.4k (order,route) rows affected; diagnosis remains consistent after removal but magnitudes shift.
- **`goal_seek_cut` often cannot reach 5% within 10 days:** For large transit excess (especially SP->BA) cutting stage times alone may not suffice; promise extension is more feasible in those cases.
- **Model is descriptive/what-if:** Backtest shows flagged routes tend to have higher late rate in next period (supportive in most evaluated periods) but is not a causal proof.

## 8) Commands run (for reproducibility)
```bash
# Model/base checks
.\backend\env\Scripts\python.exe -c "from etl import dss_models as M; o=M.load_orders(); print(len(o), o.is_late.mean())"

# Backtest + tables
.\backend\env\Scripts\python.exe etl/dss_eval.py > reports/dss_eval_raw.txt

# Tests
.\backend\env\Scripts\python.exe -m pytest -q
cd backend && ..\backend\env\Scripts\python.exe manage.py test dss -v 2
```

Files created/modified in Giai đoạn 5: `etl/dss_eval.py`, `tests/test_dss_eval.py`, `reports/dss_eval_raw.txt`, `reports/dss_results.md` (this file).
No Django/giao diện files modified.
