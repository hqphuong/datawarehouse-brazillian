import React, { useState } from 'react';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';

export default function ETLView({ toast }) {
  const [runs, setRuns] = useState([
    { id: 3, ok: true, t: '21 Oct 2026, 02:00', d: '4m 12s' },
    { id: 2, ok: false, t: '20 Oct 2026, 02:00', d: '1m 47s', e: 'Source timeout on olist_orders' },
    { id: 1, ok: true, t: '19 Oct 2026, 02:00', d: '4m 05s' },
  ]);
  const [running, setRunning] = useState(false);

  const run = () => {
    setRunning(true);
    setTimeout(() => {
      setRuns(r => [{ id: r[0].id + 1, ok: true, t: new Date().toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }), d: '4m 08s' }, ...r].slice(0, 3));
      setRunning(false);
      toast('ETL pipeline completed successfully');
    }, 2500);
  };

  const stats = [
    ['Fact_Delivery_SLA', '100,000'],
    ['Dim_Location', '4,000'],
    ['Dim_Seller', '3,095'],
    ['Dim_Product', '32,951'],
    ['Dim_Customer', '96,096'],
    ['Dim_Date', '1,461']
  ];

  return (
    <div className="space-y-6 w-full animate-fadeIn">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-slate-700">Data Warehouse Pipeline</div>
            <div className="text-xs text-slate-400 mt-1">Extract → Transform → Load · scheduled daily at 02:00</div>
          </div>
          <button 
            onClick={run} 
            disabled={running} 
            className="inline-flex items-center gap-2 bg-blue-400 hover:bg-blue-500 disabled:bg-blue-300 text-white text-sm font-medium px-5 py-2.5 rounded-xl transition"
          >
            <Icon n={running ? 'loader' : 'play'} size={16} className={running ? 'animate-spin' : ''} />
            {running ? 'Running…' : 'Run ETL Pipeline Now'}
          </button>
        </div>
      </Card>

      <Card title="Last 3 Runs">
        <ol className="relative border-l border-slate-200 ml-2 space-y-5">
          {runs.map(r => (
            <li key={r.id} className="pl-6 relative">
              <span className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ${r.ok ? 'bg-emerald-400' : 'bg-red-300'}`} />
              <div className="flex flex-wrap items-center gap-3">
                <span className={`text-xs px-2.5 py-0.5 rounded-full border ${r.ok ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-red-50 text-red-500 border-red-100'}`}>
                  {r.ok ? 'Success' : 'Failed'}
                </span>
                <span className="text-sm text-slate-700">{r.t}</span>
                <span className="text-xs text-slate-400">{r.d}</span>
              </div>
              {r.e && <div className="text-xs text-red-400 mt-1">{r.e}</div>}
            </li>
          ))}
        </ol>
      </Card>

      <div>
        <h3 className="text-sm font-medium text-slate-600 mb-3">Warehouse Metadata</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 w-full">
          {stats.map(([n, v]) => (
            <div key={n} className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
              <div className="text-xs text-slate-400 truncate">{n}</div>
              <div className="text-lg font-semibold text-slate-800 mt-1">{v}</div>
              <div className="text-xs text-slate-400">rows</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}