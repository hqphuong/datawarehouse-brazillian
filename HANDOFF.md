# HANDOFF — Phase 2 (C1–C10 done; C9 wired)

Repo: `D:\Downloads\HK261\Data\Assignment\Brazillian` · Date: 2026-11-12 · Branch `dss-v2`
**Status: C9 complete + follow-up done. Thresholds only from `/brief.parameters`; 2016 tooltip says “too little data”; CDN requirement documented; smoke-test log row `id=4` deleted. 87 pytest + 25 Django tests pass; verifier ALL PASS.**

## 1. Done
- **C1** observed-date `dim_time` (612 rows); **C2** raw first-seen city; **C3** `normalize_location_id()` NaN guard; **C4** `dss_action_log` DDL = live 6 cols (`detail`, no `status`/`note`); **C5** signed Shapley excess; **C6** `OWNER` canonical; **C7** `root_cause()`/`RULES` kept; **C8** full-period `BASE_RATE` + `/routes` bare array; **C10** CSV backend kept + CSV↔PostgreSQL row-count test.
- **C9 real UI** (`Olist_DSS_Action_Center.html`, 365 lines) now fetches all 9 endpoints with `AbortController`; no synthetic rows; `?year=` on every data call; routes rendered `SP→RJ`.
- **C9 demo** split to `Olist_DSS_Action_Center.sample.html`: “Sample data” badge, own 1,400-row generator, CONFIG `10/30/30`; real file has no demo data.
- **C9 signed Shapley**: `Math.max(0, …)` removed; `SignedBar` centres at 0; negative φ draws left (verified `MG→BA` = `-0,4%`).
- **C9 thresholds/config**: thresholds are read in **one place only**, from `/brief.parameters` (`min_orders`, `low_sample_threshold`, `seller_min_orders`); `base_rate` is read only from `/brief.config`. No other endpoint supplies thresholds. If `/brief` fails the UI shows an error, never demo/fallback.
- **C9 low-sample badge**: derived from `order_routes < parameters.low_sample_threshold` only. `ranked_routes.low_sample` is relative to `min_orders=30`, is always `false` after filtering, and **must not be displayed**.
- **C9 year filter**: options `all/2017/2018`; tooltip explicitly says 2016 has **too little data** (263 orders / 265 order-routes, 0 routes at `min_orders=100`). No 2016 option.
- **C9 UX**: “order-route” unit in popover; Promise policy + Seller scorecard inside collapsed “Phân tích hỗ trợ”; 5 brief groups with per-row “Ghi nhận khuyến nghị”; disabled label “Đã ghi nhận (không thực thi)”; `?dev=1`, fake-error button and `setTimeout` removed.
- **C9 CDN (C9-d B):** UI still loads Tailwind CDN, React/Babel from unpkg and Google Fonts. Offline/blocked CDN = blank UI. Documented in `REPORT_FIXES.md` §6.1/7.2; not vendored.
- **C9 empty route list**: unreachable with 2017/2018; verified by mocking an empty `/attribution` response. **Tested with a mock only.**
- **Docs:** `REPORT_FIXES.md` adds §5.6.3 API table (thresholds from `parameters`, `base_rate` from `config`), §6.4 wired flow, §6.1/7.2 CDN note, §6.4/7.1 2016 note, C10 extra live column, C4 DDL.

## 2. Commands run + counts
| Command | Result |
|---|---|
| `python -m pytest -q` | **87 passed** (27.18 s) |
| `backend\env\Scripts\python.exe manage.py test` | **25 tests OK** (59.84 s); PowerShell exit 1 = stderr noise |
| `backend\env\Scripts\python.exe verify_report_numbers.py` | **ALL PASS** (orders 96,455 · order-routes 95,591 · L 8.1556% · 14 flags 6/8 · sensitivity `[14,14,21,21,10,6]` · L1–L3 · 165/226 · 500/500 · cut 2,352/2,878 · promise 3,751/884/2,867 · sellers 252/357/2,339 · backtest 16/19, +0.082826) |
| Headless Chrome (1280×900) | initial `all`; `2018` shows 12 red/2 amber; `2017` shows 2/4; base stays **8,2%**; low-sample `MA→SP`; zero-late `RS→SC`; blocked `/brief` error; mocked empty state; POST + reload; emulated 390 px |
| `psql` | `dss_action_log` = **0 rows** (smoke-test row `id=4` deleted after SELECT; §7 C9-b); `fact_delivery_sla` = 110,173 |

