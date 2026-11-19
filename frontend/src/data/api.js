const API_BASE = "/api";

async function request(path, { method = "GET", query, body, signal } = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  const response = await fetch(url, {
    method,
    signal,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.message || `API request failed (${response.status})`);
  }
  return data;
}

export const getOlapMetadata = (signal) =>
  request("/olap/metadata", { signal });

export const getDashboardOverview = (query, signal) =>
  request("/dashboard/overview", { query, signal });

export const getSlaBreakdown = (query, signal) =>
  request("/analytics/sla-breakdown", { query, signal });

export const getRegions = (query, signal) =>
  request("/analytics/regions", { query, signal });

export const postOlapQuery = (body, signal) =>
  request("/olap/query", { method: "POST", body, signal });

/* ---------- DSS ---------- */

const dssQuery = (year) => (year && year !== "all" ? { year } : {});

export const getDssRoutes = (year, top = 10, signal) =>
  request("/dss/routes", { query: { ...dssQuery(year), top }, signal });

export const getDssBrief = (year, signal) =>
  request("/dss/brief", { query: dssQuery(year), signal });

export const getDssAttribution = (year, q = 0.5, signal) =>
  request("/dss/attribution", { query: { ...dssQuery(year), q }, signal });

export const getDssScenario = ({ year, route, cut }, signal) =>
  request("/dss/scenario", {
    query: {
      ...dssQuery(year),
      route,
      approval: cut.appr,
      prep: cut.prep,
      transit: cut.transit,
    },
    signal,
  });

export const getDssPromise = ({ year, route, target }, signal) =>
  request("/dss/promise", {
    query: { ...dssQuery(year), route, target },
    signal,
  });

export const getDssPromisePolicy = (year, signal) =>
  request("/dss/promise-policy", { query: dssQuery(year), signal });

export const getDssSellers = (year, signal) =>
  request("/dss/sellers", { query: dssQuery(year), signal });

export const getDssPortfolio = (year, signal) =>
  request("/dss/portfolio", { query: dssQuery(year), signal });

export const getDssActions = (signal) => request("/dss/actions", { signal });

export const postDssAction = (body, signal) =>
  request("/dss/actions", { method: "POST", body, signal });