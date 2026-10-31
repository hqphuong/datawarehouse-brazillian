import React, { useState, useMemo } from 'react';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { DIMS, MEAS, RAW_OLAP } from '../data/mockData';

export default function OLAPView() {
  const [dims, setDims] = useState(['loc', 'cat']);
  const [meas, setMeas] = useState(['orders', 'freight']);
  const [sort, setSort] = useState({ k: null, dir: 1 });
  const [over, setOver] = useState(null);

  const drop = (zone, e) => {
    e.preventDefault(); setOver(null);
    const key = e.dataTransfer.getData('text');
    if (zone === 'dim' && DIMS[key] && !dims.includes(key)) setDims([...dims, key]);
    if (zone === 'meas' && MEAS[key] && !meas.includes(key)) setMeas([...meas, key]);
  };

  const rows = useMemo(() => {
    const g = {};
    RAW_OLAP.forEach(r => {
      const key = dims.map(d => r[d]).join('|');
      const o = g[key] || (g[key] = { _n: 0, ...Object.fromEntries(dims.map(d => [d, r[d]])), orders: 0, freight: 0, delay: 0, rev: 0 });
      o._n++; o.orders += r.orders; o.freight += r.freight; o.rev += r.rev; o.delay += r.delay;
    });
    let a = Object.values(g).map(o => ({ ...o, delay: +(o.delay / o._n).toFixed(2) }));
    if (sort.k) a.sort((x, y) => (x[sort.k] > y[sort.k] ? 1 : -1) * sort.dir);
    return a;
  }, [dims, meas, sort]);

  const cols = [...dims.map(d => ({ k: d, l: DIMS[d], dim: true })), ...meas.map(m => ({ k: m, l: MEAS[m] }))];
  const fmtv = (k, v) => k === 'freight' || k === 'rev' ? 'R$ ' + v.toLocaleString() : typeof v === 'number' ? v.toLocaleString() : v;

  const Pill = ({ id, label, tone, onRemove, drag }) => (
    <span 
      draggable={drag} 
      onDragStart={e => e.dataTransfer.setData('text', id)}
      className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border ${drag ? 'cursor-grab bg-white text-slate-600 border-slate-200 hover:border-blue-200' : tone === 'dim' ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-amber-50 text-amber-700 border-amber-100'}`}
    >
      {label}
      {onRemove && <button onClick={onRemove} className="opacity-60 hover:opacity-100"><Icon n="x" size={12} /></button>}
    </span>
  );

  const Zone = ({ z, title, items, set, names, tone }) => (
    <div 
      onDragOver={e => { e.preventDefault(); setOver(z); }} 
      onDragLeave={() => setOver(null)} 
      onDrop={e => drop(z, e)}
      className={`rounded-xl border-2 border-dashed p-4 min-h-[88px] transition ${over === z ? 'border-blue-300 bg-blue-50/40' : 'border-slate-200 bg-slate-50/50'}`}
    >
      <div className="text-xs font-medium text-slate-500 mb-3">{title}</div>
      <div className="flex flex-wrap gap-2">
        {items.length === 0 && <span className="text-xs text-slate-400">Drop fields here</span>}
        {items.map(i => <Pill key={i} id={i} label={names[i]} tone={tone} onRemove={() => set(items.filter(x => x !== i))} />)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6 w-full animate-fadeIn">
      <Card title="Query Builder" right={<span className="text-xs text-slate-400">Drag fields into a zone</span>}>
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(DIMS).map(([k, l]) => <Pill key={k} id={k} label={l} drag />)}
          <span className="w-px bg-slate-200 mx-1" />
          {Object.entries(MEAS).map(([k, l]) => <Pill key={k} id={k} label={l} drag />)}
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <Zone z="dim" title="Dimensions" items={dims} set={setDims} names={DIMS} tone="dim" />
          <Zone z="meas" title="Measures" items={meas} set={setMeas} names={MEAS} tone="meas" />
        </div>
      </Card>

      <Card title={`Pivot Table · ${rows.length} rows`}>
        {dims.length === 0 || meas.length === 0 ? (
          <div className="text-sm text-slate-400 py-10 text-center">Select at least one dimension and one measure.</div>
        ) : (
          <div className="overflow-x-auto w-full">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  {cols.map(c => (
                    <th key={c.k} onClick={() => setSort({ k: c.k, dir: sort.k === c.k ? -sort.dir : 1 })}
                      className={`py-2.5 px-3 font-medium text-xs text-slate-500 cursor-pointer select-none whitespace-nowrap ${c.dim ? 'text-left' : 'text-right'}`}>
                      <span className="inline-flex items-center gap-1">
                        {c.l}
                        <Icon n={sort.k === c.k ? (sort.dir === 1 ? 'up' : 'down') : 'sort'} size={13} className={sort.k === c.k ? 'text-blue-400' : 'text-slate-300'} />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50/70">
                    {cols.map(c => (
                      <td key={c.k} className={`py-2.5 px-3 ${c.dim ? 'text-slate-700' : 'text-right tabular-nums text-slate-600'}`}>
                        {fmtv(c.k, r[c.k])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}