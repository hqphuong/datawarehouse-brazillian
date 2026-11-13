# Frontend and Backend Integration

## Scope

The Dashboard and OLAP views now request live data from the Flask API. DSS remains on its existing local sample data and calculations; its migration is intentionally deferred.

## API client and URL configuration

`frontend/src/data/api.js` is the shared JSON request layer. It provides the API operations used by these views, forwards abort signals, and turns non-success responses into readable errors. The browser requests relative `/api/...` paths.

`frontend/vite.config.js` reads `BACKEND_HOST` and `BACKEND_PORT` from the workspace-root environment and proxies `/api` to the backend for Vite dev and preview servers. The default is `http://localhost:8000`. This is the one edit outside `frontend/src`: Vite owns the proxy, and the proxy avoids exposing backend connection settings to browser code or requiring development CORS configuration. A deployed static frontend still needs its hosting server or gateway to proxy `/api` to Flask.

## Dashboard

`frontend/src/views/DashboardViewImpl.jsx` loads these requests together:

- `/api/dashboard/overview` supplies KPI data and monthly late-trend data. The year selection is sent as inclusive `from` and `to` dates.
- `/api/analytics/sla-breakdown` supplies average approval, seller preparation, and transit durations. It uses `start_date` and `end_date` query parameters.
- `/api/analytics/regions` supplies seller-state/customer-state route counts and late rates. The view constructs route labels and ranks routes with at least 100 orders; routes below 200 orders are marked as small samples.
- `/api/olap/metadata` supplies the available time range. Dashboard year options are derived from its `time_range` rather than hard-coded years.

API field names are mapped into the existing card and chart view model. The API's dashboard `delay_rate` is a ratio in the range 0–1, as expected by the existing percentage formatter.

## OLAP

`frontend/src/views/OlapViewImpl.jsx` gets states, seller states, categories, and the available month range from `/api/olap/metadata`. It posts filters and groupings to `/api/olap/query`; results are normalized from `{ columns, data }` into the existing table, chart, heatmap, and CSV view model.

Dimension and measure keys are the backend's whitelisted keys. For example, customer state uses `Dim_Location.state`, time uses `Dim_Time.month` with `time_mode` selecting the actual granularity, and late rate uses `late_rate`. The OLAP endpoint returns `late_rate` as a percentage (0–100), unlike the dashboard endpoints' ratio, so the view converts it before using the shared percentage formatter.

Cell, row-total, and column-total requests are issued in parallel because the API requires at least one grouping dimension. Grand totals for additive measures are summed. Grand totals for averages and rates are weighted by `total_orders`; for a nullable metric such as average review score this may differ slightly from a direct average over non-null values because the API does not expose that metric's non-null denominator.

The old weight, volume, and late-only filters were removed because the current OLAP request schema only accepts customer states, seller states, and categories. The OLAP labels, valid API dimension/measure keys, and preset definitions remain frontend configuration because the metadata endpoint does not expose those capabilities.

## Shared loading behavior and remaining mock data

`frontend/src/utils/utils.js` now lets `useData` resolve promises and aborts stale requests when inputs change or a component unmounts. Synchronous computations continue to work, so DSS does not need to change in this phase.

`frontend/src/data/mockData.jsx` remains for DSS only. The Dashboard and OLAP views no longer import its generated rows or local aggregation functions.

## Validation

The production frontend build and focused ESLint checks for modified source/config files pass. The full frontend lint command still reports existing errors in legacy views and components not changed for this migration. A live API smoke test could not run because `http://localhost:8000/api/health` did not respond during implementation.