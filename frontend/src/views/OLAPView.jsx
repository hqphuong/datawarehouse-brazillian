// src/views/OLAPView.jsx
import React, { useState, useRef, useEffect } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { MONTHS, QUARTERS, YEARS, TIME_OPTS, LV_NAME, STATES, CATS, RAW, agg, pct, num, int } from '../data/mockData.jsx';
import { useData } from '../hooks/useData.js';

const DIMS = { time: 'Thời gian', state: 'Bang khách hàng', category: 'Danh mục sản phẩm', payment: 'Hình thức thanh toán' };
const NEXT = { year: 'quarter', quarter: 'month' };
const MEAS = { 
  n: ['Số đơn', a => int(a.n), 'COUNT(order_id)'], 
  rate: ['Tỷ lệ trễ', a => pct(a.rate), '(SUM(CASE WHEN delay_days > 0 THEN 1.0 ELSE 0.0 END) / COUNT(*)) * 100'], 
  transit: ['Vận chuyển TB (ngày)', a => num(a.transit), 'AVG(carrier_transit_time_days)'], 
  freight: ['Phí vận chuyển TB', a => num(a.freight, 2), 'AVG(freight_value)'], 
  review: ['Điểm đánh giá TB', a => num(a.review, 2), 'AVG(review_score)'] 
};
const PRESETS = [
  { t: 'Trễ theo bang × quý', rows: 'state', cols: 'time', tl: 'quarter', m: 'rate' }, 
  { t: 'Số đơn theo danh mục × thanh toán', rows: 'category', cols: 'payment', tl: 'year', m: 'n' }, 
  { t: 'Vận chuyển theo năm → tháng', rows: 'time', cols: 'none', tl: 'year', m: 'transit' }
];

