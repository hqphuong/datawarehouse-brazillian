import { useState } from "react";
import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
} from "recharts";
import { getOlapMetadata, postOlapQuery } from "../data/api.js";
import {
  pct,
  num,
  int,
  useData,
  MultiSelect,
  Errored,
  Skeleton,
  Empty,
} from "../utils/utils.js";

const LV_NAME = { year: "Năm", quarter: "Quý", month: "Tháng" };
const NEXT = { year: "quarter", quarter: "month" };
const DIMS = {
  time: "Thời gian",
  customer_state: "Bang khách hàng",
  seller_state: "Bang người bán",
  category: "Danh mục sản phẩm",
  payment_type: "Phương thức thanh toán",
  seller: "Người bán",
  day_of_week: "Ngày trong tuần",
};
const DIMENSION_KEYS = {
  time: "Dim_Time.month",
  customer_state: "Dim_Location.state",
  seller_state: "Dim_Seller.state",
  category: "Dim_Product.category_name_english",
  payment_type: "Fact_Delivery_SLA.payment_type",
  seller: "Dim_Seller.seller_id",
  day_of_week: "Dim_Time.day_of_week",
};
const MEAS = {
  total_orders: ["Số đơn", (value) => int(value)],
  total_items: ["Số dòng dữ liệu", (value) => int(value)],
  late_count: ["Số đơn trễ", (value) => int(value)],
  late_rate: ["Tỷ lệ trễ", (value) => pct(value / 100)],
  avg_approval_days: ["Duyệt thanh toán TB (ngày)", (value) => num(value, 2)],
  avg_prep_days: ["Người bán chuẩn bị TB (ngày)", (value) => num(value, 2)],
  avg_transit_days: ["Vận chuyển TB (ngày)", (value) => num(value, 2)],
  avg_delivery_days: ["Thời gian giao TB (ngày)", (value) => num(value, 2)],
  avg_freight_value: ["Phí vận chuyển TB (R$)", (value) => num(value, 2)],
  total_freight: ["Tổng phí vận chuyển (R$)", (value) => num(value, 2)],
  avg_review_score: ["Điểm đánh giá TB", (value) => num(value, 2)],
};
const PRESETS = [
  { t: "Tỷ lệ trễ theo bang khách × quý", rows: "customer_state", cols: "time", tl: "quarter", m: "late_rate" },
  { t: "Tỷ lệ trễ theo bang người bán × bang khách", rows: "seller_state", cols: "customer_state", tl: "year", m: "late_rate" },
  { t: "Vận chuyển TB theo năm → tháng (drill-down)", rows: "time", cols: "none", tl: "year", m: "avg_transit_days" },
  { t: "Số đơn trễ theo người bán", rows: "seller", cols: "none", tl: "year", m: "late_count" },
  { t: "Số đơn theo danh mục", rows: "category", cols: "none", tl: "year", m: "total_orders" },
];

function makeTimeOptions(timeRange) {
  const [startYear, startMonth] = (timeRange?.min_month || "").split("-").map(Number);
  const [endYear, endMonth] = (timeRange?.max_month || "").split("-").map(Number);
  if (!startYear || !endYear || startYear > endYear || (startYear === endYear && startMonth > endMonth)) {
    return { month: [], quarter: [], year: [] };
  }
  const month = [];
  for (let year = startYear, currentMonth = startMonth; year < endYear || (year === endYear && currentMonth <= endMonth);) {
    month.push(`${year}-${String(currentMonth).padStart(2, "0")}`);
    currentMonth += 1;
    if (currentMonth > 12) {
      currentMonth = 1;
      year += 1;
    }
  }
  return {
    month,
    quarter: [...new Set(month.map((value) => `${value.slice(0, 4)}-Q${Math.ceil(Number(value.slice(5)) / 3)}`))],
    year: [...new Set(month.map((value) => value.slice(0, 4)))],
  };
}

function periodMonths(level, value) {
  if (level === "year") return { from: `${value}-01`, to: `${value}-12` };
  if (level === "quarter") {
    const [, year, quarter] = value.match(/^(\d{4})-Q([1-4])$/) || [];
    if (!year) return { from: value, to: value };
    const firstMonth = (Number(quarter) - 1) * 3 + 1;
    return {
      from: `${year}-${String(firstMonth).padStart(2, "0")}`,
      to: `${year}-${String(firstMonth + 2).padStart(2, "0")}`,
    };
  }
  return { from: value, to: value };
}

