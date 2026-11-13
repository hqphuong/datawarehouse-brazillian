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