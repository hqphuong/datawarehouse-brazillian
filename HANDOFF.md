# HANDOFF — Phase 1 (C1–C8, C10 implemented; C9 pending)

Repo: `D:\Downloads\HK261\Data\Assignment\Brazillian` · Date: 2026-11-12 · Branch `dss-v2` · **Status: STOP — C9 blocked on §8.4 approval.** No commits made yet.

## 1. Done
- **C1** kept observed-date `dim_time` (612 rows); wording fix queued in `REPORT_FIXES.md` §4.2.2.
- **C2** kept raw first-seen city; evidence collected (below); wording fix in `REPORT_FIXES.md` §3.2.
- **C3** added `normalize_location_id()` (`etl/transform_rules.py`): `isna()` guard *before* `zfill(5)`, clear `ValueError`; applied in `etl/fact_delivery_sla.py`, `etl/dim_location.py`, `etl/dim_seller.py`; 3 tests added.
- **C4** added `dss_action_log` DDL to `sql/create_tables.sql` matching live (`id, created_at, action, route, level, detail`); no column renames; no `status`/`note`.
- **C5** kept signed Shapley excess; formula/residual wording fix in `REPORT_FIXES.md` §5.3; no numbers changed.
- **C6** code `OWNER` canonical; backend `/brief` returns `owner`; wording fix in `REPORT_FIXES.md` §2.2/§5.1.
- **C7** kept `root_cause()`/`RULES`; exact `/routes` + `/scenario` fields documented (§5); confirmed UI cause card uses Shapley only.
- **C8** added `overall=None` to `route_priority`, `low_sample_targets`, `route_flag_check`, `decision_brief`/`_low_sample_actions`; `BASE_RATE`/`_config()` in `backend/dss/views.py`; `config` exposed on 6 object endpoints (not `/routes`, see §7).
- **C10** kept CSV backend; row-count test CSV↔PostgreSQL added in `tests/test_warehouse_schema.py`; deviation wording in `REPORT_FIXES.md` §5.1/§6.3.
- **C9** *not started* — UI still synthetic 1,400 rows, thresholds 10/30/30, no `fetch`.
- Created `verify_report_numbers.py` (recomputes all headline numbers; exits 1 on mismatch) and `REPORT_FIXES.md` (exact Vietnamese wording per section).

## 2. Commands run + counts
| Command | Result |
|---|---|
| `python -m pytest tests/test_transform_rules.py tests/test_warehouse_schema.py tests/test_dss_models.py` | **44 passed** (4.45 s) |
| `python -m pytest` (repo root, full) | see §8.5 — rerun pending after doc update |
| `backend\env\Scripts\python.exe manage.py test` | **25 tests OK** (55.03 s); PowerShell exit 1 = stderr noise |
| `python verify_report_numbers.py` | **ALL PASS** (orders 96,455 · order-routes 96,981→95,591 · excluded 1,390/1.4333% · L 8.1556% · 14 flags 6/8 · sensitivity `[14,14,21,21,10,6]` · L1–L3 · 165/226 · 500/500 · cut 2,352/2,878 · promise 3,751/884/2,867 · sellers 252/357/2,339 · backtest 16/19, +0.082826) |
| `psql "\d+ dss_action_log"` | cols `id bigint identity, created_at timestamptz NOT NULL, action varchar(40), route varchar(20), level varchar(10), detail text`; 0 rows |

C8 year behaviour (fixed `BASE_RATE` vs year-local L):
| Year | rows | L(year) | fixed-L flags | year-L flags |
|---|---|---|---|---|
| 2017 | 43,498 | 6.6026% | 6 (2 red/4 amber) | 10 (5/5) |
| 2018 | 51,828 | 9.4929% | 14 (12/2) | 12 (7/5) |

C2 evidence (15,078 zips): 10 have first-seen city ≠ mode; 3 non-ASCII; 0 uppercase; 0 leading/trailing spaces; 162 missing coords; city is **not** used by route/distance; 33 zip prefixes map to >1 state (state re-picking would change routes).

## 3. Live schema compact
| Table | Rows | Notes |
|---|---|---|
| `dim_time` | 612 | Only dates that have orders; `time_id=yyyymmdd`. |
| `dim_location` | 15,078 | One row per raw zip; first-seen city; lat/lng = mean per zip. |
| `dim_product` | 32,951 | OK. |
| `dim_seller` | 3,095 | OK. |
| `fact_delivery_sla` | 110,173 | Grain order_id+order_item_id; still has stale `handoff_slack_days float8` (not in ETL/DDL/model). |
| `dss_action_log` | 0 | Now in `sql/create_tables.sql`; 6 cols as §2. |