function queryBounds(filters, drill) {
  const start = periodMonths(filters.level, filters.from);
  const end = periodMonths(filters.level, filters.to);
  let from = start.from;
  let to = end.to;
  drill.forEach((period) => {
    const bounds = periodMonths(period.level, period.value);
    if (bounds.from > from) from = bounds.from;
    if (bounds.to < to) to = bounds.to;
  });
  return { from_time: from, to_time: to };
}

function dimensionValue(row, dimension, timeLevel) {
  const aliases = {
    time: timeLevel,
    customer_state: "customer_state",
    seller_state: "seller_state",
    category: "category_name_english",
    payment_type: "payment_type",
    seller: "seller_id",
    day_of_week: "day_of_week",
  };
  return String(row[aliases[dimension]] ?? "");
}

function toCell(row, measure) {
  return { n: Number(row.total_orders) || 0, [measure]: row[measure] };
}

function sumCells(cells, measure) {
  const n = cells.reduce((sum, cell) => sum + cell.n, 0);
  const additive = ["total_orders", "total_items", "late_count", "total_freight"];
  const value = additive.includes(measure)
    ? cells.reduce((sum, cell) => sum + (Number(cell[measure]) || 0), 0)
    : n
      ? cells.reduce((sum, cell) => sum + (Number(cell[measure]) || 0) * cell.n, 0) / n
      : 0;
  return { n, [measure]: value };
}

function DimensionPick({ label, field, none, config, onChange }) {
  return (
    <label className="text-xs text-slate-600">
      {label}
      <br />
      <select
        className="sel mt-0.5 min-w-[150px]"
        value={config[field]}
        onChange={(e) => onChange(e.target.value)}
      >
        {none && <option value="none">(Không dùng)</option>}
        {Object.entries(DIMS)
          .filter(
            ([dimension]) =>
              dimension !== (field === "rows" ? config.cols : config.rows),
          )
          .map(([dimension, name]) => (
            <option key={dimension} value={dimension}>
              {name}
            </option>
          ))}
      </select>
    </label>
  );
}

