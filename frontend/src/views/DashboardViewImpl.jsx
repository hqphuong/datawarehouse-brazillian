import {
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
} from "recharts";
import {
  byYear,
  routeStats,
  MIN_ORDERS,
  LOW_SAMPLE,
} from "../data/mockData.jsx";
import {
  agg,
  pct,
  num,
  int,
  useData,
  YearSel,
  Skeleton,
  Errored,
  Pill,
} from "../utils/utils.js";

export default function DashboardView({ year, setYear, sim, goDss }) {
  const { data, loading, error, retry } = useData(
    () => {
      const rows = byYear(year),
        g = {};
      rows.forEach((r) => (g[r.month] ??= []).push(r));
      const trend = Object.keys(g)
        .sort()
        .map((k) => ({ label: k, ...agg(g[k]) }));
      const { L, list } = routeStats(rows);
      return {
        kpi: agg(rows),
        trend,
        L,
        top: [...list].sort((a, b) => b.p - a.p).slice(0, 5),
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
  const { kpi, trend, top } = data;
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
        <YearSel year={year} setYear={setYear} />
        <p className="text-xs text-slate-500 max-w-3xl">
          Tỷ lệ trễ = đơn-tuyến giao sau ngày dự kiến ({"delay_days > 0"}) ÷
          đơn-tuyến đã giao; tuyến = bang người bán → bang khách hàng. Theo báo
          cáo (dữ liệu thật): 8,1556% theo đơn-tuyến, 8,1950% nếu tính theo đơn
          duy nhất. Dữ liệu mẫu: 1 đơn = 1 tuyến.
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
            Cho biết vấn đề đang tăng hay giảm; rê chuột để xem số đơn của
            tháng.
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
                    pct(v) + ` (${p.payload.late}/${p.payload.n} đơn)`,
                    "Tỷ lệ trễ",
                  ]}
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
          <h2 className="font-semibold">5 tuyến có tỷ lệ trễ cao nhất</h2>
          <p className="text-xs text-slate-500 mb-2">
            Chỉ xét tuyến từ {MIN_ORDERS} đơn-tuyến trở lên (báo cáo: 100).
            Tuyến dưới {LOW_SAMPLE} đơn gắn “Mẫu nhỏ”.
          </p>
          <table className="w-full text-xs">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1">Tuyến</th>
                <th className="text-right">Đơn</th>
                <th className="text-right">Trễ</th>
                <th className="text-right">Tỷ lệ</th>
                <th />
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
                  <td className="text-right">
                    <button className="btn" onClick={() => goDss(s.route)}>
                      Mở trong DSS
                    </button>
                  </td>
                </tr>
              ))}
              {!top.length && (
                <tr>
                  <td colSpan="5" className="py-4 text-center text-slate-500">
                    Chưa có tuyến đủ mẫu.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
