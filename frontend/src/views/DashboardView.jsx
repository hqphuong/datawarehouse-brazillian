// src/views/DashboardView.jsx
import React, { useState, useEffect } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line, Legend } from 'recharts';
import { MONTHS, LV_NAME, STATES, RAW, agg, pct, num, int } from '../data/mockData.jsx';
import { useData } from '../hooks/useData.js';

const DEFAULT_F = { level: 'month', from: MONTHS[0], to: MONTHS[MONTHS.length - 1], states: [], lateOnly: false };

export default function DashboardView({ year, setYear, sim, goDss, f, setF, sel, setSel }) {
  // Nếu f chưa có từ App chung, ta dùng local hoặc prop từ App. Ở đây nhận f, setF, sel, setSel từ App hoặc dùng mặc định.
  const currentF = f || DEFAULT_F;
  
  const { data, loading, error, retry } = useData(() => {
    // Lọc theo năm nếu ở component cha có chọn năm hoặc dùng f
    const rows = RAW.filter(r => (year === 'all' || r.year === year) && r[currentF.level] >= currentF.from && r[currentF.level] <= currentF.to && (!currentF.states.length || currentF.states.includes(r.state)) && (!currentF.lateOnly || r.late) && (!sel || r[currentF.level] === sel));
    const base = RAW.filter(r => (year === 'all' || r.year === year) && r[currentF.level] >= currentF.from && r[currentF.level] <= currentF.to && (!currentF.states.length || currentF.states.includes(r.state)) && (!currentF.lateOnly || r.late));
    
    const periods = {}; base.forEach(r => (periods[r[currentF.level]] ?? []).push(r));
    const trend = Object.keys(periods).sort().map(k => ({ label: k, ...agg(periods[k]) }));
    
    const byState = {}; rows.forEach(r => (byState[r.state] ?? []).push(r));
    const states = Object.entries(byState).map(([s, a]) => ({ state: s, ...agg(a) })).sort((a, b) => b.rate - a.rate);
    
    return { kpi: agg(rows), trend, states, rows };
  }, [year, currentF, sel], sim);

  const [page, setPage] = useState(0);
  const [sort, setSort] = useState({ k: 'delay', d: -1 });
  useEffect(() => setPage(0), [currentF, sel, year]);

  if (error) return <div className="panel p-10 text-center"><p className="font-semibold text-red-600">Không tải được dữ liệu: {error}</p><button className="btn btn-main mt-3" onClick={retry}>Tải lại</button></div>;
  if (loading || !data) return <div className="space-y-4"><div className="panel animate-pulse bg-slate-100 h-32" /><div className="panel animate-pulse bg-slate-100 h-64" /></div>;
  
  const { kpi, trend, states, rows } = data;
  const MIN = 15;
  const sorted = [...rows].sort((a, b) => (a[sort.k] > b[sort.k] ? 1 : -1) * sort.d), PS = 8, pages = Math.ceil(sorted.length / PS);
  const th = (k, t, r) => <th key={k} className={'py-2 px-3 font-semibold ' + (r ? 'text-right' : '')}><button onClick={() => setSort({ k, d: sort.k === k ? -sort.d : -1 })}>{t}{sort.k === k ? (sort.d < 0 ? ' ↓' : ' ↑') : ''}</button></th>;
  const small = [['Số đơn', int(kpi.n)], ['Thời gian vận chuyển TB', num(kpi.transit) + ' ngày'], ['Phí vận chuyển TB', 'R$ ' + num(kpi.freight, 2)], ['Điểm đánh giá TB', num(kpi.review, 2) + ' / 5']];

  return (
    <div className="space-y-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_1fr] gap-4">
        <div className="panel p-4 flex items-center gap-4 lg:row-span-2">
          <div>
            <div className="text-sm text-slate-600">Tỷ lệ giao trễ</div>
            <div className="text-5xl font-bold text-orange-700 leading-tight">{pct(kpi.rate)}</div>
            <div className="text-xs text-slate-500">{int(kpi.late)} / {int(kpi.n)} đơn</div>
          </div>
          <div className="flex-1 h-24" aria-label="Xu hướng tỷ lệ trễ">
            <ResponsiveContainer><LineChart data={trend}><Line type="monotone" dataKey="rate" stroke="#c2410c" strokeWidth={2} dot={false}/><Tooltip formatter={v => pct(v)} labelFormatter={l => l}/></LineChart></ResponsiveContainer>
          </div>
        </div>
        {small.map(([t, v]) => <div key={t} className="panel p-3"><div className="text-xs text-slate-600">{t}</div><div className="text-xl font-semibold mt-0.5">{v}</div></div>)}
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className="panel p-4">
          <h2 className="font-semibold">Thời gian từng giai đoạn theo {LV_NAME[currentF.level]?.toLowerCase()}</h2>
          <p className="text-xs text-slate-500 mb-2">Trung bình số ngày mỗi giai đoạn. Nhấp một cột để xem đơn của kỳ đó.</p>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={trend} onClick={s => s && s.activeLabel && setSel && setSel(s.activeLabel)}>
                <CartesianGrid vertical={false} stroke="#e5e9ec"/><XAxis dataKey="label" tick={{fontSize: 11}}/><YAxis tick={{fontSize: 11}} unit="d"/>
                <Tooltip formatter={v => num(v) + ' days'}/><Legend wrapperStyle={{fontSize: 12}}/>
                <Bar name="Duyệt đơn" dataKey="appr" stackId="a" fill="#94a3b8" cursor="pointer"/>
                <Bar name="Chuẩn bị hàng" dataKey="prep" stackId="a" fill="#0f766e" cursor="pointer"/>
                <Bar name="Vận chuyển" dataKey="transit" stackId="a" fill="#b45309" cursor="pointer"/>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="panel p-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="font-semibold">Tỷ lệ trễ theo bang khách hàng</h2>
              <p className="text-xs text-slate-500 mb-2">Bang có dưới {MIN} đơn được đánh dấu “mẫu nhỏ”.</p>
            </div>
            <button className="btn" onClick={() => goDss && goDss()}>Mở trong DSS</button>
          </div>
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <tbody>
                {states.map(s => (
                  <tr key={s.state} className="border-t border-slate-100">
                    <td className="py-1.5 w-10 font-medium">{s.state}</td>
                    <td className="py-1.5"><div className="h-3 bg-slate-100 rounded-sm"><div className="h-3 rounded-sm" style={{width: Math.min(100, s.rate * 250) + '%', background: s.n < MIN ? '#b8c2cc' : '#c2410c'}}/></div></td>
                    <td className="py-1.5 px-2 text-right w-14">{pct(s.rate)}</td>
                    <td className="py-1.5 text-right text-slate-500 w-20">{int(s.n)} đơn{s.n < MIN && <span title="Mẫu nhỏ, tỷ lệ chưa ổn định"> ⚠</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Detailed Orders Table */}
      <section className="panel p-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="font-semibold">Chi tiết đơn hàng{sel ? ` – kỳ ${sel}` : ''}</h2>
          <span className="text-xs text-slate-500">{int(rows.length)} đơn</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50">
              <tr>{th('id', 'Mã đơn')}{th('month', 'Tháng')}{th('state', 'Bang khách')}{th('seller_state', 'Bang bán')}{th('appr', 'Duyệt (ngày)', 1)}{th('prep', 'Chuẩn bị (ngày)', 1)}{th('transit', 'Vận chuyển (ngày)', 1)}{th('review', 'Đánh giá', 1)}{th('delay', 'Trạng thái', 1)}</tr>
            </thead>
            <tbody>
              {sorted.slice(page * PS, page * PS + PS).map(o => (
                <tr key={o.id} className="border-t border-slate-100">
                  <td className="py-2 px-3 font-mono">{o.id}</td>
                  <td className="px-3">{o.month}</td>
                  <td className="px-3">{o.state}</td>
                  <td className="px-3">{o.seller_state}</td>
                  <td className="px-3 text-right">{o.appr}</td>
                  <td className="px-3 text-right">{o.prep}</td>
                  <td className="px-3 text-right">{o.transit}</td>
                  <td className="px-3 text-right">{o.review}/5</td>
                  <td className="px-3 text-right"><span className={'px-2 py-0.5 rounded ' + (o.late ? 'bg-orange-100 text-orange-900' : 'bg-teal-50 text-teal-900')}>{o.late ? `Trễ ${o.delay} ngày` : 'Đúng hạn'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-end items-center gap-2 mt-2 text-xs">
          <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Trước</button>
          Trang {page + 1}/{pages || 1}
          <button className="btn" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Sau</button>
        </div>
      </section>
    </div>
  );
}