export default function OlapView({ sim }) {
  const [fl, setFl] = useState({
      level: "month", from: "", to: "", sstates: [], cstates: [], categories: [],
    }),
    [cfg, setCfg] = useState({ rows: "customer_state", cols: "time", tl: "quarter", m: "late_rate" }),
    [drill, setDrill] = useState([]),
    [view, setView] = useState("table"),
    [sqlOpen, setSqlOpen] = useState(false);
  const metadataState = useData((signal) => getOlapMetadata(signal), [], sim);
  const metadata = metadataState.data;
  const timeOptions = makeTimeOptions(metadata?.time_range);
  const filters = {
    ...fl,
    from: fl.from || timeOptions.month[0] || "",
    to: fl.to || timeOptions.month[timeOptions.month.length - 1] || "",
  };
  const { data, loading, error, retry } = useData(
    async (signal) => {
      if (!metadata || !filters.from || !filters.to) return null;
      if (filters.from > filters.to) {
        return { ck: [], body: [], colTot: [], grand: { n: 0, [cfg.m]: 0 }, cutR: false, cutC: false, payload: null };
      }
      const bounds = queryBounds(filters, drill);
      const payloadFilters = {
        customer_states: filters.cstates,
        seller_states: filters.sstates,
        categories: filters.categories,
      };
      const measures = [...new Set([cfg.m, "total_orders"])];
      const query = (dimensions) => ({
        time_mode: cfg.tl,
        ...bounds,
        dimensions: [...new Set(dimensions.map((dimension) => DIMENSION_KEYS[dimension]))],
        measures,
        filters: payloadFilters,
      });
      const cellPayload = query([cfg.rows, ...(cfg.cols === "none" ? [] : [cfg.cols])]);
      const [cellResult, rowResult, colResult] = await Promise.all([
        postOlapQuery(cellPayload, signal),
        postOlapQuery(query([cfg.rows]), signal),
        cfg.cols === "none" ? Promise.resolve(null) : postOlapQuery(query([cfg.cols]), signal),
      ]);
      const rows = cellResult.data;
      const rowTotals = new Map(rowResult.data.map((row) => [
        dimensionValue(row, cfg.rows, cfg.tl), toCell(row, cfg.m),
      ]));
      const colTotals = cfg.cols === "none"
        ? null
        : new Map(colResult.data.map((row) => [
            dimensionValue(row, cfg.cols, cfg.tl), toCell(row, cfg.m),
          ]));
      const groupCounts = (dimension) => {
        const counts = new Map();
        rows.forEach((row) => {
          const value = dimensionValue(row, dimension, cfg.tl);
          counts.set(value, (counts.get(value) || 0) + (Number(row.total_orders) || 0));
        });
        return counts;
      };
      const order = (counts, dimension) => [...counts.keys()].sort((a, b) =>
        dimension === "time" ? a.localeCompare(b) : counts.get(b) - counts.get(a) || a.localeCompare(b),
      );
      const allR = order(groupCounts(cfg.rows), cfg.rows);
      const allC = cfg.cols === "none" ? ["Tất cả"] : order(groupCounts(cfg.cols), cfg.cols);
      const grouped = new Map();
      rows.forEach((row) => {
        const rowKey = dimensionValue(row, cfg.rows, cfg.tl);
        const colKey = cfg.cols === "none" ? "Tất cả" : dimensionValue(row, cfg.cols, cfg.tl);
        grouped.set(`${rowKey}|${colKey}`, toCell(row, cfg.m));
      });
      const rk = allR.slice(0, 30),
        ck = allC.slice(0, 12);
      return {
        ck,
        body: rk.map((k) => ({
          k,
          cells: ck.map((c) => grouped.get(`${k}|${c}`) || { n: 0, [cfg.m]: 0 }),
          tot: rowTotals.get(k) || { n: 0, [cfg.m]: 0 },
        })),
        colTot: cfg.cols === "none"
          ? [sumCells([...rowTotals.values()], cfg.m)]
          : ck.map((c) => colTotals.get(c) || { n: 0, [cfg.m]: 0 }),
        grand: sumCells([...rowTotals.values()], cfg.m),
        cutR: allR.length > 30,
        cutC: allC.length > 12,
        payload: cellPayload,
      };
    },
    [metadata?.time_range?.min_month, metadata?.time_range?.max_month, filters, cfg, drill],
    sim,
  );
  const set = (p) => {
    setCfg({ ...cfg, ...p });
    setDrill([]);
  };
  const setLevel = (l) => {
    const o = timeOptions[l];
    if (!o.length) return;
    setFl({ ...fl, level: l, from: o[0], to: o[o.length - 1] });
    setDrill([]);
  };
  const resetAll = () => {
    setFl({
      level: "month",
      from: timeOptions.month[0] || "",
      to: timeOptions.month[timeOptions.month.length - 1] || "",
      sstates: [], cstates: [], categories: [],
    });
    setCfg({ rows: "customer_state", cols: "time", tl: "quarter", m: "late_rate" });
    setDrill([]);
  };
  const [mName, mFmt] = MEAS[cfg.m];
  const val = (cell) => cell?.n ? mFmt(cell[cfg.m]) : "—";
  const nums = data
      ? data.body.flatMap((b) =>
          b.cells.filter((c) => c.n).map((c) => Number(c[cfg.m]) || 0),
        )
      : [],
    mx = Math.max(...nums, 1e-9),
    mn = Math.min(...nums, 0);
  const rel = (c) => ((Number(c[cfg.m]) || 0) - mn) / (mx - mn || 1);
  const heat = (c) => ({
    background:
      view === "heat" && c.n ? `rgba(15,118,110,${0.08 + 0.7 * rel(c)})` : "",
    color: view === "heat" && c.n && rel(c) > 0.6 ? "#fff" : "",
  });
  const drillInto = (v) => {
    if (cfg.rows === "time" && NEXT[cfg.tl]) {
      setDrill([...drill, { level: cfg.tl, value: v }]);
      setCfg({ ...cfg, tl: NEXT[cfg.tl] });
    }
  };
  const rollUp = (i) => {
    const lv = drill[i]?.level || cfg.tl;
    setDrill(drill.slice(0, i));
    setCfg({ ...cfg, tl: lv });
  };
  const bad = filters.from > filters.to,
    opts = timeOptions[filters.level];
  const isRate = cfg.m === "late_rate";
  const csv = () => {
    const l = [
      [DIMS[cfg.rows], ...data.ck, "Tổng"],
      ...data.body.map((b) => [b.k, ...b.cells.map(val), val(b.tot)]),
    ];
    const u = URL.createObjectURL(
      new Blob(
        ["\ufeff" + l.map((r) => r.map((x) => `"${x}"`).join(",")).join("\n")],
        { type: "text/csv" },
      ),
    );
    const a = document.createElement("a");
    a.href = u;
    a.download = "olap.csv";
    a.click();
    URL.revokeObjectURL(u);
  };
  if (metadataState.error) return <Errored msg={metadataState.error} retry={metadataState.retry} />;
  if (metadataState.loading || !metadata) return <Skeleton h={300} />;
  if (!timeOptions.month.length) return <Empty msg="Không có dữ liệu thời gian từ backend" />;
  return (
    <div className="space-y-3">
      <section className="panel p-3 space-y-3" aria-label="Bộ lọc và cấu hình">
        <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
          <span className="text-sm font-semibold self-center">
            Bộ lọc (slice / dice)
          </span>
          <label className="text-xs text-slate-600">
            Mức thời gian
            <br />
            <select
              className="sel"
              value={filters.level}
              onChange={(e) => setLevel(e.target.value)}
            >
              {Object.entries(LV_NAME)
                .reverse()
                .map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Từ
            <br />
            <select
              className="sel"
              value={filters.from}
              onChange={(e) => {
                setFl({ ...fl, from: e.target.value });
                setDrill([]);
              }}
            >
              {opts.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-600">
            Đến
            <br />
            <select
              className="sel"
              value={filters.to}
              onChange={(e) => {
                setFl({ ...fl, to: e.target.value });
                setDrill([]);
              }}
            >
              {opts.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
          <MultiSelect
            label="Bang người bán"
            options={metadata.seller_states}
            value={fl.sstates}
            onChange={(v) => setFl({ ...fl, sstates: v })}
          />
          <MultiSelect
            label="Bang khách hàng"
            options={metadata.states}
            value={fl.cstates}
            onChange={(v) => setFl({ ...fl, cstates: v })}
          />
          <MultiSelect
            label="Danh mục"
            options={metadata.categories}
            value={fl.categories}
            onChange={(v) => setFl({ ...fl, categories: v })}
          />
          {bad && (
            <span className="text-xs text-red-700 font-medium" role="alert">
              “Từ” đang sau “Đến” – hãy chọn lại.
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-x-5 gap-y-2 border-t border-slate-100 pt-3">
          <span className="text-sm font-semibold self-center">Bảng</span>
          <DimensionPick
            label="Hàng"
            field="rows"
            config={cfg}
            onChange={(value) => set({ rows: value })}
          />
          <DimensionPick
            label="Cột"
            field="cols"
            none
            config={cfg}
            onChange={(value) => set({ cols: value })}
          />
          {(cfg.rows === "time" || cfg.cols === "time") && (
            <div className="text-xs text-slate-600">
              Mức thời gian trong bảng
              <div className="flex gap-1 mt-0.5">
                {Object.keys(LV_NAME)
                  .reverse()
                  .map((l) => (
                    <button
                      key={l}
                      className={"btn " + (cfg.tl === l ? "btn-main" : "")}
                      onClick={() => {
                        setDrill([]);
                        setCfg({ ...cfg, tl: l });
                      }}
                    >
                      {LV_NAME[l]}
                    </button>
                  ))}
              </div>
            </div>
          )}
          <label className="text-xs text-slate-600">
            Chỉ số
            <br />
            <select
              className="sel mt-0.5"
              value={cfg.m}
              onChange={(e) => set({ m: e.target.value })}
            >
              {Object.entries(MEAS).map(([k, [n]]) => (
                <option key={k} value={k}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" onClick={resetAll}>
            Đặt lại
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span className="text-slate-500">Truy vấn mẫu:</span>
          {PRESETS.map((p) => (
            <button
              key={p.t}
              className="underline text-teal-800 hover:text-teal-950"
              onClick={() => {
                setDrill([]);
                setCfg({ rows: p.rows, cols: p.cols, tl: p.tl, m: p.m });
              }}
            >
              {p.t}
            </button>
          ))}
        </div>
      </section>
      <section className="min-w-0 space-y-3">
        <div className="panel p-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm">
            {mName} theo <b>{DIMS[cfg.rows]}</b>
            {cfg.cols !== "none" && (
              <>
                {" "}
                × <b>{DIMS[cfg.cols]}</b>
              </>
            )}
            {drill.length > 0 && (
              <nav
                className="text-xs mt-1 text-slate-600"
                aria-label="Phân cấp thời gian"
              >
                <button className="underline" onClick={() => rollUp(0)}>
                  Tất cả
                </button>
                {drill.map((d, i) => (
                  <span key={i}>
                    {" "}
                    ›{" "}
                    <button className="underline" onClick={() => rollUp(i + 1)}>
                      {d.value}
                    </button>
                  </span>
                ))}
                <button
                  className="btn ml-2"
                  onClick={() => rollUp(drill.length - 1)}
                >
                  ▲ Roll-up
                </button>
              </nav>
            )}
          </div>
          <div className="flex items-center gap-1">
            {[
              ["table", "Bảng"],
              ["heat", "Heatmap"],
              ["chart", "Biểu đồ"],
            ].map(([k, t]) => (
              <button
                key={k}
                className={"btn " + (view === k ? "btn-main" : "")}
                onClick={() => setView(k)}
              >
                {t}
              </button>
            ))}
            <button className="btn" disabled={!data} onClick={csv}>
              Xuất CSV
            </button>
          </div>
        </div>
        {error ? (
          <Errored msg={error} retry={retry} />
        ) : loading || !data ? (
          <Skeleton h={300} />
        ) : !data.grand.n ? (
          <Empty reset={resetAll} />
        ) : view === "chart" ? (
          <div className="panel p-4 h-80">
            <ResponsiveContainer>
              <BarChart
                data={data.body.map((b) => ({
                  k: b.k,
                  v: isRate ? b.tot[cfg.m] / 100 : b.tot[cfg.m],
                }))}
              >
                <CartesianGrid vertical={false} stroke="#e5e9ec" />
                <XAxis dataKey="k" tick={{ fontSize: 11 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => (isRate ? pct(v) : v)}
                />
                <Tooltip
                  formatter={(v) => (isRate ? pct(v) : num(v, 2))}
                />
                <Bar dataKey="v" name={mName} fill="#0f766e" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="panel overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left py-2 px-3">{DIMS[cfg.rows]}</th>
                  {data.ck.map((c) => (
                    <th key={c} className="text-right px-3">
                      {c}
                    </th>
                  ))}
                  <th className="text-right px-3 bg-slate-100">Tổng</th>
                </tr>
              </thead>
              <tbody>
                {data.body.map((b) => (
                  <tr key={b.k} className="border-t border-slate-100">
                    <th className="text-left py-2 px-3 font-medium">
                      {cfg.rows === "time" && NEXT[cfg.tl] ? (
                        <button
                          className="underline decoration-dotted hover:text-teal-800"
                          title="Drill-down xuống mức thấp hơn"
                          onClick={() => drillInto(b.k)}
                        >
                          ▼ {b.k}
                        </button>
                      ) : (
                        b.k
                      )}
                    </th>
                    {b.cells.map((c, i) => (
                      <td
                        key={i}
                        className={
                          "text-right px-3 " +
                          (c.n && c.n < 15 ? "text-slate-400 italic" : "")
                        }
                        style={heat(c)}
                        title={
                          c.n
                            ? `${c.n} đơn${c.n < 15 ? " – mẫu nhỏ" : ""}`
                            : "Không có dữ liệu"
                        }
                      >
                        {val(c)}
                      </td>
                    ))}
                    <td className="text-right px-3 font-semibold bg-slate-50">
                      {val(b.tot)}
                    </td>
                  </tr>
                ))}
                <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
                  <th className="text-left py-2 px-3">Tổng</th>
                  {data.colTot.map((c, i) => (
                    <td key={i} className="text-right px-3">
                      {val(c)}
                    </td>
                  ))}
                  <td className="text-right px-3">{val(data.grand)}</td>
                </tr>
              </tbody>
            </table>
            <p className="text-[11px] text-slate-500 p-2">
              Chữ nghiêng xám: ô dưới 15 đơn (mẫu nhỏ). Rê chuột vào ô để xem số
              đơn.
              {data.cutR &&
                " Chỉ hiển thị 30 hàng nhiều đơn nhất (hàng Tổng vẫn tính trên toàn bộ)."}
              {data.cutC && " Chỉ hiển thị 12 cột đầu."}
              {cfg.rows === "time" &&
                NEXT[cfg.tl] &&
                " Bấm ▼ ở hàng thời gian để drill-down."}
            </p>
          </div>
        )}
        <div className="panel">
          <button
            className="w-full text-left px-3 py-2 text-sm font-medium flex justify-between"
            aria-expanded={sqlOpen}
            onClick={() => setSqlOpen(!sqlOpen)}
          >
            Payload API<span>{sqlOpen ? "▴" : "▾"}</span>
          </button>
          {sqlOpen && (
            <pre className="px-3 pb-3 text-xs overflow-x-auto text-slate-700">
              {JSON.stringify(data?.payload, null, 2)}
            </pre>
          )}
        </div>
      </section>
    </div>
  );
}