Browser checks actually run: `all/2017/2018`, route select, popover, support open, 5-col seller header, signed negative bar, blocked `/brief` error, mocked empty `attribution` empty state, one POST + log reload, 390 px layout (desktop table hidden, mobile list visible, no horizontal overflow). **Not run:** real phone, Firefox/Safari, slider drags, target 10%, seller segment tab clicks, POST failure path.

## 3. Live schema compact
| Table | Rows | Notes |
|---|---|---|
| `dim_time` | 612 | Only dates that have orders; `time_id=yyyymmdd`. |
| `dim_location` | 15,078 | One row per raw zip; first-seen city; mean lat/lng. |
| `dim_product` | 32,951 | OK. |
| `dim_seller` | 3,095 | OK. |
| `fact_delivery_sla` | 110,173 | Grain order_id+order_item_id; stale unused `handoff_slack_days float8`. |
| `dss_action_log` | 0 | 6 cols; C9 POST smoke-test row deleted (§7 C9-b). |

## 4. Real numbers vs report
| Metric | Recomputed | Report | Match |
|---|---|---|---|
| Delivered orders / order-routes raw→DSS | 96,455 · 96,981→95,591 (excl. 1,390 = 1.4333%) | same | ✓ |
| L full period · red 2.0L · amber 1.5L | 8.1556% · 16.31% · 12.23% | same | ✓ |
| Flagged routes all / 2017 / 2018 (fixed L) | 14 (6/8) · 6 (2/4) · 14 (12/2) | same | ✓ |
| Shapley L1/L2/L3 · transit share q=0.5 | pass · 69.8820% point / 69.9162% bootstrap | same | ✓ |
| Cut top-5/10 · Promise GROSS/new/NET | 2,352/2,878 · 3,751/884/2,867 | same | ✓ |
| Sellers prio/stable/more | 252/357/2,339 (2,948 total, 609 scored) | same | ✓ |
| Backtest `min_orders=30` | 16/19; weighted +0.082826 | same | ✓ |

No number was rounded/faked. UI shows 8,2% because `BASE_RATE` is full-period even under `?year=` (C8).

## 5. API contract (base `/api/dss/`; GET except `/actions`)
| Endpoint | Params | Trimmed sample |
|---|---|---|
| `/routes` | `year?`, `top?=10` | `[{"route":"SP->MA","orders":480,"late_rate":0.21875,"level":"red","ci_low":0.184,"low_sample":false,"uncertain":false,"root_cause":{"stage":"transit","owner":"Đơn vị vận chuyển","has_bottleneck":true}}]` |
| `/scenario` | `route*`, `approval?`, `prep?`, `transit?`, `year?` | `{"orders":480,"baseline":0.21875,"projected":0.12,"avoided":47,"bottleneck":"transit","has_bottleneck":true,"series":[{"cut":0,"projected":0.12}],"config":{...}}` |
| `/promise` | `route*`, `target?=0.05`, `year?` | `{"extra_days":6,"late_after":0.049}` |
| `/actions` | POST `{action,route,level,detail}`; GET last 50 | POST `{"ok":true}` · GET `[{"created_at":"...","action":"recommendation","route":"SP->SP","level":"red","detail":"{...}"}]` |
| `/brief` | `year?` | `{"route_actions":[...],"payment_actions":[...],"promise_actions":[...],"promise_summary":{...},"seller_actions":[...],"low_sample_actions":[...],"low_sample_check":[...],"notes":[...],"parameters":{"min_orders":100,"low_sample_threshold":200,"seller_min_orders":30},"config":{"base_rate":0.081556,"base_rate_label":"overall rate of the full period","grain":"order-route"}}` |
| `/attribution` | `q?=0.5` (only 0.25/0.5), `year?` | `{"q":0.5,"grain":"order-route","rows":[{"route":"PR->AL","orders":37,"cause_share_transit":1.0}],"ranked_routes":[{"route":"PR->AL","order_routes":37,"late_orders":13,"low_sample":false}],"systemwide":{...},"invariants":{"passed":true},"config":{...}}` |
| `/promise-policy` | `year?` | `{"label":"...","rows":[{"route":"SP->SP","service_level":0.85,"needed_days":13,"avoidable_orders":12,"new_late_orders":3,"net_avoided_orders":9}],"config":{...}}` |
| `/sellers` | `year?` | `{"summary":{"n_sellers_scored":609},"rows":[{"seller_id":"...","orders":42,"late_rate":0.12,"bad_review_rate":0.18,"segment":"ưu tiên","level":"red"}],"config":{...}}` |
| `/portfolio` | `year?` | `{"summary":{"top_seller_share_late_orders":0.21},"segments":[{"segment":"ưu tiên","n_sellers":252,"late_orders":1000,"late_orders_share":0.4}],"top_sellers":[...],"coverage_50_percent":{"k":252,...},"config":{...}}` |