## 4. Real numbers vs report
| Metric | Recomputed | Report | Match |
|---|---|---|---|
| Delivered orders / order-routes raw→DSS | 96,455 · 96,981→95,591 (excl. 1,390 = 1.4333%) | same | ✓ |
| L (full period) · red 2.0L · amber 1.5L | 8.1556% · 16.31% · 12.23% | same | ✓ |
| Flagged routes | 14 (6 red / 8 amber) | same | ✓ |
| Sensitivity `min_orders=100` (6 pairs) | `14, 14, 21, 21, 10, 6` | 6–21 | ✓ |
| Shapley L1/L2/L3 | pass | pass | ✓ |
| Transit share q=0.5 | 69.8820% point / 69.9162% bootstrap | both quoted | ✓ |
| Route / system bootstrap transit #1 | 165/226 · 500/500 | same | ✓ |
| Feasible cut top-5 / top-10 | 2,352 / 2,878 | same | ✓ |
| Promise GROSS / new-late / NET | 3,751 / 884 / 2,867 (130 of 1,157 cells; 83,104 order-routes) | same | ✓ |
| Sellers prio/stable/more | 252 / 357 / 2,339 (2,948 total, 609 scored) | same | ✓ |
| Backtest `min_orders=30` | 16/19; weighted +0.082826 | same | ✓ |

Divergences are **wording only** (C1/C2/C5/C6/C10) → `REPORT_FIXES.md`; no number was rounded or faked.

## 5. API contract (base `/api/`, GET except `/actions`)
| Endpoint | Params | Trimmed sample |
|---|---|---|
| `/routes` | `year?`, `top?=10` | `[{"route":"SP->RJ","orders":8016,"late_orders":1259,"late_rate":0.1571,"level":"amber","ci_low":...,"uncertain":true,"low_sample":false,"root_cause":{"stage":"transit","owner":"Đơn vị vận chuyển","excess":0.4,"has_bottleneck":true,"recommendation":"..."}}]` |
| `/scenario` | `route*`, `approval?`, `prep?`, `transit?`, `year?` | `{"orders":8016,"baseline":0.157,"projected":0.13,"avoided":123,"bottleneck":"transit","has_bottleneck":true,"series":[{"cut":0,"projected":0.13}],"config":{"base_rate":0.081556,"base_rate_label":"overall rate of the full period","grain":"order-route"}}` |
| `/promise` | `route*`, `target?=0.05`, `year?` | `{"extra_days":6,"late_after":0.049}` |
| `/actions` | POST `{action,route,level,detail...}`; GET last 50 | POST `{"ok":true}` · GET `[{"created_at":"...","action":"...","route":"SP->SP","level":"red","detail":"{...}"}]` |
| `/brief` | `year?` | `{"route_actions":[...],"payment_actions":[...],"promise_actions":[...],"promise_summary":{...},"seller_actions":[...],"low_sample_actions":[...],"low_sample_check":[...],"notes":[...],"parameters":{...},"config":{...}}` |
| `/attribution` | `q?=0.5` (only 0.25/0.5), `year?` | `{"q":0.5,"design":"Shapley attribution theo peer group","grain":"order-route","rows":[...],"ranked_routes":[...],"systemwide":{"orders":95591,"late_rate":0.0816,"shares_in_late_orders":{"share_transit":0.6988,...}},"invariants":{"passed":true},"config":{...}}` |
| `/promise-policy` | `year?` | `{"label":"mức phục vụ, không phải khuyến nghị đặt promise","note":"...","rows":[{"route":"SP->SP","service_level":0.85,"needed_days":13,"avoidable_orders":12,"new_late_orders":3,"net_avoided_orders":9}],"config":{...}}` |
| `/sellers` | `year?` | `{"summary":{"n_sellers_scored":609,"segment_counts":{...}},"rows":[{"seller_id":"...","orders":42,"late_rate":0.12,"wilson_low":...,"level":"red","low_sample":false}],"note":"...","config":{...}}` |
| `/portfolio` | `year?` | `{"summary":{...},"segments":[...],"top_sellers":[...],"coverage_50_percent":{...},"note":"...","config":{...}}` |

Errors: `400 {"error":"..."}` via `_bad()`. C7 detail: `/scenario` uses only `root_cause["stage"]`→`bottleneck` and `root_cause["has_bottleneck"]`, discards `recommendation`. UI cause card (`Olist_DSS_Action_Center.html:317-324`) uses Shapley `att/topSt/shares` only.

