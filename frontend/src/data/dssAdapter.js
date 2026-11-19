/* Chuyển response /api/dss/* sang view model mà tab DSS dùng.
 * UI vẫn giữ nhãn "yellow" trong khi API trả "amber" — chuẩn hoá ở đây. */

const finite = (value, fallback = 0) =>
  typeof value === "number" && Number.isFinite(value) ? value : fallback;

const levelOf = (level) =>
  level === "red" ? "red" : level === "amber" ? "yellow" : "none";

const findRoute = (rows, route) =>
  (rows || []).find((row) => row.route === route) || null;

export function mapRoutes(rows = [], baseRate = 0) {
  return {
    L: finite(baseRate),
    list: rows.map((row) => ({
      route: row.route,
      n: finite(row.orders),
      k: finite(row.late_orders),
      p: finite(row.late_rate),
      lo: finite(row.ci_low),
      hi: finite(row.ci_high),
      level: levelOf(row.level),
      low: !!row.low_sample,
      uncertain: !!row.uncertain,
      rootCause: row.root_cause || null,
    })),
  };
}

export function mapAttribution(payload, route) {
  const shares = findRoute(payload?.rows, route);
  const ranked = findRoute(payload?.ranked_routes, route);
  if (!shares && !ranked) return null;
  return {
    // `rows` có share_* nhưng không có late_orders; `ranked_routes` thì ngược lại.
    n: finite(ranked?.late_orders),
    appr: finite(shares?.share_approval ?? ranked?.cause_share_approval),
    prep: finite(shares?.share_prep ?? ranked?.cause_share_prep),
    transit: finite(shares?.share_transit ?? ranked?.cause_share_transit),
    resid: finite(shares?.share_promise ?? ranked?.share_promise),
    stage: shares?.top_stage || ranked?.top_stage || null,
  };
}

/* mean_excess_* tại q=0.25 chính là mean(actual) − mean(peer P25) theo S1,
 * tức mức cắt P25 mà nút "Đặt về mức P25" của UI cần. */
export function mapDefaultCut(payload25, route) {
  const row =
    findRoute(payload25?.rows, route) || findRoute(payload25?.ranked_routes, route);
  const round = (value) => Math.round(Math.max(0, finite(value)) * 10) / 10;
  if (!row) return { appr: 0, prep: 0, transit: 0 };
  return {
    appr: round(row.mean_excess_approval),
    prep: round(row.mean_excess_prep),
    transit: round(row.mean_excess_transit),
  };
}

/* /routes chỉ trả tuyến bị gắn cờ, nên không đủ late_orders cho mọi dòng
 * Decision Brief; /attribution.ranked_routes thì có cho mọi tuyến. */
export const mapLateByRoute = (payload) =>
  Object.fromEntries(
    (payload?.ranked_routes || []).map((row) => [row.route, finite(row.late_orders)]),
  );

export const cutToQuery = (cut) => ({
  approval: cut.appr,
  prep: cut.prep,
  transit: cut.transit,
});

export function mapScenario(payload = {}) {
  return {
    orders: finite(payload.orders),
    baseline: finite(payload.baseline),
    projected: finite(payload.projected),
    avoided: finite(payload.avoided),
    bottleneck: payload.bottleneck || null,
    hasBottleneck: !!payload.has_bottleneck,
    series: (payload.series || []).map((point) => ({
      cut: finite(point.cut),
      projected: finite(point.projected),
    })),
  };
}

const ciOf = (row) => ({
  avLo: finite(row.avoided_ci_low),
  avHi: finite(row.avoided_ci_high),
});

export function mapBrief(payload = {}, lateByRoute = {}) {
  const promRows = payload.promise_actions || [];
  const promCnt = promRows.reduce(
    (acc, row) => {
      if (row.label === "tight") acc.tight += 1;
      else if (row.label === "loose") acc.loose += 1;
      else acc.ok += 1;
      return acc;
    },
    { tight: 0, ok: 0, loose: 0 },
  );

  return {
    L: finite(payload.config?.base_rate),
    parameters: payload.parameters || {},
    notes: payload.notes || [],
    routes: (payload.route_actions || []).map((row) => ({
      route: row.route,
      k: lateByRoute[row.route] ?? null,
      avoided: finite(row.avoided_orders),
      ci: ciOf(row),
      status: row.status || "",
      sub: row.action || "",
    })),
    pay: (payload.payment_actions || []).map((row) => ({
      pay: row.payment_type,
      avoided: finite(row.avoided_orders),
      ci: ciOf(row),
      status: row.status || "",
      sub: row.action || "",
    })),
    promTop: promRows.map((row) => ({
      route: row.route,
      need: finite(row.needed_days),
      net: finite(row.net_avoided_orders),
      label: row.label || "ok",
      sub: row.action || "",
    })),
    promCnt,
    sellers: (payload.seller_actions || []).map((row) => ({
      id: row.seller_id,
      n: finite(row.orders),
      k: finite(row.late_orders),
      p: finite(row.late_rate),
      excess: finite(row.estimated_excess_late_orders),
      prio: row.segment === "ưu tiên",
      sub: row.action || "",
    })),
    more: (payload.low_sample_actions || []).map((row) => ({
      route: row.route,
      n: finite(row.orders),
      k: finite(row.late_orders),
      p: finite(row.late_rate),
      level: levelOf(row.level),
      need: finite(row.needed_orders, 200),
      sub: row.action || "",
    })),
  };
}
