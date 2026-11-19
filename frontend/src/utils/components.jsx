/* eslint-disable react-refresh/only-export-components */
import { useEffect, useRef, useState } from 'react';

export function MultiSelect({label,options,value,onChange}){
  const [open,setOpen]=useState(false),[q,setQ]=useState(''),ref=useRef(null);
  useEffect(()=>{const h=e=>{if(ref.current&&!ref.current.contains(e.target))setOpen(false)};document.addEventListener('mousedown',h);return()=>document.removeEventListener('mousedown',h)},[]);
  const list=options.filter(o=>o.toLowerCase().includes(q.toLowerCase()));
  const toggle=o=>onChange(value.includes(o)?value.filter(x=>x!==o):[...value,o]);
  return <div className="relative" ref={ref}>
    <button className="sel flex items-center gap-2 min-w-[130px] justify-between" aria-haspopup="listbox" aria-expanded={open} onClick={()=>setOpen(!open)}>
      <span>{label}: <b>{value.length?`${value.length} đã chọn`:'Tất cả'}</b></span><span aria-hidden>▾</span></button>
    {open&&<div className="absolute z-40 mt-1 w-56 panel shadow-lg p-2">
      <input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="Tìm…" aria-label={'Tìm '+label} className="sel w-full mb-2"/>
      <div className="max-h-48 overflow-y-auto">{list.map(o=><label key={o} className="flex items-center gap-2 px-1 py-1 text-xs hover:bg-slate-50 cursor-pointer">
        <input type="checkbox" checked={value.includes(o)} onChange={()=>toggle(o)}/>{o}</label>)}{!list.length&&<div className="text-xs text-slate-500 p-2">Không có kết quả</div>}</div>
      <button className="text-xs text-teal-700 mt-1 underline" onClick={()=>onChange([])}>Bỏ chọn tất cả</button></div>}
  </div>}
export const YearSel=({year,setYear,years=['2017','2018']})=><label className="text-xs text-slate-600 flex items-center gap-2">Năm
  <select className="sel" value={year} onChange={e=>setYear(e.target.value)}><option value="all">{years.length?`Tất cả (${years[0]}–${years[years.length-1]})`:'Tất cả'}</option>{years.map(value=><option key={value}>{value}</option>)}</select></label>;
export const Skeleton=({h=160})=><div className="panel animate-pulse bg-slate-100" style={{height:h}} aria-busy="true"/>;
export const Errored=({msg,retry})=><div className="panel p-10 text-center" role="alert"><p className="font-semibold">Không tải được dữ liệu</p><p className="text-sm text-slate-600 mt-1">{msg} Kiểm tra backend đang chạy rồi thử lại.</p><button className="btn btn-main mt-3" onClick={retry}>Tải lại</button></div>;
export const Empty=({reset,msg='Không có đơn hàng khớp bộ lọc'})=><div className="panel p-10 text-center"><p className="font-semibold">{msg}</p><p className="text-sm text-slate-600 mt-1">Mở rộng khoảng thời gian hoặc bỏ bớt điều kiện lọc.</p>{reset&&<button className="btn mt-3" onClick={reset}>Đặt lại bộ lọc</button>}</div>;
export const Pill=({t,c})=><span className={'px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap '+c}>{t}</span>;
export const ST={ok:'bg-teal-50 text-teal-900',warn:'bg-amber-50 text-amber-900',more:'bg-slate-100 text-slate-700'};
export const LV={red:['Đỏ','bg-red-100 text-red-900'],yellow:['Vàng','bg-amber-100 text-amber-900'],amber:['Vàng','bg-amber-100 text-amber-900'],none:['—','text-slate-400']};
export const flagsOf=s=><>{s.low&&<Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700"/>} {s.uncertain&&<Pill t="Chưa chắc chắn" c="bg-amber-50 text-amber-900"/>}</>;

/* ============ 1. BI DASHBOARD: giám sát nhanh ============ */