export default function OLAPView({ f, sim }) {
  const DEFAULT_F = f || { level: 'month', from: '2017-01', to: '2018-08', states: [], lateOnly: false };
  const [cfg, setCfg] = useState({ rows: 'state', cols: 'time', tl: 'quarter', m: 'rate' });
  const [drill, setDrill] = useState([]);
  const [view, setView] = useState('table');
  const [run, setRun] = useState(0);
  const [sqlOpen, setSqlOpen] = useState(false);

  const key = (r, d) => d === 'time' ? r[cfg.tl] : r[d];
  
  const { data, loading, error, retry } = useData(() => {
    // Lọc RAW tương tự bản gốc
    const rows = RAW.filter(r => r[DEFAULT_F.level] >= DEFAULT_F.from && r[DEFAULT_F.level] <= DEFAULT_F.to && (!DEFAULT_F.states.length || DEFAULT_F.states.includes(r.state)) && (!DEFAULT_F.lateOnly || r.late) && drill.every(d => r[d.level] === d.value));
    
    const rk = [...new Set(rows.map(r => key(r, cfg.rows)))].sort();
    const ck = cfg.cols === 'none' ? ['Tất cả'] : [...new Set(rows.map(r => key(r, cfg.cols)))].sort().slice(0, 10);
    
    const cell = (a) => agg(a), g = {};
    rows.forEach(r => { const c = cfg.cols === 'none' ? 'Tất cả' : key(r, cfg.cols); (g[key(r, cfg.rows) + '|' + c] ?? []).push(r); });
    
    const body = rk.map(k => ({ k, cells: ck.map(c => cell(g[k + '|' + c] || [])), tot: cell(rows.filter(r => key(r, cfg.rows) === k)) }));
    const colTot = ck.map(c => cell(rows.filter(r => cfg.cols === 'none' || key(r, cfg.cols) === c)));
    
    return { rk, ck, body, colTot, grand: cell(rows) };
  }, [DEFAULT_F, cfg, drill, run], sim);

  const set = (p) => { setCfg({ ...cfg, ...p }); setDrill([]); };
  const [mName, mFmt, mSql] = MEAS[cfg.m];
  const val = a => a.n ? mFmt(a) : '—';
  
  const nums = data ? data.body.flatMap(b => b.cells.filter(c => c.n).map(c => c[cfg.m])) : [];
  const mx = Math.max(...nums, 1e-9), mn = Math.min(...nums, 0);
  const heat = c => ({ background: view === 'heat' && c.n ? `rgba(15,118,110,${0.08 + 0.7 * ((c[cfg.m] - mn) / ((mx - mn) || 1))})` : '', color: view === 'heat' && c.n && ((c[cfg.m] - mn) / ((mx - mn) || 1)) > .6 ? '#fff' : '' });
  
  const drillInto = v => { if (cfg.rows === 'time' && NEXT[cfg.tl]) { setDrill([...drill, { level: cfg.tl, value: v }]); setCfg({ ...cfg, tl: NEXT[cfg.tl] }); } };
  const rollUp = i => { const lv = drill[i]?.level || cfg.tl; setDrill(drill.slice(0, i)); setCfg({ ...cfg, tl: lv }); };

  const sql = `SELECT 
    ${cfg.rows === 'time' ? 't.' + cfg.tl : cfg.rows}${cfg.cols !== 'none' ? ', ' + (cfg.cols === 'time' ? 't.' + cfg.tl : cfg.cols) : ''}, 
    ${mSql} AS ${cfg.m}
FROM Fact_Delivery_SLA f
JOIN Dim_Time t ON f.time_id = t.time_id
JOIN Dim_Location c ON f.customer_location_id = c.location_id
JOIN Dim_Product p ON f.product_id = p.product_id
WHERE t.${DEFAULT_F.level} BETWEEN '${DEFAULT_F.from}' AND '${DEFAULT_F.to}'${DEFAULT_F.states.length ? `\n  AND c.state IN (${DEFAULT_F.states.map(s => `'${s}'`).join(', ')})` : ''}${drill.map(d => `\n  AND t.${d.level} = '${d.value}'`).join('')}
GROUP BY ${cfg.rows === 'time' ? 't.' + cfg.tl : cfg.rows}${cfg.cols !== 'none' ? ', ' + (cfg.cols === 'time' ? 't.' + cfg.tl : cfg.cols) : ''};`;

  const csv = () => {
    const h = [DIMS[cfg.rows], ...data.ck, 'Tổng'];
    const l = [h, ...data.body.map(b => [b.k, ...b.cells.map(val), val(b.tot)])];
    const u = URL.createObjectURL(new Blob(['\ufeff' + l.map(r => r.join(',')).join('\n')], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = u; a.download = 'olap.csv'; a.click(); URL.revokeObjectURL(u);
  };

  const Pick = ({ label, k, none }) => (
    <label className="block text-xs text-slate-600 mb-2">
      {label}
      <select className="sel w-full mt-0.5" value={cfg[k]} onChange={e => set({ [k]: e.target.value })}>
        {none && <option value="none">(Không dùng)</option>}
        {Object.entries(DIMS).filter(([d]) => d !== (k === 'rows' ? cfg.cols : cfg.rows)).map(([d, v]) => <option key={d} value={d}>{v}</option>)}
      </select>
    </label>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[290px_1fr] gap-4">
      {/* Sidebar cấu hình */}
      <aside className="space-y-3 lg:sticky lg:top-[200px] self-start">
        <div className="panel p-3">
          <h2 className="font-semibold text-sm mb-2">Cấu hình bảng</h2>
          <Pick label="Hàng (Rows)" k="rows" />
          <Pick label="Cột (Columns)" k="cols" none />
          {(cfg.rows === 'time' || cfg.cols === 'time') && (
            <div className="text-xs text-slate-600 mb-2">
              Mức thời gian
              <div className="flex gap-1 mt-0.5">
                {Object.keys(LV_NAME).reverse().map(l => (
                  <button key={l} className={'btn flex-1 ' + (cfg.tl === l ? 'btn-main' : '')} onClick={() => { setDrill([]); setCfg({ ...cfg, tl: l }); }}>{LV_NAME[l]}</button>
                ))}
              </div>
            </div>
          )}
          <fieldset className="text-xs text-slate-600">
            <legend className="mb-1">Chỉ số trong ô (Values)</legend>
            {Object.entries(MEAS).map(([k, [n]]) => (
              <label key={k} className="flex items-center gap-2 py-0.5 text-slate-800 cursor-pointer">
                <input type="radio" name="m" checked={cfg.m === k} onChange={() => set({ m: k })} />{n}
              </label>
            ))}
          </fieldset>
          <p className="text-[11px] text-slate-500 mt-2">Bộ lọc thời gian và bang dùng chung với thanh phía trên.</p>
          <div className="flex gap-2 mt-3">
            <button className="btn btn-main flex-1" onClick={() => setRun(run + 1)}>Chạy truy vấn</button>
            <button className="btn" onClick={() => { setCfg({ rows: 'state', cols: 'time', tl: 'quarter', m: 'rate' }); setDrill([]); }}>Đặt lại</button>
          </div>
        </div>
        <div className="panel p-3">
          <h3 className="font-semibold text-sm mb-1">Truy vấn mẫu</h3>
          {PRESETS.map(p => (
            <button key={p.t} className="block w-full text-left text-xs py-1 hover:text-teal-800 hover:underline" onClick={() => { setDrill([]); setCfg({ rows: p.rows, cols: p.cols, tl: p.tl, m: p.m }); }}>{p.t}</button>
          ))}
        </div>
      </aside>

      {/* Vùng hiển thị chính */}
      <section className="min-w-0 space-y-3">
        <div className="panel p-3 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm">
            {mName} theo <b>{DIMS[cfg.rows]}</b>{cfg.cols !== 'none' && <> × <b>{DIMS[cfg.cols]}</b></>}
            {drill.length > 0 && (
              <nav className="text-xs mt-1 text-slate-600" aria-label="Phân cấp">
                <button className="underline" onClick={() => rollUp(0)}>Tất cả</button>
                {drill.map((d, i) => <span key={i}> › <button className="underline" onClick={() => rollUp(i + 1 < drill.length ? i + 1 : i + 1)}>{d.value}</button></span>)}
                <button className="btn ml-2" onClick={() => rollUp(drill.length - 1)}>▲ Roll-up</button>
              </nav>
            )}
          </div>
          <div className="flex items-center gap-1">
            {[['table', 'Bảng'], ['heat', 'Heatmap'], ['chart', 'Biểu đồ']].map(([k, t]) => (
              <button key={k} className={'btn ' + (view === k ? 'btn-main' : '')} onClick={() => setView(k)}>{t}</button>
            ))}
            <button className="btn" disabled={!data} onClick={csv}>Xuất CSV</button>
          </div>
        </div>

        {error ? (
          <div className="panel p-10 text-center"><p className="text-red-600">Lỗi: {error}</p></div>
        ) : loading || !data ? (
          <div className="panel animate-pulse h-80 bg-slate-100" />
        ) : !data.grand.n ? (
          <div className="panel p-10 text-center"><p>Không có dữ liệu khớp bộ lọc</p></div>
        ) : view === 'chart' ? (
          <div className="panel p-4 h-80">
            <ResponsiveContainer>
              <BarChart data={data.body.map(b => ({ k: b.k, v: b.tot[cfg.m] }))}>
                <CartesianGrid vertical={false} stroke="#e5e9ec"/><XAxis dataKey="k" tick={{fontSize: 11}}/><YAxis tick={{fontSize: 11}} tickFormatter={v => cfg.m === 'rate' ? pct(v) : v}/>
                <Tooltip formatter={v => cfg.m === 'rate' ? pct(v) : num(v, 2)}/><Bar dataKey="v" name={mName} fill="#0f766e"/>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="panel overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left py-2 px-3">{DIMS[cfg.rows]}</th>
                  {data.ck.map(c => <th key={c} className="text-right px-3">{c}</th>)}
                  <th className="text-right px-3 bg-slate-100">Tổng</th>
                </tr>
              </thead>
              <tbody>
                {data.body.map(b => (
                  <tr key={b.k} className="border-t border-slate-100">
                    <th className="text-left py-2 px-3 font-medium">
                      {cfg.rows === 'time' && NEXT[cfg.tl] ? (
                        <button className="underline decoration-dotted hover:text-teal-800" title="Drill-down xuống mức thấp hơn" onClick={() => drillInto(b.k)}>▼ {b.k}</button>
                      ) : b.k}
                    </th>
                    {b.cells.map((c, i) => (
                      <td key={i} className={'text-right px-3 ' + (c.n && c.n < 15 ? 'text-slate-400 italic' : '')} style={heat(c)} title={c.n ? `${c.n} đơn${c.n < 15 ? ' – mẫu nhỏ' : ''}` : 'Không có dữ liệu'}>
                        {val(c)}
                      </td>
                    ))}
                    <td className="text-right px-3 font-semibold bg-slate-50">{val(b.tot)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold">
                  <th className="text-left py-2 px-3">Tổng</th>
                  {data.colTot.map((c, i) => <td key={i} className="text-right px-3">{val(c)}</td>)}
                  <td className="text-right px-3">{val(data.grand)}</td>
                </tr>
              </tbody>
            </table>
            <p className="text-[11px] text-slate-500 p-2">Chữ nghiêng xám: ô dưới 15 đơn (mẫu nhỏ). Rê chuột vào ô để xem số đơn.</p>
          </div>
        )}

        {/* Khung xem mã SQL tương ứng */}
        <div className="panel">
          <button className="w-full text-left px-3 py-2 text-sm font-medium flex justify-between" aria-expanded={sqlOpen} onClick={() => setSqlOpen(!sqlOpen)}>
            SQL tương ứng<span>{sqlOpen ? '▴' : '▾'}</span>
          </button>
          {sqlOpen && <pre className="px-3 pb-3 text-xs overflow-x-auto text-slate-700 bg-slate-50 p-2 font-mono">{sql}</pre>}
        </div>
      </section>
    </div>
  );
}