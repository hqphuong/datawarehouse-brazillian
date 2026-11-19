import { useEffect, useRef, useState } from "react";
import {
  getDssActions,
  getDssAttribution,
  getDssBrief,
  getDssPortfolio,
  getDssPromise,
  getDssPromisePolicy,
  getDssRoutes,
  getDssScenario,
  getDssSellers,
  postDssAction,
} from "../data/api.js";
import {
  detailOf,
  mapAttributionRow,
  mapPolicyRows,
  mapPortfolio,
  mapPromise,
  mapRouteRows,
  mapScenario,
  mapSellerRows,
  routeLabel,
  shortId,
} from "../data/dssAdapter.js";
import {
  pct,
  num,
  int,
  useData,
  YearSel,
  Errored,
  Skeleton,
  Empty,
  Pill,
} from "../utils/utils.js";
import {
  BLOCKS,
  BriefGroup,
  BriefList,
  CopyBtn,
  InlineError,
  KV,
  Note,
  Pop,
  PS,
  SG,
  SignedBar,
  Status,
  Takeaway,
  TIPS,
  Tip,
  Block,
} from "./dssParts.jsx";

const STAGE_NAMES = {
  approval: "Duyệt thanh toán",
  prep: "Người bán chuẩn bị",
  transit: "Vận chuyển",
};
const pctSigned = (v) => (v == null ? "—" : (v > 0 ? "+" : "") + num(v * 100, 1) + "%");
const fmtTime = (s) => {
  try {
    return new Date(s).toLocaleString("vi-VN");
  } catch {
    return s || "";
  }
};