Errors: `400 {"error":"..."}`. **`/routes` is array-only**; UI reads `config` only from `/brief`. Mapping used: route list from `/attribution.ranked_routes` + flags/CI/root cause from `/routes`; low-sample badge from `order_routes < parameters.low_sample_threshold`; cause card from `cause_share_*`/`share_promise`; scenario fields as returned; promise/policy; portfolio segments + sellers rows; brief 5 action groups.

## 6. Threshold locations
| Setting | Where |
|---|---|
| `red=2.0`, `amber=1.5` | `etl/dss_models.py:492-493`, `:584-585`, `:667-668`; `etl/dss_eval.py:494-499` |
| `min_orders=100` | `etl/dss_models.py:494`, `:579`, `:663`; `etl/dss_brief.py:381`; `etl/dss_attrib.py:952`, `:624`, `:1055` |
| `low_sample=200` | hard-coded `etl/dss_models.py:548`; params `:580`; `etl/dss_brief.py:383` |
| `seller_min=30` | `etl/dss_models.py` scorecard; `etl/dss_brief.py:382`; `backend/dss/views.py:304`, `:326-328` |
| Full-period base rate | `backend/dss/views.py:23`, `:26-32`, `:129`, `:222-224` |
| API overrides | `backend/dss/views.py:223` (`n_boot=300, seed=42`) |
| UI thresholds (single source) | `Olist_DSS_Action_Center.html:150` (`params.min_orders`), `:221-222` (`low_sample_threshold`), `:356` (thresholds text) — all from `/brief.parameters` |
| UI base rate | `Olist_DSS_Action_Center.html:283` — `cfg.base_rate`/label from `/brief.config` |
| Signed bars (no clip) | `Olist_DSS_Action_Center.html:118` (`SignedBar`), `:290` (call), `:221` (low-sample badge) |

`ranked_routes.low_sample` is computed relative to `min_orders=30` and is always
`false` after filtering; it is **not** the 200 threshold and must **not** be
displayed. The badge uses `order_routes < parameters.low_sample_threshold`.

## 7. Resolved decisions
| ID | Decision | Result |
|---|---|---|
| C1–C8, C10 | earlier wording/data choices | Resolved in Phase 1. |
| **C9-a (A)** | Thresholds come from `/brief.parameters` only, in one place in the UI. | No API change; any text implying thresholds come from `config` fixed. |
| **C9-b** | Delete only the POST smoke-test row, identified by id/note, after showing the SELECT. | `SELECT` showed `id=4` (`SP->SP`, recommendation, 10:36:17); `DELETE … WHERE id = 4` → 1 row; table now 0 rows, no other rows touched. |
| **C9-c (A)** | Badge derived from `order_routes < parameters.low_sample_threshold`. | `ranked_routes.low_sample` no longer read; documented as always `false`/not displayable. |
| **C9-d (B)** | Keep CDN. | `REPORT_FIXES.md` §6.1/7.2 now says the UI needs Internet for Tailwind/Babel/React/fonts. |
| **C9-e (A)** | No 2016 option. | Tooltip says 2016 has too little data; empty route-list state was **tested with a mock only**. |

## 8. Remaining limits
- UI needs Internet for CDN assets; offline/blocked CDN = blank UI.
- Empty route list is not reachable with real 2017/2018 data; verified only by mocking an empty `/attribution`.
- Not tested: real phone, Firefox/Safari, slider drags, target 10%, seller segment tab clicks, POST failure path.
- Branch `dss-v2` is not pushed. Untracked by design: `CO4031_BaoCao.zip`, `main.pdf`.