## 6. Threshold locations
| Setting | Where |
|---|---|
| `red=2.0`, `amber=1.5` | `etl/dss_models.py:492-493` (`route_priority`), `:584-585` (`low_sample_targets`), `:667-668` (`route_flag_check`); `etl/dss_eval.py:494-499` |
| `min_orders=100` | `etl/dss_models.py:494`, `:579`, `:663`; `etl/dss_brief.py:381`; `etl/dss_attrib.py:952`, `:624`, `:1055` |
| `low_sample=200` | **hard-coded** `etl/dss_models.py:548`; also param `:580`, `etl/dss_brief.py:383` |
| `seller_min=30` | `etl/dss_models.py` scorecard; `etl/dss_brief.py:382`; `backend/dss/views.py:304`, `:326-328` |
| Full-period base rate | `backend/dss/views.py:23` (`BASE_RATE`), `:26-32` (`_config()`), `:129` (`/routes`), `:222-224` (`/brief`) |
| API overrides | `backend/dss/views.py:223` (`n_boot=300, seed=42`) |
| UI (still sample mode) | `Olist_DSS_Action_Center.html:58` (`10 / 30 / 30`); 2.0/1.5 at `:69`; synthetic 1,400 rows at `:38` |

## 7. Open conflicts
| ID | Conflict | Option A | Option B | Impact |
|---|---|---|---|---|
| C1 | `dim_time` 612 observed dates vs report “continuous calendar” | Build calendar (~700+) | Keep observed | A needs ETL/test rewrite; B matches live + tests ✓ done |
| C2 | city raw first-seen vs report “mode + strip/lowercase” | Normalize | Keep raw ✓ | A relabels 10 zips only; no route/distance effect |
| C3 | zfill on NaN → `"00nan"` | Guard NaN ✓ | Keep | Fixed; 0 affected rows today |
| C4 | `dss_action_log` DDL missing; `status`/`note` vs `detail` | Match Appendix A | Match live/code ✓ | DDL synced; `status` would need new nullable column |
| C5 | Shapley signed excess vs report `min` cap | Cap | Keep signed ✓ | A changes transit share + CI → breaks §4 |
| C6 | owner labels differ | Code `OWNER` ✓ | Per-layer | Text only |
| C7 | `root_cause()` used by 2 endpoints | Remove | Keep ✓ | No numeric effect |
| C8 | L on year-filtered frame | Full-period `BASE_RATE` ✓ | Per-year | B changes labels under `?year=` (2017: 10 vs 6; 2018: 12 vs 14) |
| C9 | UI synthetic 1,400 rows, no `fetch`, clips Shapley ≥0 (`:74`) | Wire to 9 endpoints | Keep demo | A changes every displayed number; needs signed-Shapley alignment |
| C10 | Backend reads CSV not PostgreSQL | Read DB | Keep CSV ✓ | DB path risks `handoff_slack_days` drift |
| **C8b** | **`/routes` returns bare array → cannot add top-level `config` without breaking contract/tests** | **Add `config` (wrap in object)** | **Leave `/routes` array-only** | A breaks UI + `test_routes_*`; B leaves 1 endpoint without `config` |

## 8. Questions — recommended default in **bold**
1. **C8b:** add `config` to `/routes` by wrapping `{rows, config}` (A) or leave it array-only (B)? → **B** now; UI can hardcode/`/brief` for label, or do A as a versioned change in C9.
2. **C4:** add optional `dss_action_log.status` (default `'recorded'`) (A) or keep 6 columns (B)? → **B**; add later as new nullable column if needed.
3. **C10:** drop stale live `fact_delivery_sla.handoff_slack_days` (A) or leave it (B)? → **B** now (no code reads it); separate migration later.
4. **C9:** approve API→UI field mapping before I edit the UI — `/routes` row → route card (route, orders, late_orders, late_rate, level, ci_low/high, uncertain, low_sample, root_cause.stage/owner), `/attribution` → cause card (`top_stage`, `phi_*` shares, signed), `/scenario` → what-if, `/promise` → goal-seek, `/brief` → actions, `/sellers`+`/portfolio` → seller panel, `/actions` → log. **Approve or amend?** → **approve as listed**.
5. Re-run full `pytest` + `manage.py test`, then make small commits (ETL/C3; C8; C4/C10; docs) — **confirm commit grouping?** → **yes**.
