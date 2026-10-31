import React from 'react';
import { ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Card } from '../components/Card';
import { MONTHS, BLUE, RED, AMBER, GRID, MUTED } from '../data/mockData';

export default function DashboardView({ f }) {
  const k = (f.year === 'All' ? 1 : f.year === '2017' ? 0.45 : 0.55) * (f.quarter === 'All' ? 1 : 0.25) * (f.state === 'All' ? 1 : 0.3);
  const month = f.month === 'All' ? 1 : 0.2;
  const sc = k * month;
  const fmt = n => Math.round(n).toLocaleString();

  const cards = [
    { l: 'Total Orders', v: fmt(99441 * sc), s: 'delivered & shipped' },
    { l: 'SLA Violation Rate', v: (8.1 + (f.state === 'RJ' ? 3.2 : f.state === 'SP' ? -1.1 : 0.6)).toFixed(1) + '%', s: 'vs 7.5% target', warn: true },
    { l: 'Avg Freight Cost', v: 'R$ ' + (f.state === 'All' ? 19.9 : 21.4).toFixed(2), s: 'per order' },
    { l: 'Avg Transit Time', v: (12.1 + (f.state === 'RJ' ? 1.8 : 0)).toFixed(1) + ' days', s: 'purchase → delivery' },
  ];

  const states = [['SP', 3420], ['RJ', 2315], ['MG', 1180], ['RS', 640], ['PR', 520]]
    .filter(([s]) => f.state === 'All' || s === f.state)
    .map(([s, v]) => ({ s, v: Math.round(v * (f.year === 'All' ? 1 : 0.5) * (f.quarter === 'All' ? 1 : 0.25)) }));

  const trend = MONTHS.map((m, i) => ({ m, v: Math.round((260 + 90 * Math.sin(i / 1.8) + i * 14) * (f.state === 'All' ? 1 : 0.35)) }));
  const causes = [{ n: 'Carrier', v: 52, c: BLUE }, { n: 'Seller', v: 33, c: AMBER }, { n: 'Weather', v: 15, c: RED }];
  const tip = { contentStyle: { borderRadius: 10, border: '1px solid #e8edf3', boxShadow: 'none', fontSize: 12 } };

  return (
    /* Thêm w-full max-w-none để trải dài full màn hình, loại bỏ khoảng trắng hai bên */
    <div className="space-y-6 w-full max-w-none animate-fadeIn">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 w-full">
        {cards.map(c => (
          <div key={c.l} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition">
            <div className="text-xs text-slate-500">{c.l}</div>
            <div className={`text-2xl font-semibold mt-2 ${c.warn ? 'text-red-400' : 'text-slate-800'}`}>{c.v}</div>
            <div className="text-xs text-slate-400 mt-1">{c.s}</div>
          </div>
        ))}
      </div>

      {/* Biểu đồ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 w-full">
        <Card title="Top States by Delay Count">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={states} barSize={28}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="s" tick={{ fontSize: 12, fill: MUTED }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: MUTED }} axisLine={false} tickLine={false} />
                <Tooltip {...tip} cursor={{ fill: '#f1f5f9' }} />
                <Bar dataKey="v" name="Delays" fill={BLUE} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Biểu đồ Delay Trend over Time đã được thêm domain cho YAxis để không bị chạm đỉnh */}
        <Card title="Delay Trend over Time">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="m" tick={{ fontSize: 12, fill: MUTED }} axisLine={false} tickLine={false} />
                <YAxis 
                  tick={{ fontSize: 12, fill: MUTED }} 
                  axisLine={false} 
                  tickLine={false} 
                  domain={[0, 'dataMax + 100']} 
                />
                <Tooltip {...tip} />
                <Line type="monotone" dataKey="v" name="Delays" stroke={BLUE} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Root Causes of Delays">
          <div className="h-52 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={causes} dataKey="v" nameKey="n" innerRadius={55} outerRadius={80} paddingAngle={3} stroke="none">
                  {causes.map(c => <Cell key={c.n} fill={c.c} />)}
                </Pie>
                <Tooltip {...tip} formatter={v => v + '%'} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 text-xs text-slate-500 mt-2">
            {causes.map(c => (
              <span key={c.n} className="flex items-center gap-1.5">
                <i className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c.c }} />
                {c.n} {c.v}%
              </span>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}