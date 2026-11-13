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
import {
  APP_STATES as STATES,
  TIME_OPTS,
  LV_NAME,
  OLAP_DIMS as DIMS,
  NEXT,
  OLAP_MEAS as MEAS,
  MASS_BANDS,
  VOLUME_BANDS,
  MEAS_SQL,
  DIM_SQL,
  TL_SQL,
  DEF_O,
  DEF_CFG,
  PRESETS,
  dateRange,
  massBand,
  olapRows,
  volumeBand,
} from "../data/mockData.jsx";
import {
  agg,
  pct,
  num,
  useData,
  MultiSelect,
  Errored,
  Skeleton,
  Empty,
} from "../utils/utils.js";

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
  const [fl, setFl] = useState(DEF_O),
    [cfg, setCfg] = useState(DEF_CFG),
    [drill, setDrill] = useState([]),
    [view, setView] = useState("table"),
    [sqlOpen, setSqlOpen] = useState(false);
  const key = (r, d) =>
    d === "time"
      ? r[cfg.tl]
      : d === "mass"
        ? massBand(r.massKg)
        : d === "volume"
          ? volumeBand(r.volumeL)
          : r[d];
  const aggregate = (rows) => ({
    ...agg(rows),
    mass: rows.length
      ? rows.reduce((sum, row) => sum + row.massKg, 0) / rows.length
      : null,
    volume: rows.length
      ? rows.reduce((sum, row) => sum + row.volumeL, 0) / rows.length
      : null,
  });
  const { data, loading, error, retry } = useData(
    () => {
      const rows = olapRows(fl, drill),
        byRow = {},
        byCol = {},
        g = {};
      rows.forEach((r) => {
        const rk = key(r, cfg.rows),
          ck = cfg.cols === "none" ? "Tất cả" : key(r, cfg.cols);
        (byRow[rk] ??= []).push(r);
        (byCol[ck] ??= []).push(r);
        (g[rk + "|" + ck] ??= []).push(r);
      });
      const order = (o, dim) =>
        dim === "time"
          ? Object.keys(o).sort()
          : Object.keys(o).sort((a, b) => o[b].length - o[a].length);
      const allR = order(byRow, cfg.rows),
        allC = order(byCol, cfg.cols),
        rk = allR.slice(0, 30),
        ck = allC.slice(0, 12);
      return {
        ck,
        body: rk.map((k) => ({
          k,
          cells: ck.map((c) => aggregate(g[k + "|" + c] || [])),
          tot: aggregate(byRow[k]),
        })),
        colTot: ck.map((c) => aggregate(byCol[c])),
        grand: aggregate(rows),
        cutR: allR.length > 30,
        cutC: allC.length > 12,
      };
    },
    [fl, cfg, drill],
    sim,
  );
  const set = (p) => {
    setCfg({ ...cfg, ...p });
    setDrill([]);
  };
  const setLevel = (l) => {
    const o = TIME_OPTS[l];
    setFl({ ...fl, level: l, from: o[0], to: o[o.length - 1] });
    setDrill([]);
  };
  const resetAll = () => {
    setFl(DEF_O);
    setCfg(DEF_CFG);
    setDrill([]);
  };
  const [mName, mFmt] = MEAS[cfg.m],
    val = (a) => (a.n ? mFmt(a) : "—");
  const nums = data
      ? data.body.flatMap((b) =>
          b.cells.filter((c) => c.n).map((c) => c[cfg.m]),
        )
      : [],
    mx = Math.max(...nums, 1e-9),
    mn = Math.min(...nums, 0);
  const rel = (c) => (c[cfg.m] - mn) / (mx - mn || 1);
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
  const bad = fl.from > fl.to,
    opts = TIME_OPTS[fl.level];
  const gcols = [cfg.rows, cfg.cols !== "none" ? cfg.cols : null]
    .filter(Boolean)
    .map((d) => (d === "time" ? TL_SQL[cfg.tl] : DIM_SQL[d]))
    .join(", ");
  const where = [
    dateRange(fl.level, fl.from, fl.to),
    ...drill.map((d) => dateRange(d.level, d.value, d.value)),
    fl.sstates.length &&
      `sl.state IN (${fl.sstates.map((s) => `'${s}'`).join(", ")})`,
    fl.cstates.length &&
      `c.state IN (${fl.cstates.map((s) => `'${s}'`).join(", ")})`,
    fl.massBands.length &&
      `${DIM_SQL.mass} IN (${fl.massBands.map((s) => `'${s}'`).join(", ")})`,
    fl.volumeBands.length &&
      `${DIM_SQL.volume} IN (${fl.volumeBands.map((s) => `'${s}'`).join(", ")})`,
    fl.lateOnly && "f.delay_days > 0",
  ].filter(Boolean);
  const sql = `-- Minh hoạ truy vấn tương ứng trên star schema\nSELECT ${gcols}, ${MEAS_SQL[cfg.m]} AS ${cfg.m}\nFROM Fact_Delivery_SLA f\nJOIN Dim_Time t ON f.time_id = t.time_id\nJOIN Dim_Location c ON f.customer_location_id = c.location_id\nJOIN Dim_Location sl ON f.seller_location_id = sl.location_id\nJOIN Dim_Product p ON f.product_id = p.product_id\nWHERE ${where.join("\n  AND ")}\nGROUP BY ${gcols};`;
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
              value={fl.level}
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
              value={fl.from}
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
              value={fl.to}
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
            options={STATES}
            value={fl.sstates}
            onChange={(v) => setFl({ ...fl, sstates: v })}
          />
          <MultiSelect
            label="Bang khách hàng"
            options={STATES}
            value={fl.cstates}
            onChange={(v) => setFl({ ...fl, cstates: v })}
          />
          <MultiSelect
            label="Khối lượng"
            options={MASS_BANDS}
            value={fl.massBands}
            onChange={(v) => setFl({ ...fl, massBands: v })}
          />
          <MultiSelect
            label="Thể tích"
            options={VOLUME_BANDS}
            value={fl.volumeBands}
            onChange={(v) => setFl({ ...fl, volumeBands: v })}
          />
          <label className="flex items-center gap-1.5 text-xs pb-1.5">
            <input
              type="checkbox"
              checked={fl.lateOnly}
              onChange={(e) => setFl({ ...fl, lateOnly: e.target.checked })}
            />
            Chỉ đơn trễ
          </label>
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
                data={data.body.map((b) => ({ k: b.k, v: b.tot[cfg.m] }))}
              >
                <CartesianGrid vertical={false} stroke="#e5e9ec" />
                <XAxis dataKey="k" tick={{ fontSize: 11 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => (cfg.m === "rate" ? pct(v) : v)}
                />
                <Tooltip
                  formatter={(v) => (cfg.m === "rate" ? pct(v) : num(v, 2))}
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
            SQL tương ứng<span>{sqlOpen ? "▴" : "▾"}</span>
          </button>
          {sqlOpen && (
            <pre className="px-3 pb-3 text-xs overflow-x-auto text-slate-700">
              {sql}
            </pre>
          )}
        </div>
      </section>
    </div>
  );
}