export default function DssView({ year, setYear, sim, initRoute }) {
  const [sort, setSort] = useState("rate");
  const [sel, setSel] = useState(initRoute ? String(initRoute).replace("→", "->") : null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [q, setQ] = useState(0.5);
  const [cut, setCut] = useState({ approval: 0, prep: 0, transit: 0 });
  const [target, setTarget] = useState(0.05);
  const [tab, setTab] = useState(null);
  const [openSupport, setOpenSupport] = useState(false);
  const [toast, setToast] = useState(null);
  const [posting, setPosting] = useState(false);

  const brief = useData((signal) => getDssBrief(year, signal), [year], sim);
  const routesApi = useData((signal) => getDssRoutes(year, 1000, signal), [year], sim);
  const attrApi = useData((signal) => getDssAttribution(year, q, signal), [year, q], sim);
  const policyApi = useData((signal) => getDssPromisePolicy(year, signal), [year], sim);
  const sellersApi = useData((signal) => getDssSellers(year, signal), [year], sim);
  const portfolioApi = useData((signal) => getDssPortfolio(year, signal), [year], sim);
  const logApi = useData((signal) => getDssActions(signal), [], sim);

  const flagged = routesApi.data || [];
  const params = brief.data?.parameters;
  const routeRows = params ? mapRouteRows(attrApi.data, flagged, params.min_orders) : [];
  const cur = routeRows.find((r) => r.route === sel) || routeRows[0] || null;

  const scenarioApi = useData(
    (signal) => (cur ? getDssScenario({ year, route: cur.route, cut }, signal) : null),
    [year, cur?.route, cut.approval, cut.prep, cut.transit],
    sim,
  );
  const promiseApi = useData(
    (signal) => (cur ? getDssPromise({ year, route: cur.route, target }, signal) : null),
    [year, cur?.route, target],
    sim,
  );

  const firstYear = useRef(true);
  useEffect(() => {
    if (firstYear.current) {
      firstYear.current = false;
      return;
    }
    setSel(null);
    setFrom("");
    setTo("");
    setShowAll(false);
  }, [year]);

  const records = logApi.data || [];
  const record = async ({ id, level, text }) => {
    setPosting(true);
    try {
      await postDssAction({
        action: "recommendation",
        route: String(id || "").slice(0, 20),
        level: String(level || "").slice(0, 10),
        detail: text,
      });
      logApi.retry();
      setToast("Đã ghi nhận khuyến nghị (chỉ ghi log, không thực thi).");
    } catch (e) {
      setToast("Không ghi nhận được: " + (e?.message || "lỗi kết nối"));
    } finally {
      setPosting(false);
    }
  };
  const isDone = (id, text) =>
    records.some(
      (l) =>
        l.action === "recommendation" &&
        l.route === String(id || "").slice(0, 20) &&
        detailOf(l) === text,
    );
  const jump = (id) => {
    const el = document.getElementById("dss-" + id);
    if (el) {
      const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
      el.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    }
  };
  const go = (id) => {
    if (id === "promise" || id === "seller") {
      setOpenSupport(true);
      requestAnimationFrame(() => jump(id));
    } else {
      jump(id);
    }
  };
  const onView = (v) => {
    if (v.type === "route") {
      setSel(v.route);
      jump("attr");
    } else {
      go(v.grp);
    }
  };

  const frame = (curRow, body) => (
    <div className="space-y-4">
      <div className="panel px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <span
          className="text-[11px] px-1.5 py-0.5 rounded bg-teal-50 text-teal-900 font-medium"
          title="Số liệu lấy trực tiếp từ backend DSS, không có dữ liệu mẫu"
        >
          Dữ liệu thật · API
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <YearSel year={year} setYear={setYear} />
          <Pop label="Cách đọc số liệu" w="w-96">
            <ul className="text-xs space-y-1.5 list-disc pl-4 text-slate-700">
              <li>Đơn vị phân tích là <b>đơn-tuyến (order-route)</b>: một đơn có nhiều người bán sẽ tạo nhiều dòng và có thể nằm trên nhiều tuyến.</li>
              <li>Số “tránh được” là mô phỏng theo luật, không phải tác động nhân quả; hệ thống không thực thi hành động vận hành.</li>
              <li>Tỷ trọng giai đoạn là nhãn mô tả, không phải nguyên nhân; tỷ trọng có dấu nên có thể âm.</li>
              <li>Khoảng tin cậy 95% do API tính (Wilson); nếu chứa 0 thì kết luận là “chưa đủ bằng chứng”.</li>
              <li>Cảnh báo mẫu nhỏ và “chưa chắc chắn” do API gắn cờ; UI không tự tính lại.</li>
              <li>Rút ngắn 1 ngày được coi là giao sớm hơn 1 ngày. Đổi ngày cam kết chỉ đổi định nghĩa “trễ”.</li>
              <li>Các nhóm trong Tổng hợp hành động chồng lấn trên cùng các đơn trễ nên không cộng số giữa các nhóm.</li>
              <li>Phiếu người bán và điểm đánh giá chỉ là liên hệ, chưa hiệu chỉnh theo cơ cấu tuyến.</li>
              <li className="text-slate-500">Nút “Ghi nhận khuyến nghị” chỉ ghi log, không thực thi hành động.</li>
              <li className="text-slate-500">Wilson, Shapley (có dấu), bootstrap 300 lần (seed 42) đều do API tính; giao diện chỉ hiển thị.</li>
            </ul>
          </Pop>
          <Pop label={`Đã ghi nhận (${records.length})`} w="w-96">
            {logApi.error && <InlineError msg={logApi.error} retry={logApi.retry} />}
            {records.length ? (
              <ul className="text-xs max-h-64 overflow-y-auto">
                {records.map((l, i) => (
                  <li key={i} className="border-t border-slate-100 py-1.5 first:border-0">
                    <span className="text-slate-500">{fmtTime(l.created_at)}</span> · {l.action}: <b>{routeLabel(l.route)}</b>
                    {l.level && <> · <Status level={l.level} /></>}
                    <div className="text-slate-600">{detailOf(l)}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500">Chưa có ghi nhận nào.</p>
            )}
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
              <span className="text-[11px] text-slate-500">Chỉ ghi log, không thực thi hành động.</span>
              <button className="btn" onClick={logApi.retry}>Tải lại</button>
            </div>
          </Pop>
        </div>
      </div>
      {curRow && (
        <div className="sticky top-14 z-20 panel bg-slate-50 px-4 py-1.5 text-xs flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-slate-500">Đang xem tuyến</span>
          <b className="text-sm">{routeLabel(curRow.route)}</b>
          <span>
            {pct(curRow.lateRate)} trễ <span className="text-slate-500">({int(curRow.lateOrders)}/{int(curRow.orderRoutes)} đơn-tuyến)</span>
          </span>
          <Status level={curRow.level} />
          {curRow.lowSample && <Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700" />}
          {curRow.rootCause?.owner && <span className="text-slate-500">Phụ trách giai đoạn: {curRow.rootCause.owner}</span>}
          <button className="underline text-teal-800" onClick={() => jump("route")}>Đổi tuyến</button>
        </div>
      )}
      {body}
      <div className="fixed bottom-4 right-4 z-50 max-w-[90vw]" role="status" aria-live="polite">
        {toast && (
          <div className="bg-slate-900 text-white text-sm rounded px-4 py-2 shadow-lg flex items-center gap-3">
            {toast}
            <button className="text-slate-300" aria-label="Đóng" onClick={() => setToast(null)}>×</button>
          </div>
        )}
      </div>
    </div>
  );

  if (brief.error) return frame(null, <Errored msg={brief.error} retry={brief.retry} />);
  if (brief.loading || !brief.data) {
    return frame(null, <><Skeleton h={260} /><Skeleton h={260} /></>);
  }
  const cfg = brief.data.config;
  if (!cfg || !params) {
    return frame(null, <Errored msg="Thiếu config/parameters trong /brief" retry={brief.retry} />);
  }
  if (routesApi.error || attrApi.error) {
    return frame(null, <Errored msg={routesApi.error || attrApi.error} retry={routesApi.error ? routesApi.retry : attrApi.retry} />);
  }
  if (routesApi.loading || attrApi.loading || !attrApi.data) {
    return frame(null, <><Skeleton h={260} /><Skeleton h={260} /></>);
  }
  if (!routeRows.length) {
    return frame(null, <Empty msg="Chưa có tuyến nào đủ số đơn để phân tích" />);
  }

  const ends = (r) => String(r.route).split("->");
  const tally = (rows) => Object.entries(rows).sort((a, b) => a[0].localeCompare(b[0]));
  const fromOpts = tally(routeRows.reduce((m, r) => {
    const origin = ends(r)[0];
    m[origin] = (m[origin] || 0) + r.orderRoutes;
    return m;
  }, {}));
  const toOpts = tally(
    routeRows.filter((r) => !from || ends(r)[0] === from).reduce((m, r) => {
      const dest = ends(r)[1];
      m[dest] = (m[dest] || 0) + r.orderRoutes;
      return m;
    }, {}),
  );
  const toEff = toOpts.some(([d]) => d === to) ? to : "";
  const filtered = !!(from || toEff);
  const pool = routeRows.filter((r) => (!from || ends(r)[0] === from) && (!toEff || ends(r)[1] === toEff));
  const sorted = [...pool].sort((a, b) => (sort === "rate" ? b.lateRate - a.lateRate : b.lateOrders - a.lateOrders));
  const shownRows = showAll || filtered ? sorted : sorted.slice(0, 10);
  const nRed = flagged.filter((r) => r.level === "red").length;
  const nYel = flagged.filter((r) => r.level === "amber").length;
  const lowSample = (r) => r.orderRoutes < params.low_sample_threshold;

  const attrRow = cur ? mapAttributionRow(attrApi.data, cur.route) : null;
  const shares = attrRow && attrRow.lateRate > 0
    ? [
        ["Duyệt thanh toán", attrRow.causeShares.approval, "#94a3b8"],
        ["Người bán chuẩn bị", attrRow.causeShares.prep, "#0f766e"],
        ["Vận chuyển", attrRow.causeShares.transit, "#b45309"],
        ["Chưa giải thích được (liên quan ngày cam kết)", attrRow.sharePromise, "#64748b"],
      ]
    : [];
  const shareMax = Math.max(0, ...shares.map(([, v]) => Math.abs(v || 0)));
  const topStage = attrRow?.topStage ? STAGE_NAMES[attrRow.topStage] || attrRow.topStage : null;
  const topShare = attrRow?.topStage ? attrRow.causeShares[attrRow.topStage] : null;

  const sc = scenarioApi.data ? mapScenario(scenarioApi.data) : null;
  const seriesMax = sc?.series?.length ? sc.series[sc.series.length - 1].cut : 0;
  const anyCut = cut.approval > 0 || cut.prep > 0 || cut.transit > 0;
  const scenText = sc && anyCut
    ? `Kịch bản cắt duyệt ${num(cut.approval)}, chuẩn bị ${num(cut.prep)}, vận chuyển ${num(cut.transit)} ngày → tránh ${int(sc.avoided)} đơn trễ`
    : "";
  const pp = promiseApi.data ? mapPromise(promiseApi.data) : null;
  const policyRows = mapPolicyRows(policyApi.data);
  const sellerRows = mapSellerRows(sellersApi.data);
  const port = portfolioApi.data ? mapPortfolio(portfolioApi.data) : null;
  const segs = port?.segments || [];
  const segNames = segs.map((s) => s.segment);
  const activeTab = tab && segNames.includes(tab) ? tab : segNames[0] || null;
  const shownSellers = sellerRows
    .filter((s) => s.segment === activeTab)
    .sort((a, b) => b.lateOrders - a.lateOrders)
    .slice(0, 10);

  const br = brief.data;
  const ownerOf = (rows) =>
    Array.from(new Set((rows || []).map((r) => r.owner).filter(Boolean))).join(" · ") || "—";
  const flagOf = (route) => flagged.find((r) => r.route === route) || {};
  const briefRoute = (br.route_actions || []).map((a) => ({
    key: "r|" + a.route,
    id: a.route,
    level: flagOf(a.route).level,
    main: routeLabel(a.route),
    pill: <Status level={flagOf(a.route).level} />,
    owner: a.owner,
    sub: a.action,
    text: a.action,
    view: { type: "route", route: a.route },
  }));
  const briefPay = (br.payment_actions || []).map((a) => ({
    key: "p|" + a.payment_type,
    id: a.payment_type,
    level: "",
    main: a.payment_type,
    pill: <Pill t={a.status} c="bg-teal-50 text-teal-900" wrap />,
    owner: a.owner,
    sub: a.action,
    text: a.action,
    view: null,
  }));
  const briefProm = (br.promise_actions || []).map((a) => {
    const ps = PS[a.label] || PS.ok;
    return {
      key: "c|" + a.route + "|" + a.weight_band,
      id: a.route + "|" + a.weight_band,
      level: "",
      main: routeLabel(a.route) + " × " + a.weight_band,
      pill: <Pill t={ps[0]} c={ps[1]} />,
      owner: a.owner,
      sub: a.action,
      text: a.action,
      view: { type: "promise", grp: "promise" },
    };
  });
  const briefSell = (br.seller_actions || []).map((a) => ({
    key: "s|" + a.seller_id,
    id: a.seller_id,
    level: a.level,
    main: shortId(a.seller_id),
    copy: a.seller_id,
    pill: <Pill t={a.segment} c={(SG[a.segment] || SG["cần thêm dữ liệu"])[1]} />,
    owner: a.owner,
    sub: a.action,
    text: a.action,
    view: { type: "seller", grp: "seller" },
  }));
  const briefMore = (br.low_sample_actions || []).map((a) => ({
    key: "m|" + a.route,
    id: a.route,
    level: a.level,
    main: routeLabel(a.route),
    pill: <Pill t={a.status} c="bg-slate-100 text-slate-700" />,
    owner: a.owner,
    sub: a.action,
    text: a.action,
    view: { type: "route", route: a.route },
  }));
  const listProps = {
    done: (r) => isDone(r.id, r.text),
    onRec: (r) => record({ id: r.id, level: r.level, text: r.text }),
    onView,
  };

  return frame(
    cur,
    <>
      <nav aria-label="Luồng quyết định" className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
        {BLOCKS.map(([id, n, title]) => (
          <button key={id} onClick={() => go(id)} className="panel text-left p-2.5 hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span className="shrink-0 w-6 h-6 rounded-full bg-teal-700 text-white text-xs font-semibold grid place-items-center" aria-hidden="true">{n}</span>
              <span className="text-sm font-semibold leading-tight">{title}</span>
            </div>
          </button>
        ))}
      </nav>

      <Block
        id="route"
        aside={[
          ["rate", "Xếp theo tỷ lệ trễ"],
          ["count", "Xếp theo số đơn trễ"],
        ].map(([k, t]) => (
          <button key={k} className={"btn " + (sort === k ? "btn-main" : "")} aria-pressed={sort === k} onClick={() => setSort(k)}>{t}</button>
        ))}
      >
        <Takeaway>
          <b>{nRed} tuyến đỏ</b> và <b>{nYel} tuyến vàng</b> trong {routeRows.length} tuyến đủ mẫu (≥ {int(params.min_orders)} đơn-tuyến). Chọn một tuyến để xem các khối 2, 3 và 4.
        </Takeaway>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Lọc tuyến theo điểm đi và điểm đến">
            <label className="text-xs text-slate-600 flex items-center gap-2">
              Điểm đi
              <select className="sel" value={from} onChange={(e) => { setFrom(e.target.value); setTo(""); }}>
                <option value="">Tất cả</option>
                {fromOpts.map(([o]) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <span aria-hidden="true" className="text-slate-400">→</span>
            <label className="text-xs text-slate-600 flex items-center gap-2">
              Điểm đến
              <select className="sel" value={toEff} onChange={(e) => setTo(e.target.value)}>
                <option value="">Tất cả</option>
                {toOpts.map(([d]) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            {filtered && <button className="btn" onClick={() => { setFrom(""); setTo(""); }}>Xoá lọc</button>}
          </div>
          <span className="text-xs text-slate-500" aria-live="polite">Hiển thị {shownRows.length}/{pool.length} tuyến</span>
          {!filtered && pool.length > 10 && (
            <button className="btn" aria-expanded={showAll} onClick={() => setShowAll(!showAll)}>
              {showAll ? "Thu gọn (top 10)" : `Xem tất cả (${pool.length})`}
            </button>
          )}
        </div>
        {!pool.length ? (
          <p className="text-sm text-slate-600 py-4 text-center">
            Không có tuyến nào khớp bộ lọc điểm đi / điểm đến.{" "}
            <button className="underline text-teal-800" onClick={() => { setFrom(""); setTo(""); }}>Xoá lọc</button>
          </p>
        ) : (
          <>
            <div className="hidden md:block overflow-auto max-h-[30rem]">
              <table className="w-full text-xs">
                <thead className="text-left text-slate-500 bg-white sticky top-0 z-10">
                  <tr>
                    <th className="py-1 px-2 sticky left-0 z-20 bg-white">Tuyến</th>
                    <th className="text-right px-2">Đơn-tuyến</th>
                    <th className="text-right px-2">Trễ</th>
                    <th className="text-right px-2">Tỷ lệ trễ</th>
                    <th className="text-right px-2"><Tip t={TIPS.ci}>Khoảng tin cậy</Tip></th>
                    <th className="px-2">Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {shownRows.map((r) => {
                    const on = r.route === cur.route;
                    return (
                      <tr key={r.route} onClick={() => setSel(r.route)} className={"border-t border-slate-100 cursor-pointer " + (on ? "bg-teal-50" : "bg-white hover:bg-slate-50")}>
                        <td className={"py-1.5 px-2 font-medium sticky left-0 bg-inherit border-l-4 " + (on ? "border-teal-600" : "border-transparent")}>
                          <button className="text-left" aria-pressed={on}>
                            {routeLabel(r.route)}{on && <span className="ml-2 text-[11px] font-normal text-teal-800">● đang xem</span>}
                          </button>
                        </td>
                        <td className="text-right px-2">{int(r.orderRoutes)}</td>
                        <td className="text-right px-2">{int(r.lateOrders)}</td>
                        <td className="text-right px-2 font-semibold">{pct(r.lateRate)}</td>
                        <td className="text-right px-2 text-slate-600">{r.ciLow == null ? "—" : pct(r.ciLow) + " – " + pct(r.ciHigh)}</td>
                        <td className="px-2">
                          <Status level={r.level} />
                          {lowSample(r) && <> <Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700" /></>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <ul className="md:hidden space-y-2 max-h-[32rem] overflow-y-auto">
              {shownRows.map((r) => {
                const on = r.route === cur.route;
                return (
                  <li key={r.route}>
                    <button aria-pressed={on} onClick={() => setSel(r.route)} className={"w-full text-left panel p-3 " + (on ? "border-teal-600 bg-teal-50" : "")}>
                      <div className="flex items-center justify-between gap-2">
                        <b>{routeLabel(r.route)}{on && <span className="ml-2 text-[11px] font-normal text-teal-800">● đang xem</span>}</b>
                        <span className="flex gap-1">
                          <Status level={r.level} />
                          {lowSample(r) && <Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700" />}
                        </span>
                      </div>
                      <div className="text-xs text-slate-600 mt-1">{int(r.orderRoutes)} đơn-tuyến · {int(r.lateOrders)} trễ · <b>{pct(r.lateRate)}</b></div>
                      <div className="text-[11px] text-slate-500">Khoảng tin cậy {r.ciLow == null ? "—" : pct(r.ciLow) + " – " + pct(r.ciHigh)}</div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        )}
        <Note>
          Tỷ lệ trễ chung <b>{pct(cfg.base_rate)}</b> (vs {cfg.base_rate_label}). Đỏ khi ≥ 2 lần, vàng khi ≥ 1,5 lần mức chung. Chỉ tuyến có ít nhất {int(params.min_orders)} đơn-tuyến mới xuất hiện trong danh sách chọn.
        </Note>
      </Block>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Block id="attr">
          {attrApi.error ? (
            <InlineError msg={attrApi.error} retry={attrApi.retry} />
          ) : attrRow && attrRow.lateRate > 0 ? (
            <>
              <Takeaway>
                Giai đoạn chiếm tỷ trọng lớn nhất trong đơn trễ của <b>{routeLabel(cur.route)}</b>: <b>{topStage || "—"}</b> ({pctSigned(topShare)}).
              </Takeaway>
              <div className="space-y-2">
                {shares.map(([t, v, color]) => (
                  <div key={t}>
                    <div className="flex justify-between text-xs"><span>{t}</span><b>{pctSigned(v)}</b></div>
                    <SignedBar v={v} max={shareMax} color={color} />
                  </div>
                ))}
              </div>
              <Note>
                Tỷ trọng có dấu: φ có thể âm khi giai đoạn ngắn hơn benchmark; thanh vẽ từ mốc 0, không cắt về 0. Dựa trên {int(attrRow.orders)} đơn của tuyến này.
              </Note>
            </>
          ) : (
            <p className="text-sm text-slate-600">
              {attrRow ? "Tuyến này không có đơn trễ." : "Chưa có dữ liệu attribution cho tuyến này."}
            </p>
          )}
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer font-medium text-slate-700">Tùy chọn phân tích</summary>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-slate-600">So với mức</span>
              {[
                [0.5, "Trung vị (mặc định)"],
                [0.25, "Tốt (P25)"],
              ].map(([v, t]) => (
                <button key={v} className={"btn " + (q === v ? "btn-main" : "")} aria-pressed={q === v} onClick={() => setQ(v)}>{t}</button>
              ))}
            </div>
          </details>
        </Block>

        <Block id="cut" aside={<button className="btn" onClick={() => setCut({ approval: 0, prep: 0, transit: 0 })}>Xoá</button>}>
          <div aria-live="polite" aria-atomic="true">
            {sc && anyCut ? (
              <Takeaway>
                Kịch bản này giúp <b>{routeLabel(cur.route)}</b> tránh được khoảng <b>{int(sc.avoided)}/{int(cur.lateOrders)}</b> đơn trễ (tỷ lệ trễ {pct(sc.baseline)} → {pct(sc.projected)}).
              </Takeaway>
            ) : (
              <Takeaway>Kéo các thanh trượt để thử kịch bản cho <b>{routeLabel(cur.route)}</b>.</Takeaway>
            )}
          </div>
          {scenarioApi.error ? (
            <InlineError msg={scenarioApi.error} retry={scenarioApi.retry} />
          ) : !sc ? (
            <Skeleton h={110} />
          ) : (
            <>
              <div className="space-y-1.5">
                {[
                  ["approval", "Duyệt thanh toán"],
                  ["prep", "Người bán chuẩn bị"],
                  ["transit", "Vận chuyển"],
                ].map(([k, t]) => (
                  <label key={k} className="flex items-center gap-3 text-xs">
                    <span className="w-36">{t}</span>
                    <input type="range" min="0" max={seriesMax} step="0.5" value={cut[k]} onChange={(e) => setCut({ ...cut, [k]: +e.target.value })} className="flex-1" aria-label={"Rút ngắn " + t} />
                    <b className="w-16 text-right">−{num(cut[k])} ngày</b>
                  </label>
                ))}
              </div>
              <div className="mt-3 bg-slate-50 rounded p-3 text-sm space-y-1">
                <div>
                  Giai đoạn nghẽn do API xác định: <b>{STAGE_NAMES[sc.bottleneck] || sc.bottleneck}</b>
                  {cur.rootCause?.owner ? <> · phụ trách <b>{cur.rootCause.owner}</b></> : null}
                  {!sc.hasBottleneck && <span className="text-slate-500"> (không có giai đoạn vượt mức trung bình)</span>}
                </div>
                {sc.series.length > 0 && (
                  <div className="text-[11px] text-slate-500">
                    Độ nhạy do API trả: cắt giai đoạn nghẽn 0–{seriesMax} ngày, tỷ lệ trễ {pct(sc.series[0].projected)} → {pct(sc.series[sc.series.length - 1].projected)}.
                  </div>
                )}
                {anyCut && (
                  <div className="pt-1">
                    <button className="btn btn-main" disabled={posting} onClick={() => record({ id: cur.route, level: cur.level, text: scenText })}>
                      Ghi nhận kịch bản
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </Block>
      </div>

      <details id="dss-support" className="panel p-4 scroll-mt-28" open={openSupport} onToggle={(e) => setOpenSupport(e.currentTarget.open)}>
        <summary className="cursor-pointer font-semibold">Phân tích hỗ trợ: Promise policy và Seller scorecard</summary>
        <div className="mt-4 space-y-4">
          <Block id="promise">
            {promiseApi.error || policyApi.error ? (
              <InlineError msg={promiseApi.error || policyApi.error} retry={promiseApi.error ? promiseApi.retry : policyApi.retry} />
            ) : !pp ? (
              <Skeleton h={90} />
            ) : (
              <>
                <Takeaway>
                  Cần kéo dài cam kết của <b>{routeLabel(cur.route)}</b> thêm <b>{int(pp.extraDays)} ngày</b> để tỷ lệ trễ ≤ <b>{pct(target)}</b> (còn {pct(pp.lateAfter)}).
                </Takeaway>
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.6fr] gap-5">
                  <div>
                    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-slate-100 text-sm">
                      <span className="text-slate-600">Mục tiêu tỷ lệ trễ</span>
                      <select className="sel" value={target} onChange={(e) => setTarget(+e.target.value)}>
                        <option value={0.05}>5%</option>
                        <option value={0.1}>10%</option>
                      </select>
                    </div>
                    <KV k="Số ngày cần kéo dài">{int(pp.extraDays)} ngày</KV>
                    <KV k="Tỷ lệ trễ sau khi kéo dài">{pct(pp.lateAfter)}</KV>
                    <KV k="Tỷ lệ trễ hiện tại">{pct(cur.lateRate)}</KV>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="text-left text-slate-500">
                        <tr>
                          <th className="py-1 px-2">Tuyến</th>
                          <th className="text-right px-2">Mức phục vụ</th>
                          <th className="text-right px-2">Ngày cam kết cần</th>
                          <th className="text-right px-2">Tỷ lệ trễ</th>
                          <th className="text-right px-2">Đơn tránh được</th>
                          <th className="text-right px-2">Đơn trễ mới</th>
                          <th className="text-right px-2"><Tip t={TIPS.net}>Chênh ròng</Tip></th>
                        </tr>
                      </thead>
                      <tbody>
                        {policyRows.map((v, i) => (
                          <tr key={i} className="border-t border-slate-100">
                            <td className="py-1.5 px-2 font-medium">{routeLabel(v.route)}</td>
                            <td className="text-right px-2">{pct(v.serviceLevel)}</td>
                            <td className="text-right px-2">{int(v.neededDays)}</td>
                            <td className="text-right px-2">{pct(v.lateRate)}</td>
                            <td className="text-right px-2">{int(v.avoidable)}</td>
                            <td className="text-right px-2">{int(v.newLate)}</td>
                            <td className="text-right px-2 font-semibold">{v.net >= 0 ? "+" : "−"}{int(Math.abs(v.net))}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {br.promise_summary && (
                  <p className="text-xs text-slate-600 mt-3">
                    Toàn hệ thống: trễ {int(br.promise_summary.late_orders_before)} → {int(br.promise_summary.late_orders_after)} đơn; ròng <b>{int(br.promise_summary.net_avoided_orders)}</b> (phát sinh {int(br.promise_summary.new_late_orders)} đơn trễ mới).
                  </p>
                )}
                <Note>Đổi ngày cam kết chỉ đổi định nghĩa “trễ”, không rút ngắn thời gian giao. Bảng trên là mức phục vụ 85/90/95% cho các tuyến API chọn.</Note>
              </>
            )}
          </Block>

          <Block id="seller">
            {portfolioApi.error || sellersApi.error ? (
              <InlineError msg={portfolioApi.error || sellersApi.error} retry={portfolioApi.error ? portfolioApi.retry : sellersApi.retry} />
            ) : !port ? (
              <Skeleton h={120} />
            ) : (
              <>
                <Takeaway>
                  Cần ít nhất <b>{int(port.kCover50)}</b> người bán để phủ 50% đơn trễ; 10 người đầu chiếm <b>{pct(port.topShare)}</b> đơn trễ. Chọn một nhóm để xem danh sách.
                </Takeaway>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" role="group" aria-label="Nhóm người bán">
                  {segs.map((s) => {
                    const sg = SG[s.segment] || SG["cần thêm dữ liệu"];
                    return (
                      <button key={s.segment} aria-pressed={activeTab === s.segment} onClick={() => setTab(s.segment)} className={"panel text-left p-3 hover:bg-slate-50 " + (activeTab === s.segment ? "border-teal-600 bg-teal-50" : "")}>
                        <Pill t={sg[0]} c={sg[1]} />
                        <div className="text-2xl font-semibold mt-1">{int(s.nSellers)} <span className="text-xs font-normal text-slate-600">người bán</span></div>
                        <div className="text-[11px] text-slate-500">{int(s.lateOrders)} đơn trễ ({pct(s.lateOrdersShare)})</div>
                      </button>
                    );
                  })}
                </div>
                <div className="overflow-x-auto mt-3">
                  <table className="w-full text-xs">
                    <thead className="text-left text-slate-500">
                      <tr>
                        <th className="py-1 px-2">Người bán</th>
                        <th className="text-right px-2">Đơn</th>
                        <th className="text-right px-2">Trễ</th>
                        <th className="text-right px-2">Tỷ lệ trễ</th>
                        <th className="text-right px-2"><Tip t={TIPS.review}>Tỷ lệ đánh giá xấu</Tip></th>
                      </tr>
                    </thead>
                    <tbody>
                      {shownSellers.map((s) => (
                        <tr key={s.id} className="border-t border-slate-100">
                          <td className="py-1.5 px-2 font-medium" title={s.id}>{shortId(s.id)}<CopyBtn text={s.id} /></td>
                          <td className="text-right px-2">{int(s.orders)}</td>
                          <td className="text-right px-2">{int(s.lateOrders)}</td>
                          <td className="text-right px-2 font-semibold">{pct(s.lateRate)}</td>
                          <td className="text-right px-2">{pct(s.badReviewRate)}</td>
                        </tr>
                      ))}
                      {!shownSellers.length && <tr><td colSpan="5" className="py-4 text-center text-slate-500">Không có người bán nào trong nhóm này.</td></tr>}
                    </tbody>
                  </table>
                </div>
                <Note>Hiển thị tối đa 10 người đầu mỗi nhóm. Nguồn: /portfolio (nhóm, độ phủ) và /sellers (từng người bán).</Note>
              </>
            )}
          </Block>
        </div>
      </details>

      <Block id="brief">
        <Takeaway>Bấm vào một dòng để xem chi tiết, bấm “Ghi nhận khuyến nghị” để lưu cho đơn vị phụ trách (chỉ ghi log, không thực thi).</Takeaway>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 items-start">
          <BriefGroup src="route" title="Tuyến cần hành động" owner={ownerOf(br.route_actions)}><BriefList rows={briefRoute} {...listProps} /></BriefGroup>
          <BriefGroup src="attr" title="Thanh toán" owner={ownerOf(br.payment_actions)}><BriefList rows={briefPay} {...listProps} /></BriefGroup>
          <BriefGroup src="promise" title="Chính sách cam kết" owner={ownerOf(br.promise_actions)}><BriefList rows={briefProm} {...listProps} /></BriefGroup>
          <BriefGroup src="seller" title="Người bán" owner={ownerOf(br.seller_actions)}><BriefList rows={briefSell} {...listProps} /></BriefGroup>
          <BriefGroup src="route" title="Cần thêm dữ liệu" owner={ownerOf(br.low_sample_actions)}><BriefList rows={briefMore} {...listProps} /></BriefGroup>
        </div>
        <Note>
          Năm nhóm chồng lấn trên cùng các đơn trễ nên không cộng số giữa các nhóm. Ngưỡng lấy từ /brief.parameters: min_orders={int(params.min_orders)}, low_sample&lt;{int(params.low_sample_threshold)}, seller_min={int(params.seller_min_orders)}.
        </Note>
      </Block>
    </>,
  );
}
