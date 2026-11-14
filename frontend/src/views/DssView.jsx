import React, { useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceDot } from 'recharts';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { BLUE, GRID, MUTED } from '../data/mockData-old';

export default function DSSView({ toast }) {
  const [days, setDays] = useState(2);
  const [done, setDone] = useState({});
  const base = 18.4;
  const proj = d => Math.max(4, +(base - d * 2.1 + d * d * 0.08).toFixed(1));
  const data = [0, 1, 2, 3, 4, 5].map(d => ({ d, v: proj(d) }));

  const alerts = [
    { id: 1, t: 'SP → RJ route exceeded SLA by 3 days', d: '1,240 orders affected · carrier hub congestion detected', c: 'red' },
    { id: 2, t: 'MG → BA lane forecast to breach SLA next week', d: '380 orders at risk · seller prep time above 4.5 days', c: 'amber' },
  ];
  const cls = { red: 'bg-red-50/60 border-red-100', amber: 'bg-amber-50/60 border-amber-100' };
  const ic = { red: 'text-red-400', amber: 'text-amber-500' };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full animate-fadeIn">
      <div className="space-y-4">
        <h2 className="text-sm font-medium text-slate-600">Active Alerts</h2>
        {alerts.map(a => (
          <div key={a.id} className={`rounded-2xl border p-5 ${cls[a.c]}`}>
            <div className="flex gap-3">
              <Icon n="alert" className={`mt-0.5 shrink-0 ${ic[a.c]}`} />
              <div className="flex-1">
                <div className="font-medium text-slate-800 text-sm">Warning: {a.t}</div>
                <div className="text-xs text-slate-500 mt-1">{a.d}</div>
                <button 
                  disabled={done[a.id]} 
                  onClick={() => { setDone({ ...done, [a.id]: true }); toast('Success: orders re-routed via alternate carrier'); }}
                  className={`mt-4 inline-flex items-center gap-2 text-sm px-3.5 py-1.5 rounded-lg border transition ${done[a.id] ? 'bg-white text-emerald-600 border-emerald-100' : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'}`}
                >
                  <Icon n={done[a.id] ? 'check' : 'truck'} size={15} />
                  {done[a.id] ? 'Rerouted' : 'Auto-Reroute Orders'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Card title="What-if Analysis">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600">Reduce Seller Prep Time (Days)</span>
          <span className="font-semibold text-slate-800">{days}d</span>
        </div>
        <input type="range" min="0" max="5" step="1" value={days} onChange={e => setDays(+e.target.value)} className="w-full mt-3 accent-blue-400" />
        <div className="flex justify-between text-xs text-slate-400 mt-1"><span>0</span><span>5</span></div>

        <div className="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="text-xs text-slate-500">Projected SLA Violation Rate</div>
          <div className="flex items-baseline gap-3 mt-1">
            <span className="text-3xl font-semibold text-slate-800">{proj(days)}%</span>
            <span className="text-sm text-emerald-600">
              {days > 0 ? `↓ ${(base - proj(days)).toFixed(1)} pts from ${base}%` : 'baseline'}
            </span>
          </div>
        </div>

        <div className="h-48 mt-4 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 10 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="d" tick={{ fontSize: 12, fill: MUTED }} axisLine={false} tickLine={false} unit="d" />
              <YAxis tick={{ fontSize: 12, fill: MUTED }} axisLine={false} tickLine={false} unit="%" domain={[0, 20]} />
              <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e8edf3', boxShadow: 'none', fontSize: 12 }} formatter={v => v + '%'} />
              <Line type="monotone" dataKey="v" name="Violation" stroke={BLUE} strokeWidth={2.5} dot={false} />
              <ReferenceDot x={days} y={proj(days)} r={6} fill={BLUE} stroke="#fff" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}