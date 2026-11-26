import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  ReferenceLine,
} from "recharts";
import {
  getDashboardOverview,
  getDssAttribution,
  getOlapMetadata,
  getRegions,
  getSlaBreakdown,
} from "../data/api.js";
import { routeLabel } from "../data/dssAdapter.js";
import {
  pct,
  num,
  int,
  useData,
  YearSel,
  Skeleton,
  Errored,
  Pill,
} from "../utils/utils.js";

const MIN_ORDERS = 100;
const LOW_SAMPLE = 200;
const TREND_MIN_ORDERS = 50;

function makeYearOptions(timeRange) {
  const first = Number(timeRange?.min_month?.slice(0, 4));
  const last = Number(timeRange?.max_month?.slice(0, 4));
  if (!Number.isInteger(first) || !Number.isInteger(last) || first > last) return [];
  return Array.from({ length: last - first + 1 }, (_, index) => String(first + index));
}

export default function DashboardView({ year, setYear, sim, goDss }) {
  const { data, loading, error, retry } = useData(
    async (signal) => {
      const bounds = year === "all"
        ? {}
        : { from: `${year}-01-01`, to: `${year}-12-31` };
      const dateFilters = year === "all"
        ? {}
        : { start_date: `${year}-01-01`, end_date: `${year}-12-31` };
      const [overview, sla, regions, attribution, metadata] = await Promise.all([
        getDashboardOverview({ time_mode: "month", ...bounds }, signal),
        getSlaBreakdown(dateFilters, signal),
        getRegions(dateFilters, signal),
        getDssAttribution(year, 0.5, signal),
        getOlapMetadata(signal),
      ]);
      const kpis = overview.kpis;
      const trend = overview.late_trend.map((period) => ({
        label: period.month != null
          ? `${period.year}-${String(period.month).padStart(2, "0")}`
          : period.quarter != null
            ? `${period.year}-Q${period.quarter}`
            : String(period.year),
        n: period.order_count,
        late: period.late_count ?? Math.round(period.delay_rate * period.order_count),
        rate: period.delay_rate,
      })).filter((row) => row.n >= TREND_MIN_ORDERS);
      const stageBars = [
        ["Duyệt", sla.avg_approval_time],
        ["Chuẩn bị", sla.avg_prep_time],
        ["Vận chuyển", sla.avg_transit_time],
      ].map(([label, days]) => ({ label, days: Number(days) || 0 }));
      // /regions trả từng cặp bang; gộp theo bang khách hàng để xếp hạng.
      const byCustomerState = new Map();
      for (const row of regions) {
        const state = row.customer_state || "—";
        const cur = byCustomerState.get(state) || { state, n: 0, late: 0 };
        cur.n += row.order_count || 0;
        cur.late += row.late_count || 0;
        byCustomerState.set(state, cur);
      }
      const stateBars = [...byCustomerState.values()]
        .map((row) => ({
          ...row,
          rate: row.n ? row.late / row.n : 0,
        }))
        .sort((a, b) => b.rate - a.rate)
        .slice(0, 10);
      // Tỷ lệ trễ trên Dashboard dùng chung grain order-route với DSS.
      const sys = attribution.systemwide || {};
      const list = (attribution.ranked_routes || [])
        .map((row) => {
          const n = row.order_routes ?? row.orders ?? 0;
          return {
            route: routeLabel(row.route),
            n,
            k: row.late_orders ?? 0,
            p: row.late_rate ?? (n ? (row.late_orders ?? 0) / n : 0),
            low: n < LOW_SAMPLE,
          };
        })
        .filter((row) => row.n >= MIN_ORDERS);
      return {
        kpi: {
          n: sys.orders ?? 0,
          late: Math.round((sys.orders ?? 0) * (sys.late_rate ?? 0)),
          rate: sys.late_rate ?? 0,
          total: kpis.avg_delivery_time,
          appr: sla.avg_approval_time,
          prep: sla.avg_prep_time,
          transit: sla.avg_transit_time,
        },
        trend,
        top: [...list].sort((a, b) => b.p - a.p).slice(0, 10),
        stageBars,
        stateBars,
        years: makeYearOptions(metadata.time_range),
      };
    },
    [year],
    sim,
  );
  if (error) return <Errored msg={error} retry={retry} />;
  if (loading || !data)
    return (
      <div className="space-y-4">
        <Skeleton h={90} />
        <Skeleton h={300} />
      </div>
    );
  const { kpi, trend, top, stageBars, stateBars } = data;
  const stageMax = Math.max(1, ...stageBars.map((s) => s.days));
  const stateMax = Math.max(0.0001, ...stateBars.map((s) => s.rate));
  const cards = [
    ["Tổng đơn-tuyến đã giao", int(kpi.n), ""],
    [
      "Tỷ lệ giao trễ",
      pct(kpi.rate),
      `${int(kpi.late)} / ${int(kpi.n)} đơn-tuyến`,
      1,
    ],
    [
      "Thời gian giao TB",
      num(kpi.total) + " ngày",
      "Từ đặt hàng đến khi khách nhận",
    ],
    ["Duyệt thanh toán TB", num(kpi.appr) + " ngày", "Hệ thống / sàn"],
    ["Người bán chuẩn bị TB", num(kpi.prep) + " ngày", "Người bán"],
    ["Vận chuyển TB", num(kpi.transit) + " ngày", "Đơn vị vận chuyển"],
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <YearSel year={year} setYear={setYear} years={data.years} />
        <p className="text-xs text-slate-500 max-w-3xl">
          Tỷ lệ trễ = đơn-tuyến giao sau ngày dự kiến ÷ tổng đơn-tuyến; tuyến = bang
          người bán → bang khách hàng. Số liệu lấy từ API DSS để đồng nhất với trang DSS.
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {cards.map(([t, v, s, hot]) => (
          <div
            key={t}
            className={
              "panel p-3 " + (hot ? "border-orange-300 bg-orange-50" : "")
            }
          >
            <div className="text-xs text-slate-600">{t}</div>
            <div
              className={
                "text-2xl font-semibold mt-0.5 " +
                (hot ? "text-orange-800" : "")
              }
            >
              {v}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">{s}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-[1.3fr_1fr] gap-4">
        <section className="panel p-4">
          <h2 className="font-semibold">Xu hướng tỷ lệ trễ theo tháng</h2>
          <p className="text-xs text-slate-500 mb-2">
            Cho biết vấn đề đang tăng hay giảm; rê chuột để xem số đơn trễ và tổng
            số đơn-tuyến. ẩn các tháng dưới {TREND_MIN_ORDERS} đơn.
          </p>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={trend}>
                <CartesianGrid vertical={false} stroke="#e5e9ec" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => Math.round(v * 100) + "%"}
                />
                <Tooltip
                  formatter={(v, n, p) => [
                    pct(v) + ` (${p.payload.late}/${p.payload.n} đơn-tuyến)`,
                    "Tỷ lệ trễ",
                  ]}
                />
                <ReferenceLine
                  y={kpi.rate}
                  stroke="#64748b"
                  strokeDasharray="4 3"
                  label={{
                    value: `Tỷ lệ trễ chung ${pct(kpi.rate)}`,
                    position: "insideTopRight",
                    fontSize: 11,
                    fill: "#475569",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="#c2410c"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">10 tuyến có tỷ lệ trễ cao nhất</h2>
              <p className="text-xs text-slate-500 mb-2">
                Chỉ xét tuyến từ {MIN_ORDERS} đơn-tuyến trở lên. Tuyến dưới{" "}
                {LOW_SAMPLE} đơn-tuyến gắn “Mẫu nhỏ”.
              </p>
            </div>
            <button
              className="btn shrink-0"
              onClick={() => goDss && goDss()}
            >
              Mở trong DSS
            </button>
          </div>
          <table className="w-full text-xs">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Tuyến</th>
                <th className="text-right">Đơn-tuyến</th>
                <th className="text-right">Trễ</th>
                <th className="text-right">Tỷ lệ</th>
              </tr>
            </thead>
            <tbody>
              {top.map((s) => (
                <tr key={s.route} className="border-t border-slate-100">
                  <td className="py-2 font-medium">
                    {s.route}{" "}
                    {s.low && (
                      <Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700" />
                    )}
                  </td>
                  <td className="text-right">{int(s.n)}</td>
                  <td className="text-right">{int(s.k)}</td>
                  <td className="text-right font-semibold">{pct(s.p)}</td>
                </tr>
              ))}
              {!top.length && (
                <tr>
                  <td colSpan="4" className="py-4 text-center text-slate-500">
                    Chưa có tuyến đủ mẫu.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="panel p-4">
          <h2 className="font-semibold">Thời gian TB theo giai đoạn</h2>
          <p className="text-xs text-slate-500 mb-3">
            Trung bình theo đơn-tuyến, đơn vị: ngày.
          </p>
          <div className="space-y-3">
            {stageBars.map((s) => (
              <div key={s.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span>{s.label}</span>
                  <b>{num(s.days)} ngày</b>
                </div>
                <div className="h-2 rounded bg-slate-100 overflow-hidden">
                  <div
                    className="h-full bg-teal-600"
                    style={{ width: `${(s.days / stageMax) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
        <section className="panel p-4">
          <h2 className="font-semibold">Tỷ lệ trễ theo bang khách hàng (top 10)</h2>
          <p className="text-xs text-slate-500 mb-3">
            Sắp theo tỷ lệ trễ giảm dần; tính trên đơn-tuyến.
          </p>
          <div className="space-y-2">
            {stateBars.map((s) => (
              <div key={s.state}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium">{s.state}</span>
                  <span>
                    {pct(s.rate)}{" "}
                    <span className="text-slate-500">({int(s.n)} đơn-tuyến)</span>
                  </span>
                </div>
                <div className="h-2 rounded bg-slate-100 overflow-hidden">
                  <div
                    className="h-full bg-orange-500"
                    style={{ width: `${(s.rate / stateMax) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {!stateBars.length && (
              <p className="text-xs text-slate-500">Chưa có dữ liệu theo bang.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
