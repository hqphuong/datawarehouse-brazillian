
import { useState, useEffect, useRef } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line } from 'recharts';
import './redesign.css';


/*LOGIC-START*/
/* ============ DỮ LIỆU MẪU (sinh ngẫu nhiên, KHÔNG phải số liệu Olist thật – thay bằng API) ============
   Mỗi dòng = một đơn-tuyến đã giao (route = bang người bán → bang khách hàng), cùng mẫu số với DSS trong báo cáo.
   delay > 0 là trễ; promise = total − delay (ngày cam kết = tổng thời gian hoàn tất − số ngày trễ). */
const MONTHS=[];for(let y=2017;y<=2018;y++)for(let m=1;m<=12;m++){if(y===2018&&m>8)break;MONTHS.push(`${y}-${String(m).padStart(2,'0')}`)}
const QUARTERS=[...new Set(MONTHS.map(m=>m.slice(0,4)+'-Q'+Math.ceil(+m.slice(5)/3)))];
const YEARS=['2017','2018'];
const TIME_OPTS={month:MONTHS,quarter:QUARTERS,year:YEARS};
const LV_NAME={year:'Năm',quarter:'Quý',month:'Tháng'};
const STATES=['AL','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RS','SC','SE','SP','TO'];
const CATS=['bed_bath_table','health_beauty','sports_leisure','computers_accessories','furniture_decor','toys'];
const PAYS=['credit_card','boleto','voucher','debit_card'];
const SELLER_STATES=['SP','SP','SP','MG','PR','RJ'];
function rng(s){return()=>{s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
const RAW=(()=>{const r=rng(7),pick=a=>a[Math.floor(r()*a.length)],out=[];
  const heavy=['SP','SP','SP','SP','RJ','RJ','MG','MG','RS','PR','SC','BA','PE','CE',...STATES];
  for(let i=0;i<1400;i++){const month=pick(MONTHS),state=pick(heavy),si=Math.floor(r()*30);
    const far=['MA','AL','PI','SE','BA','PA','TO'].includes(state);
    const isLate=r()<(0.05+(far?0.12:0)+(['2017-11','2018-03'].includes(month)?0.05:0)+(si<3?0.08:0));
    const appr=+(0.1+r()*0.9).toFixed(1),prep=+(1+r()*3).toFixed(1),transit=+((far?9:4)+r()*7+(isLate?4:0)).toFixed(1);
    const total=+(appr+prep+transit).toFixed(1);
    const delay=isLate?+(0.5+r()*Math.max(0,Math.min(6,total-6))).toFixed(1):-+(0.1+r()*8).toFixed(1);
    const ss=SELLER_STATES[si%6];
    out.push({id:'ord_'+(9000+i),month,quarter:month.slice(0,4)+'-Q'+Math.ceil(+month.slice(5)/3),year:month.slice(0,4),
      state,seller_state:ss,route:ss+'→'+state,seller:'seller_'+String(si+1).padStart(2,'0'),category:pick(CATS),payment:pick(PAYS),
      late:delay>0?1:0,delay,appr,prep,transit,total,promise:+(total-delay).toFixed(1),
      price:+(20+r()*180).toFixed(2),freight:+(8+r()*30).toFixed(1),review:Math.max(1,Math.min(5,Math.round(isLate?2.5+r()*2:4+r()*1.5)))})}
  return out})();
function agg(a){const n=a.length,s=k=>a.reduce((x,y)=>x+y[k],0),m=k=>n?s(k)/n:null;
  return{n,late:s('late'),rate:m('late'),appr:m('appr'),prep:m('prep'),transit:m('transit'),total:m('total'),freight:m('freight'),review:m('review'),gmv:s('price')}}
const vn=(x,d)=>x.toFixed(d).replace('.',',');
const pct=v=>v==null?'—':vn(v*100,1)+'%',num=(v,d=1)=>v==null?'—':vn(v,d),int=v=>v.toLocaleString('vi-VN');
const byYear=y=>RAW.filter(r=>y==='all'||r.year===y);

/* ============ LOGIC DSS (thuần hàm; thay bằng API /routes, /attribution, /scenario, /brief, /promise-policy, /sellers) ============
   Ngưỡng trong báo cáo (dữ liệu thật): min_orders=100, low_sample<200. Dữ liệu mẫu chỉ 1 400 dòng nên thu nhỏ lại. */
const MIN_ORDERS=10,LOW_SAMPLE=30,MIN_SELLER=30,Z=1.96;
const STAGES=[['appr','Duyệt thanh toán'],['prep','Người bán chuẩn bị'],['transit','Vận chuyển']];
function wilson(k,n){if(!n)return[0,0];const p=k/n,z2=Z*Z,den=1+z2/n,c=p+z2/(2*n),m=Z*Math.sqrt(p*(1-p)/n+z2/(4*n*n));return[(c-m)/den,(c+m)/den]}
function quant(v,q){if(!v.length)return 0;const s=[...v].sort((a,b)=>a-b),i=(s.length-1)*q,lo=Math.floor(i),hi=Math.ceil(i);return s[lo]+(s[hi]-s[lo])*(i-lo)}
const mean=(a,k)=>a.length?a.reduce((s,r)=>s+r[k],0)/a.length:0;
const bench=(rows,q)=>Object.fromEntries(STAGES.map(([k])=>[k,quant(rows.map(r=>r[k]),q)]));
function routeStats(rows){
  const g={};rows.forEach(r=>(g[r.route]??=[]).push(r));
  const L=rows.length?rows.reduce((s,r)=>s+r.late,0)/rows.length:0;
  const list=Object.entries(g).filter(([,a])=>a.length>=MIN_ORDERS).map(([route,a])=>{
    const n=a.length,k=a.reduce((s,r)=>s+r.late,0),p=k/n,[lo,hi]=wilson(k,n);
    const level=L>0&&p>=2*L?'red':L>0&&p>=1.5*L?'yellow':'none',thr=(level==='red'?2:1.5)*L;
    return{route,n,k,p,lo,hi,level,low:n<LOW_SAMPLE,uncertain:level!=='none'&&lo<thr,rows:a}});
  return{L,list}}
/* Shapley 3 giai đoạn cho một đơn trễ: v(S)=1 nếu đơn vẫn trễ khi các giai đoạn ngoài S về mức benchmark. */
function shapley(o,b){
  const e=STAGES.map(([k])=>Math.max(0,o[k]-b[k])),W=[2/6,1/6,2/6];
  const v=m=>{let d=o.delay;for(let i=0;i<3;i++)if(!((m>>i)&1))d-=e[i];return d>0?1:0};
  const phi=[0,1,2].map(i=>{let s=0;for(let m=0;m<8;m++){if((m>>i)&1)continue;const c=((m&1)+((m>>1)&1)+((m>>2)&1));s+=W[c]*(v(m|(1<<i))-v(m))}return s});
  return{phi,resid:v(0)}}
function attribution(rows,b){const late=rows.filter(r=>r.late);if(!late.length)return null;
  const s=[0,0,0];let res=0;late.forEach(o=>{const x=shapley(o,b);x.phi.forEach((p,i)=>s[i]+=p);res+=x.resid});
  const n=late.length;return{n,appr:s[0]/n,prep:s[1]/n,transit:s[2]/n,resid:res/n}}
const reduced=(r,cut)=>STAGES.reduce((x,[k])=>x+Math.min(cut[k]||0,r[k]),0);
const simulate=(rows,cut)=>rows.reduce((s,r)=>s+((r.delay-reduced(r,cut))>0?1:0),0);
function bootCI(rows,cut,B=300,seed=42){const rnd=rng(seed),n=rows.length,av=[],pp=[];
  for(let b=0;b<B;b++){let bf=0,af=0;for(let i=0;i<n;i++){const r=rows[Math.floor(rnd()*n)];bf+=r.late;af+=(r.delay-reduced(r,cut))>0?1:0}av.push(bf-af);pp.push((bf-af)/n*100)}
  return{avLo:quant(av,.025),avHi:quant(av,.975),ppLo:quant(pp,.025),ppHi:quant(pp,.975)}}
const p25cut=(rows,b25)=>Object.fromEntries(STAGES.map(([k])=>[k,Math.max(0,+(mean(rows,k)-b25[k]).toFixed(1))]));
function evid(ci,low){return low?['Cần thêm dữ liệu','more']:ci.avLo<=0?['Chưa đủ bằng chứng','warn']:['Ước lượng ổn định','ok']}
function buildBrief(rows){
  const {L,list}=routeStats(rows),b25=bench(rows,.25);
  const routes=list.filter(s=>!s.low).map(s=>{const cut=p25cut(s.rows,b25),avoided=s.k-simulate(s.rows,cut);return{...s,cut,avoided,ci:bootCI(s.rows,cut)}})
    .filter(x=>x.avoided>0).sort((a,b)=>b.avoided-a.avoided).slice(0,5);
  const gp={};rows.forEach(r=>(gp[r.payment]??=[]).push(r));
  const pay=Object.entries(gp).map(([p,a])=>{const cut={appr:Math.max(0,+(mean(a,'appr')-b25.appr).toFixed(1))},late=a.filter(r=>r.late).length;
    return{pay:p,n:a.length,cut:cut.appr,avoided:late-simulate(a,cut),ci:bootCI(a,cut),low:a.length<LOW_SAMPLE}}).sort((a,b)=>b.avoided-a.avoided);
  const prom=list.map(s=>{const need=Math.ceil(quant(s.rows.map(r=>r.total),.95)),med=quant(s.rows.map(r=>r.promise),.5);
    const st=med<need-1?'tight':med>need+1?'loose':'ok',newLate=s.rows.filter(r=>r.total>need).length;
    return{route:s.route,n:s.n,need,med,st,net:st==='ok'?0:s.k-newLate}});
  const promTop=prom.filter(x=>x.st==='tight'&&x.net>0).sort((a,b)=>b.net-a.net).slice(0,5);
  const promCnt={tight:prom.filter(x=>x.st==='tight').length,ok:prom.filter(x=>x.st==='ok').length,loose:prom.filter(x=>x.st==='loose').length};
  const gs={};rows.forEach(r=>(gs[r.seller]??=[]).push(r));
  const sellers=Object.entries(gs).filter(([,a])=>a.length>=MIN_SELLER).map(([id,a])=>{const n=a.length,k=a.reduce((s,r)=>s+r.late,0),[lo]=wilson(k,n);
    return{id,n,k,p:k/n,excess:k-n*L,prio:lo>L}}).filter(x=>x.excess>0).sort((a,b)=>b.excess-a.excess).slice(0,5);
  const more=list.filter(s=>s.level!=='none'&&s.low).sort((a,b)=>b.p-a.p).slice(0,5);
  return{L,routes,pay,promTop,promCnt,sellers,more}}
/*LOGIC-END*/

/* Hook dữ liệu: thay body bằng fetch('/api/...') khi gắn API. Thêm ?dev=1 để thấy nút giả lập lỗi. */
const DEV=new URLSearchParams(location.search).has('dev');
function useData(compute,deps,sim){
  const depsKey=JSON.stringify(deps);
  const computeRef=useRef(compute);
  const [st,setSt]=useState({key:null,loading:true,error:null,data:null});
  const [tick,setTick]=useState(0);
  useEffect(()=>{computeRef.current=compute},[compute]);
  useEffect(()=>{let ok=true;
    const t=setTimeout(()=>{if(!ok)return;
      if(sim.error)return setSt({key:depsKey,loading:false,error:'Không kết nối được máy chủ dữ liệu.',data:null});
      try{setSt({key:depsKey,loading:false,error:null,data:computeRef.current()})}catch(e){setSt({key:depsKey,loading:false,error:e.message,data:null})}},250);
    return()=>{ok=false;clearTimeout(t)}},[depsKey,tick,sim.error]);
  return{
    loading:st.key!==depsKey||st.loading,
    error:st.key===depsKey?st.error:null,
    data:st.key===depsKey?st.data:null,
    retry:()=>setTick(t=>t+1)
  };
}

/* ============ THÀNH PHẦN CHUNG ============ */
function MultiSelect({label,options,value,onChange}){
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
const YearSel=({year,setYear})=><label className="text-xs text-slate-600 flex items-center gap-2">Năm
  <select className="sel" value={year} onChange={e=>setYear(e.target.value)}><option value="all">Tất cả (2017–2018)</option><option>2017</option><option>2018</option></select></label>;
const Skeleton=({h=160})=><div className="panel animate-pulse bg-slate-100" style={{height:h}} aria-busy="true"/>;
const Errored=({msg,retry})=><div className="panel p-10 text-center" role="alert"><p className="font-semibold">Không tải được dữ liệu</p><p className="text-sm text-slate-600 mt-1">{msg} Kiểm tra backend đang chạy rồi thử lại.</p><button className="btn btn-main mt-3" onClick={retry}>Tải lại</button></div>;
const Empty=({reset,msg='Không có đơn hàng khớp bộ lọc'})=><div className="panel p-10 text-center"><p className="font-semibold">{msg}</p><p className="text-sm text-slate-600 mt-1">Mở rộng khoảng thời gian hoặc bỏ bớt điều kiện lọc.</p>{reset&&<button className="btn mt-3" onClick={reset}>Đặt lại bộ lọc</button>}</div>;
const Pill=({t,c})=><span className={'px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap '+c}>{t}</span>;
const ST={ok:'bg-teal-50 text-teal-900',warn:'bg-amber-50 text-amber-900',more:'bg-slate-100 text-slate-700'};
const LV={red:['Đỏ','bg-red-100 text-red-900'],yellow:['Vàng','bg-amber-100 text-amber-900'],none:['—','text-slate-400']};
const flagsOf=s=><>{s.low&&<Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700"/>} {s.uncertain&&<Pill t="Chưa chắc chắn" c="bg-amber-50 text-amber-900"/>}</>;

/* ============ 1. BI DASHBOARD: giám sát nhanh ============ */
function Dashboard({year,setYear,sim,goDss}){
  const {data,loading,error,retry}=useData(()=>{
    const rows=byYear(year),g={};rows.forEach(r=>(g[r.month]??=[]).push(r));
    const trend=Object.keys(g).sort().map(k=>({label:k,...agg(g[k])}));
    const {L,list}=routeStats(rows);
    return{kpi:agg(rows),trend,L,top:[...list].sort((a,b)=>b.p-a.p).slice(0,5)}},[year],sim);
  if(error)return <Errored msg={error} retry={retry}/>;
  if(loading||!data)return <div className="space-y-4"><Skeleton h={90}/><Skeleton h={300}/></div>;
  const {kpi,trend,top}=data;
  const cards=[['Tổng đơn-tuyến đã giao',int(kpi.n),''],['Tỷ lệ giao trễ',pct(kpi.rate),`${int(kpi.late)} / ${int(kpi.n)} đơn-tuyến`,1],
    ['Thời gian giao TB',num(kpi.total)+' ngày','Từ đặt hàng đến khi khách nhận'],['Duyệt thanh toán TB',num(kpi.appr)+' ngày','Hệ thống / sàn'],
    ['Người bán chuẩn bị TB',num(kpi.prep)+' ngày','Người bán'],['Vận chuyển TB',num(kpi.transit)+' ngày','Đơn vị vận chuyển']];
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><YearSel year={year} setYear={setYear}/>
      <p className="text-xs text-slate-500 max-w-3xl">Tỷ lệ trễ = đơn-tuyến giao sau ngày dự kiến ({'delay_days > 0'}) ÷ đơn-tuyến đã giao; tuyến = bang người bán → bang khách hàng. Theo báo cáo (dữ liệu thật): 8,1556% theo đơn-tuyến, 8,1950% nếu tính theo đơn duy nhất. Dữ liệu mẫu: 1 đơn = 1 tuyến.</p></div>
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
      {cards.map(([t,v,s,hot])=><div key={t} className={'panel p-3 '+(hot?'border-orange-300 bg-orange-50':'')}>
        <div className="text-xs text-slate-600">{t}</div><div className={'text-2xl font-semibold mt-0.5 '+(hot?'text-orange-800':'')}>{v}</div><div className="text-[11px] text-slate-500 mt-0.5">{s}</div></div>)}
    </div>
    <div className="grid grid-cols-1 xl:grid-cols-[1.3fr_1fr] gap-4">
      <section className="panel p-4"><h2 className="font-semibold">Xu hướng tỷ lệ trễ theo tháng</h2>
        <p className="text-xs text-slate-500 mb-2">Cho biết vấn đề đang tăng hay giảm; rê chuột để xem số đơn của tháng.</p>
        <div className="h-64"><ResponsiveContainer><LineChart data={trend}><CartesianGrid vertical={false} stroke="#e5e9ec"/><XAxis dataKey="label" tick={{fontSize:11}}/>
          <YAxis tick={{fontSize:11}} tickFormatter={v=>Math.round(v*100)+'%'}/><Tooltip formatter={(v,n,p)=>[pct(v)+` (${p.payload.late}/${p.payload.n} đơn)`,'Tỷ lệ trễ']}/>
          <Line type="monotone" dataKey="rate" stroke="#c2410c" strokeWidth={2} dot={{r:2}}/></LineChart></ResponsiveContainer></div></section>
      <section className="panel p-4"><h2 className="font-semibold">5 tuyến có tỷ lệ trễ cao nhất</h2>
        <p className="text-xs text-slate-500 mb-2">Chỉ xét tuyến từ {MIN_ORDERS} đơn-tuyến trở lên (báo cáo: 100). Tuyến dưới {LOW_SAMPLE} đơn gắn “Mẫu nhỏ”.</p>
        <table className="w-full text-xs"><thead className="text-left text-slate-500"><tr><th className="py-1">Tuyến</th><th className="text-right">Đơn</th><th className="text-right">Trễ</th><th className="text-right">Tỷ lệ</th><th/></tr></thead>
          <tbody>{top.map(s=><tr key={s.route} className="border-t border-slate-100"><td className="py-2 font-medium">{s.route} {s.low&&<Pill t="Mẫu nhỏ" c="bg-slate-100 text-slate-700"/>}</td>
            <td className="text-right">{int(s.n)}</td><td className="text-right">{int(s.k)}</td><td className="text-right font-semibold">{pct(s.p)}</td>
            <td className="text-right"><button className="btn" onClick={()=>goDss(s.route)}>Mở trong DSS</button></td></tr>)}
            {!top.length&&<tr><td colSpan="5" className="py-4 text-center text-slate-500">Chưa có tuyến đủ mẫu.</td></tr>}</tbody></table></section>
    </div></div>}

/* ============ 2. OLAP: tự khám phá (slice/dice, drill-down/roll-up) ============ */
const DIMS={time:'Thời gian',route:'Tuyến (bang bán → bang khách)',state:'Bang khách hàng',category:'Danh mục sản phẩm',seller:'Người bán'};
const NEXT={year:'quarter',quarter:'month'};
const MEAS={n:['Số đơn',a=>int(a.n)],late:['Số đơn trễ',a=>int(a.late)],rate:['Tỷ lệ trễ',a=>pct(a.rate)],appr:['Duyệt thanh toán TB (ngày)',a=>num(a.appr)],
  prep:['Người bán chuẩn bị TB (ngày)',a=>num(a.prep)],transit:['Vận chuyển TB (ngày)',a=>num(a.transit)],freight:['Phí vận chuyển TB (R$)',a=>num(a.freight,2)],gmv:['GMV (R$)',a=>int(Math.round(a.gmv))]};
const MEAS_SQL={n:'COUNT(DISTINCT f.order_id)',late:'COUNT(DISTINCT CASE WHEN f.delay_days > 0 THEN f.order_id END)',
  rate:'COUNT(DISTINCT CASE WHEN f.delay_days > 0 THEN f.order_id END)::float / COUNT(DISTINCT f.order_id)',appr:'AVG(f.approval_time_days)',
  prep:'AVG(f.seller_prep_time_days)',transit:'AVG(f.carrier_transit_time_days)',freight:'AVG(f.freight_value)',gmv:'SUM(f.price)'};
const DIM_SQL={route:"sl.state || '→' || c.state",state:'c.state',category:'p.category_name_english',seller:'f.seller_id'};
const TL_SQL={year:'t.year',quarter:'t.year, t.quarter',month:'t.year, t.month'};
function DimensionPick({label,field,none,config,onChange}){
  return <label className="text-xs text-slate-600">{label}<br/>
    <select className="sel mt-0.5 min-w-[150px]" value={config[field]} onChange={e=>onChange(e.target.value)}>
      {none&&<option value="none">(Không dùng)</option>}
      {Object.entries(DIMS).filter(([dimension])=>dimension!==(field==='rows'?config.cols:config.rows))
        .map(([dimension,name])=><option key={dimension} value={dimension}>{name}</option>)}
    </select>
  </label>;
}
function dateRange(level,from,to){
  const st=v=>level==='year'?`${v}-01-01`:level==='quarter'?`${v.slice(0,4)}-${String((+v.slice(6)-1)*3+1).padStart(2,'0')}-01`:`${v}-01`;
  const en=v=>{let y=+v.slice(0,4),m=level==='year'?12:level==='quarter'?+v.slice(6)*3:+v.slice(5);return `${y}-${String(m).padStart(2,'0')}-${new Date(y,m,0).getDate()}`};
  return `t.full_date BETWEEN '${st(from)}' AND '${en(to)}'`}
const DEF_O={level:'month',from:MONTHS[0],to:MONTHS[MONTHS.length-1],sstates:[],cstates:[],cats:[],lateOnly:false};
const DEF_CFG={rows:'state',cols:'time',tl:'quarter',m:'rate'};
const PRESETS=[{t:'Tỷ lệ trễ theo bang khách × quý',rows:'state',cols:'time',tl:'quarter',m:'rate'},{t:'Tỷ lệ trễ theo tuyến',rows:'route',cols:'none',tl:'year',m:'rate'},
  {t:'Vận chuyển TB theo năm → tháng (drill-down)',rows:'time',cols:'none',tl:'year',m:'transit'},{t:'Số đơn trễ theo người bán',rows:'seller',cols:'none',tl:'year',m:'late'},{t:'GMV theo danh mục',rows:'category',cols:'none',tl:'year',m:'gmv'}];
const olapRows=(fl,drill)=>RAW.filter(r=>r[fl.level]>=fl.from&&r[fl.level]<=fl.to&&(!fl.sstates.length||fl.sstates.includes(r.seller_state))&&(!fl.cstates.length||fl.cstates.includes(r.state))
  &&(!fl.cats.length||fl.cats.includes(r.category))&&(!fl.lateOnly||r.late)&&drill.every(d=>r[d.level]===d.value));
function Olap({sim}){
  const [fl,setFl]=useState(DEF_O),[cfg,setCfg]=useState(DEF_CFG),[drill,setDrill]=useState([]),[view,setView]=useState('table'),[sqlOpen,setSqlOpen]=useState(false);
  const key=(r,d)=>d==='time'?r[cfg.tl]:r[d];
  const {data,loading,error,retry}=useData(()=>{
    const rows=olapRows(fl,drill),byRow={},byCol={},g={};
    rows.forEach(r=>{const rk=key(r,cfg.rows),ck=cfg.cols==='none'?'Tất cả':key(r,cfg.cols);(byRow[rk]??=[]).push(r);(byCol[ck]??=[]).push(r);(g[rk+'|'+ck]??=[]).push(r)});
    const order=(o,dim)=>dim==='time'?Object.keys(o).sort():Object.keys(o).sort((a,b)=>o[b].length-o[a].length);
    const allR=order(byRow,cfg.rows),allC=order(byCol,cfg.cols),rk=allR.slice(0,30),ck=allC.slice(0,12);
    return{ck,body:rk.map(k=>({k,cells:ck.map(c=>agg(g[k+'|'+c]||[])),tot:agg(byRow[k])})),colTot:ck.map(c=>agg(byCol[c])),grand:agg(rows),cutR:allR.length>30,cutC:allC.length>12}},[fl,cfg,drill],sim);
  const set=p=>{setCfg({...cfg,...p});setDrill([])};
  const setLevel=l=>{const o=TIME_OPTS[l];setFl({...fl,level:l,from:o[0],to:o[o.length-1]});setDrill([])};
  const resetAll=()=>{setFl(DEF_O);setCfg(DEF_CFG);setDrill([])};
  const [mName,mFmt]=MEAS[cfg.m],val=a=>a.n?mFmt(a):'—';
  const nums=data?data.body.flatMap(b=>b.cells.filter(c=>c.n).map(c=>c[cfg.m])):[],mx=Math.max(...nums,1e-9),mn=Math.min(...nums,0);
  const rel=c=>(c[cfg.m]-mn)/((mx-mn)||1);
  const heat=c=>({background:view==='heat'&&c.n?`rgba(15,118,110,${0.08+0.7*rel(c)})`:'',color:view==='heat'&&c.n&&rel(c)>.6?'#fff':''});
  const drillInto=v=>{if(cfg.rows==='time'&&NEXT[cfg.tl]){setDrill([...drill,{level:cfg.tl,value:v}]);setCfg({...cfg,tl:NEXT[cfg.tl]})}};
  const rollUp=i=>{const lv=drill[i]?.level||cfg.tl;setDrill(drill.slice(0,i));setCfg({...cfg,tl:lv})};
  const bad=fl.from>fl.to,opts=TIME_OPTS[fl.level];
  const gcols=[cfg.rows,cfg.cols!=='none'?cfg.cols:null].filter(Boolean).map(d=>d==='time'?TL_SQL[cfg.tl]:DIM_SQL[d]).join(', ');
  const where=[dateRange(fl.level,fl.from,fl.to),...drill.map(d=>dateRange(d.level,d.value,d.value)),fl.sstates.length&&`sl.state IN (${fl.sstates.map(s=>`'${s}'`).join(', ')})`,
    fl.cstates.length&&`c.state IN (${fl.cstates.map(s=>`'${s}'`).join(', ')})`,fl.cats.length&&`p.category_name_english IN (${fl.cats.map(s=>`'${s}'`).join(', ')})`,fl.lateOnly&&'f.delay_days > 0'].filter(Boolean);
  const sql=`-- Minh hoạ truy vấn tương ứng trên star schema\nSELECT ${gcols}, ${MEAS_SQL[cfg.m]} AS ${cfg.m}\nFROM Fact_Delivery_SLA f\nJOIN Dim_Time t ON f.time_id = t.time_id\nJOIN Dim_Location c ON f.customer_location_id = c.location_id\nJOIN Dim_Location sl ON f.seller_location_id = sl.location_id\nJOIN Dim_Product p ON f.product_id = p.product_id\nWHERE ${where.join('\n  AND ')}\nGROUP BY ${gcols};`;
  const csv=()=>{const l=[[DIMS[cfg.rows],...data.ck,'Tổng'],...data.body.map(b=>[b.k,...b.cells.map(val),val(b.tot)])];
    const u=URL.createObjectURL(new Blob(['\ufeff'+l.map(r=>r.map(x=>`"${x}"`).join(',')).join('\n')],{type:'text/csv'}));const a=document.createElement('a');a.href=u;a.download='olap.csv';a.click();URL.revokeObjectURL(u)};
  return <div className="space-y-3">
    <section className="panel p-3 space-y-3" aria-label="Bộ lọc và cấu hình">
      <div className="flex flex-wrap items-end gap-x-5 gap-y-2"><span className="text-sm font-semibold self-center">Bộ lọc (slice / dice)</span>
        <label className="text-xs text-slate-600">Mức thời gian<br/><select className="sel" value={fl.level} onChange={e=>setLevel(e.target.value)}>{Object.entries(LV_NAME).reverse().map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-xs text-slate-600">Từ<br/><select className="sel" value={fl.from} onChange={e=>{setFl({...fl,from:e.target.value});setDrill([])}}>{opts.map(o=><option key={o}>{o}</option>)}</select></label>
        <label className="text-xs text-slate-600">Đến<br/><select className="sel" value={fl.to} onChange={e=>{setFl({...fl,to:e.target.value});setDrill([])}}>{opts.map(o=><option key={o}>{o}</option>)}</select></label>
        <MultiSelect label="Bang người bán" options={STATES} value={fl.sstates} onChange={v=>setFl({...fl,sstates:v})}/>
        <MultiSelect label="Bang khách hàng" options={STATES} value={fl.cstates} onChange={v=>setFl({...fl,cstates:v})}/>
        <MultiSelect label="Danh mục" options={CATS} value={fl.cats} onChange={v=>setFl({...fl,cats:v})}/>
        <label className="flex items-center gap-1.5 text-xs pb-1.5"><input type="checkbox" checked={fl.lateOnly} onChange={e=>setFl({...fl,lateOnly:e.target.checked})}/>Chỉ đơn trễ</label>
        {bad&&<span className="text-xs text-red-700 font-medium" role="alert">“Từ” đang sau “Đến” – hãy chọn lại.</span>}</div>
      <div className="flex flex-wrap items-end gap-x-5 gap-y-2 border-t border-slate-100 pt-3"><span className="text-sm font-semibold self-center">Bảng</span>
        <DimensionPick label="Hàng" field="rows" config={cfg} onChange={value=>set({rows:value})}/>
        <DimensionPick label="Cột" field="cols" none config={cfg} onChange={value=>set({cols:value})}/>
        {(cfg.rows==='time'||cfg.cols==='time')&&<div className="text-xs text-slate-600">Mức thời gian trong bảng<div className="flex gap-1 mt-0.5">{Object.keys(LV_NAME).reverse().map(l=><button key={l} className={'btn '+(cfg.tl===l?'btn-main':'')} onClick={()=>{setDrill([]);setCfg({...cfg,tl:l})}}>{LV_NAME[l]}</button>)}</div></div>}
        <label className="text-xs text-slate-600">Chỉ số<br/><select className="sel mt-0.5" value={cfg.m} onChange={e=>set({m:e.target.value})}>{Object.entries(MEAS).map(([k,[n]])=><option key={k} value={k}>{n}</option>)}</select></label>
        <button className="btn" onClick={resetAll}>Đặt lại</button></div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs"><span className="text-slate-500">Truy vấn mẫu:</span>{PRESETS.map(p=><button key={p.t} className="underline text-teal-800 hover:text-teal-950" onClick={()=>{setDrill([]);setCfg({rows:p.rows,cols:p.cols,tl:p.tl,m:p.m})}}>{p.t}</button>)}</div>
    </section>
    <section className="min-w-0 space-y-3">
      <div className="panel p-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm">{mName} theo <b>{DIMS[cfg.rows]}</b>{cfg.cols!=='none'&&<> × <b>{DIMS[cfg.cols]}</b></>}
          {drill.length>0&&<nav className="text-xs mt-1 text-slate-600" aria-label="Phân cấp thời gian">
            <button className="underline" onClick={()=>rollUp(0)}>Tất cả</button>{drill.map((d,i)=><span key={i}> › <button className="underline" onClick={()=>rollUp(i+1)}>{d.value}</button></span>)}
            <button className="btn ml-2" onClick={()=>rollUp(drill.length-1)}>▲ Roll-up</button></nav>}</div>
        <div className="flex items-center gap-1">{[['table','Bảng'],['heat','Heatmap'],['chart','Biểu đồ']].map(([k,t])=><button key={k} className={'btn '+(view===k?'btn-main':'')} onClick={()=>setView(k)}>{t}</button>)}
          <button className="btn" disabled={!data} onClick={csv}>Xuất CSV</button></div></div>
      {error?<Errored msg={error} retry={retry}/>:loading||!data?<Skeleton h={300}/>:!data.grand.n?<Empty reset={resetAll}/>:
      view==='chart'?<div className="panel p-4 h-80"><ResponsiveContainer><BarChart data={data.body.map(b=>({k:b.k,v:b.tot[cfg.m]}))}><CartesianGrid vertical={false} stroke="#e5e9ec"/><XAxis dataKey="k" tick={{fontSize:11}}/><YAxis tick={{fontSize:11}} tickFormatter={v=>cfg.m==='rate'?pct(v):v}/><Tooltip formatter={v=>cfg.m==='rate'?pct(v):num(v,2)}/><Bar dataKey="v" name={mName} fill="#0f766e"/></BarChart></ResponsiveContainer></div>:
      <div className="panel overflow-x-auto"><table className="w-full text-xs"><thead className="bg-slate-50"><tr><th className="text-left py-2 px-3">{DIMS[cfg.rows]}</th>{data.ck.map(c=><th key={c} className="text-right px-3">{c}</th>)}<th className="text-right px-3 bg-slate-100">Tổng</th></tr></thead>
        <tbody>{data.body.map(b=><tr key={b.k} className="border-t border-slate-100">
          <th className="text-left py-2 px-3 font-medium">{cfg.rows==='time'&&NEXT[cfg.tl]?<button className="underline decoration-dotted hover:text-teal-800" title="Drill-down xuống mức thấp hơn" onClick={()=>drillInto(b.k)}>▼ {b.k}</button>:b.k}</th>
          {b.cells.map((c,i)=><td key={i} className={'text-right px-3 '+(c.n&&c.n<15?'text-slate-400 italic':'')} style={heat(c)} title={c.n?`${c.n} đơn${c.n<15?' – mẫu nhỏ':''}`:'Không có dữ liệu'}>{val(c)}</td>)}
          <td className="text-right px-3 font-semibold bg-slate-50">{val(b.tot)}</td></tr>)}
          <tr className="border-t-2 border-slate-300 bg-slate-50 font-semibold"><th className="text-left py-2 px-3">Tổng</th>{data.colTot.map((c,i)=><td key={i} className="text-right px-3">{val(c)}</td>)}<td className="text-right px-3">{val(data.grand)}</td></tr></tbody></table>
        <p className="text-[11px] text-slate-500 p-2">Chữ nghiêng xám: ô dưới 15 đơn (mẫu nhỏ). Rê chuột vào ô để xem số đơn.{data.cutR&&' Chỉ hiển thị 30 hàng nhiều đơn nhất (hàng Tổng vẫn tính trên toàn bộ).'}{data.cutC&&' Chỉ hiển thị 12 cột đầu.'}{cfg.rows==='time'&&NEXT[cfg.tl]&&' Bấm ▼ ở hàng thời gian để drill-down.'}</p></div>}
      <div className="panel"><button className="w-full text-left px-3 py-2 text-sm font-medium flex justify-between" aria-expanded={sqlOpen} onClick={()=>setSqlOpen(!sqlOpen)}>SQL tương ứng<span>{sqlOpen?'▴':'▾'}</span></button>
        {sqlOpen&&<pre className="px-3 pb-3 text-xs overflow-x-auto text-slate-700">{sql}</pre>}</div>
    </section></div>}

/* ============ 3. DSS: từ tuyến ưu tiên đến khuyến nghị hành động ============ */
const BriefCard=({title,owner,note,children})=><section className="panel p-3 flex flex-col"><div className="font-semibold text-sm">{title}</div>
  <div className="text-[11px] text-slate-500 mb-1">Phụ trách: {owner}</div>{children}<p className="text-[11px] text-slate-500 mt-auto pt-2">{note}</p></section>;
const BriefRow=({main,sub,pill,onLog})=><div className="border-t border-slate-100 py-1.5 text-xs flex gap-2 justify-between"><div className="min-w-0"><div><b>{main}</b> {pill}</div><div className="text-slate-600">{sub}</div></div>
  <button className="btn self-start shrink-0" onClick={onLog}>Ghi nhận</button></div>;
const NoItem=()=><p className="text-xs text-slate-500 py-2">Không có mục nào đủ điều kiện.</p>;
const ciTxt=ci=>`CI 95%: ${num(ci.avLo,0)}–${num(ci.avHi,0)} đơn`;

function Dss({year,setYear,sim,initRoute}){
  const [sort,setSort]=useState('rate'),[sel,setSel]=useState(initRoute),[q,setQ]=useState(.5),[cut,setCut]=useState({appr:0,prep:0,transit:0}),[log,setLog]=useState([]);
  const {data,loading,error,retry}=useData(()=>{const rows=byYear(year);return{rows,rs:routeStats(rows),brief:buildBrief(rows)}},[year],sim);
  const rec=(g,l)=>setLog([{t:new Date().toLocaleTimeString('vi-VN'),g,l},...log].slice(0,50));
  const head=<div className="flex flex-wrap items-center justify-between gap-2"><YearSel year={year} setYear={setYear}/>
    <p className="text-xs text-slate-500 max-w-3xl">Mọi số “tránh được” là mô phỏng theo luật trên dữ liệu mẫu, không phải tác động nhân quả và không thực thi hành động vận hành. Dữ liệu thật sẽ lấy từ API <code>/api/dss/*</code>.</p></div>;
  if(error)return <div className="space-y-3">{head}<Errored msg={error} retry={retry}/></div>;
  if(loading||!data)return <div className="space-y-3">{head}<Skeleton h={260}/><Skeleton h={260}/></div>;
  const {rows,rs,brief}=data,{L,list}=rs;
  if(!list.length)return <div className="space-y-3">{head}<Empty msg="Chưa có tuyến nào đủ số đơn để phân tích"/></div>;
  const ranked=[...list].sort((a,b)=>sort==='rate'?b.p-a.p:b.k-a.k).slice(0,10);
  const cur=list.find(s=>s.route===sel)||[...list].sort((a,b)=>b.p-a.p)[0];
  const b=bench(rows,q),b25=bench(rows,.25),att=attribution(cur.rows,b),cutDef=p25cut(cur.rows,b25);
  const mx=Object.fromEntries(STAGES.map(([k])=>[k,Math.ceil(Math.max(...cur.rows.map(r=>r[k])))]));
  const c=Object.fromEntries(STAGES.map(([k])=>[k,Math.min(cut[k],mx[k])])),any=STAGES.some(([k])=>c[k]>0);
  const after=simulate(cur.rows,c),avoided=cur.k-after,newRate=after/cur.n,ci=bootCI(cur.rows,c),[evT,evK]=evid(ci,cur.low);
  const pick=r=>{setSel(r);setCut({appr:0,prep:0,transit:0})};
  const shares=att?[['Duyệt thanh toán',att.appr,'#94a3b8'],['Người bán chuẩn bị',att.prep,'#0f766e'],['Vận chuyển',att.transit,'#b45309'],['Chưa giải thích được (liên quan ngày cam kết)',att.resid,'#64748b']]:[];
  return <div className="space-y-4">{head}
    <section className="panel p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-semibold">1. Chọn tuyến ưu tiên</h2>
      <p className="text-xs text-slate-500">Tỷ lệ trễ chung L = {pct(L)}. Đỏ: ≥ 2,0×L = {pct(2*L)}; vàng: ≥ 1,5×L = {pct(1.5*L)}. “Chưa chắc chắn”: cận dưới Wilson 95% thấp hơn ngưỡng của mức đó.</p></div>
      <div className="flex gap-1">{[['rate','Xếp theo tỷ lệ trễ'],['count','Xếp theo số đơn trễ']].map(([k,t])=><button key={k} className={'btn '+(sort===k?'btn-main':'')} onClick={()=>setSort(k)}>{t}</button>)}</div></div>
      <div className="overflow-x-auto mt-2"><table className="w-full text-xs"><thead className="text-left text-slate-500"><tr><th className="py-1 px-2">Tuyến</th><th className="text-right px-2">Đơn</th><th className="text-right px-2">Trễ</th><th className="text-right px-2">Tỷ lệ</th><th className="text-right px-2">CI Wilson 95%</th><th className="px-2">Mức</th><th className="px-2">Cảnh báo</th></tr></thead>
        <tbody>{ranked.map(s=><tr key={s.route} className={'border-t border-slate-100 cursor-pointer hover:bg-slate-50 '+(s.route===cur.route?'pick':'')} onClick={()=>pick(s.route)}>
          <td className="py-1.5 px-2 font-medium"><button className="text-left" aria-pressed={s.route===cur.route}>{s.route}</button></td><td className="text-right px-2">{int(s.n)}</td><td className="text-right px-2">{int(s.k)}</td><td className="text-right px-2 font-semibold">{pct(s.p)}</td>
          <td className="text-right px-2 text-slate-600">{pct(s.lo)} – {pct(s.hi)}</td><td className="px-2"><Pill t={LV[s.level][0]} c={LV[s.level][1]}/></td><td className="px-2">{flagsOf(s)}</td></tr>)}</tbody></table></div>
      <p className="text-[11px] text-slate-500 mt-2">Hai cách xếp hạng (theo tỷ lệ, theo số đơn) có thể cho kết quả khác nhau; danh sách là gợi ý ưu tiên, không phải ranh giới cứng.</p></section>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <section className="panel p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-semibold">2. Giai đoạn nghẽn của tuyến {cur.route}</h2>
        <p className="text-xs text-slate-500">Tỷ trọng từng giai đoạn trong các đơn trễ của tuyến (Shapley trên 3 giai đoạn). Nhãn phân bổ mô tả, không phải kết luận nhân quả.</p></div>
        <div className="flex gap-1">{[[.5,'q = 0,5'],[.25,'q = 0,25']].map(([v,t])=><button key={v} className={'btn '+(q===v?'btn-main':'')} onClick={()=>setQ(v)}>{t}</button>)}</div></div>
        {att?<div className="mt-3 space-y-2">{shares.map(([t,v,col])=><div key={t}><div className="flex justify-between text-xs"><span>{t}</span><b>{pct(v)}</b></div>
          <div className="h-3 bg-slate-100 rounded-sm"><div className="h-3 rounded-sm" style={{width:Math.max(0,v*100)+'%',background:col}}/></div></div>)}
          <p className="text-[11px] text-slate-500">Dựa trên {att.n} đơn trễ. Mỗi đơn so với phân vị q = {q} của từng giai đoạn trên toàn bộ dữ liệu đang xem.</p>
          {att.n<10&&<p className="text-xs text-amber-800 bg-amber-50 rounded px-2 py-1" role="status">Tuyến có rất ít đơn trễ nên tỷ trọng kém tin cậy.</p>}</div>:<p className="text-sm text-slate-600 mt-3">Tuyến này không có đơn trễ.</p>}</section>
      <section className="panel p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="font-semibold">3. Thử kịch bản rút ngắn (What-if)</h2>
        <p className="text-xs text-slate-500">Giả định 1 ngày rút ngắn = 1 ngày giao sớm hơn; mức rút của mỗi giai đoạn không vượt thời gian thực tế của đơn.</p></div>
        <div className="flex gap-1"><button className="btn" onClick={()=>setCut({appr:Math.min(cutDef.appr,mx.appr),prep:Math.min(cutDef.prep,mx.prep),transit:Math.min(cutDef.transit,mx.transit)})}>Đặt về mức P25</button><button className="btn" onClick={()=>setCut({appr:0,prep:0,transit:0})}>Xoá</button></div></div>
        <div className="mt-2 space-y-1.5">{STAGES.map(([k,t])=><label key={k} className="flex items-center gap-3 text-xs"><span className="w-36">{t}</span>
          <input type="range" min="0" max={mx[k]} step="0.1" value={c[k]} onChange={e=>setCut({...cut,[k]:+e.target.value})} className="flex-1" aria-label={'Rút ngắn '+t}/><b className="w-16 text-right">−{num(c[k])} ngày</b></label>)}</div>
        <div className="mt-3 bg-slate-50 rounded p-3 text-sm">{any?<>
          <div>Tỷ lệ trễ: <b>{pct(cur.p)}</b> → <b>{pct(newRate)}</b> <span className="text-slate-500">(−{num((cur.p-newRate)*100,2)} điểm %, CI 95%: −{num(ci.ppLo,2)} đến −{num(ci.ppHi,2)})</span></div>
          <div className="mt-1">Ước tính tránh được <b>{avoided}</b> / {cur.k} đơn trễ <span className="text-slate-500">({ciTxt(ci)})</span> <Pill t={evT} c={ST[evK]}/></div>
          <p className="text-[11px] text-slate-500 mt-1">CI từ bootstrap 300 lần (seed 42) chỉ phản ánh nhiễu lấy mẫu, không chứng tỏ mục tiêu khả thi. CI chứa 0 thì kết luận là “chưa đủ bằng chứng”.</p></>
          :<span className="text-slate-600">Kéo thanh trượt hoặc bấm “Đặt về mức P25” để xem ước tính cho tuyến {cur.route}.</span>}</div></section>
    </div>
    <section className="space-y-2"><div><h2 className="font-semibold">4. Decision Brief</h2>
      <p className="text-xs text-slate-500">Năm nhóm hành động tách biệt, cùng chồng lấn trên các đơn trễ nên <b>không cộng số giữa các nhóm</b>. Mỗi tổng chỉ áp dụng cho các mục trong nhóm đó.</p></div>
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
        <BriefCard title="Tuyến (5 tuyến đầu, mức P25)" owner="Quản lý vận hành logistics" note="Nếu đưa cả ba giai đoạn về P25 toàn cục thì ước tính tránh được số đơn trễ như trên. Tuyến mẫu nhỏ nằm ở nhóm “Cần thêm dữ liệu”.">
          {brief.routes.map(r=>{const [t,k]=evid(r.ci,r.low);return <BriefRow key={r.route} main={r.route} pill={<Pill t={t} c={ST[k]}/>} onLog={()=>rec('Tuyến',r.route)}
            sub={`Tránh ~${r.avoided}/${r.k} đơn trễ (${ciTxt(r.ci)}). Rút: duyệt ${num(r.cut.appr)} + chuẩn bị ${num(r.cut.prep)} + vận chuyển ${num(r.cut.transit)} ngày`}/>})}{!brief.routes.length&&<NoItem/>}</BriefCard>
        <BriefCard title="Thanh toán (chỉ cắt giai đoạn duyệt)" owner="Hệ thống thanh toán / sàn" note="Chỉ rút giai đoạn duyệt thanh toán về P25; thường nhỏ so với vận chuyển.">
          {brief.pay.map(p=>{const [t,k]=evid(p.ci,p.low);return <BriefRow key={p.pay} main={p.pay} pill={<Pill t={t} c={ST[k]}/>} onLog={()=>rec('Thanh toán',p.pay)}
            sub={`Tránh ~${p.avoided} đơn trễ (${ciTxt(p.ci)}), rút duyệt ${num(p.cut)} ngày; ${int(p.n)} đơn`}/>})}</BriefCard>
        <BriefCard title="Chính sách cam kết (5 ô đầu, chỉ số ròng)" owner="Chủ chính sách cam kết giao hàng" note="Đổi định nghĩa trễ (cam kết = Q95 thời gian hoàn tất), không rút ngắn thời gian giao; chỉ hiển thị số ròng (NET). Cam kết quá dài không thực tế.">
          <p className="text-[11px] text-slate-600 pb-1">Ô tuyến: {brief.promCnt.tight} tight / {brief.promCnt.ok} ok / {brief.promCnt.loose} loose.</p>
          {brief.promTop.map(x=><BriefRow key={x.route} main={x.route} pill={x.need>40&&<Pill t="Cam kết quá dài" c={ST.warn}/>} onLog={()=>rec('Chính sách cam kết',x.route)}
            sub={`Cam kết trung vị ${num(x.med)} → cần ${x.need} ngày: ròng +${x.net} đơn được phân loại lại là đúng hạn`}/>)}{!brief.promTop.length&&<NoItem/>}</BriefCard>
        <BriefCard title="Người bán (5 người đầu, chỉ là liên hệ)" owner="Bộ phận hỗ trợ người bán" note="Số đơn trễ vượt tỷ lệ hệ thống, không phải số đơn tránh được; chưa hiệu chỉnh theo cơ cấu tuyến của từng người bán.">
          {brief.sellers.map(s=><BriefRow key={s.id} main={s.id} pill={<Pill t={s.prio?'Ưu tiên':'Chưa đủ bằng chứng'} c={s.prio?ST.ok:ST.warn}/>} onLog={()=>rec('Người bán',s.id)}
            sub={`${s.k}/${s.n} đơn trễ (${pct(s.p)}), vượt mức hệ thống ~${num(s.excess,0)} đơn`}/>)}{!brief.sellers.length&&<NoItem/>}</BriefCard>
        <BriefCard title="Cần thêm dữ liệu (tuyến gắn cờ, mẫu nhỏ)" owner="Quản lý vận hành logistics" note={`Tuyến đỏ/vàng nhưng dưới ${LOW_SAMPLE} đơn-tuyến; không tính là hành động ưu tiên chính. Thu thập thêm đơn rồi đánh giá lại.`}>
          {brief.more.map(s=><BriefRow key={s.route} main={s.route} pill={<Pill t={LV[s.level][0]} c={LV[s.level][1]}/>} onLog={()=>rec('Cần thêm dữ liệu',s.route)}
            sub={`${s.n} đơn, tỷ lệ trễ ${pct(s.p)}; cần thêm ít nhất ${LOW_SAMPLE-s.n} đơn`}/>)}{!brief.more.length&&<NoItem/>}</BriefCard>
        <section className="panel p-3"><div className="font-semibold text-sm">Nhật ký ghi nhận khuyến nghị</div>
          <p className="text-[11px] text-slate-500 mb-1">Chỉ ghi log, không thực thi hành động (sau này gửi POST /api/dss/actions).</p>
          {log.length?<ul className="text-xs max-h-48 overflow-y-auto">{log.map((l,i)=><li key={i} className="border-t border-slate-100 py-1"><span className="text-slate-500">{l.t}</span> · {l.g}: <b>{l.l}</b></li>)}</ul>:<p className="text-xs text-slate-500 py-2">Chưa có ghi nhận nào.</p>}</section>
      </div></section></div>}

/* ============ KHUNG ỨNG DỤNG ============ */
const TITLES={dashboard:['Tổng quan giao hàng và SLA','Giám sát nhanh: vấn đề lớn đến đâu, đang tăng hay giảm, tập trung ở tuyến nào'],
  olap:['Truy vấn đa chiều (OLAP)','Tự khám phá: trễ ở đâu, khi nào, với nhóm nào'],dss:['DSS Action Center','Nên xem xét làm gì và kết quả ước tính ra sao']};
function App(){
  const [page,setPage]=useState('dashboard'),[open,setOpen]=useState(true),[year,setYear]=useState('all'),[sim,setSim]=useState({error:false}),[dssRoute,setDssRoute]=useState(null);
  const nav=[['dashboard','▦','BI Dashboard'],['olap','▤','OLAP'],['dss','◆','DSS']];
  const goDss=r=>{setDssRoute(r||null);setPage('dss')};
  return <div className="min-h-screen flex">
    <aside className={(open?'w-52':'w-14')+' hidden md:flex shrink-0 flex-col bg-[#14232e] text-slate-100 sticky top-0 h-screen transition-all'}>
      <div className="px-3 py-4 flex items-center justify-between border-b border-white/10">{open?<div><div className="font-semibold">Olist DSS</div><div className="text-[11px] text-slate-400">Giao hàng trễ</div></div>:<span className="mx-auto font-semibold">DSS</span>}
        <button aria-label="Thu gọn menu" className="px-1.5 rounded hover:bg-white/10" onClick={()=>setOpen(!open)}>{open?'‹':'›'}</button></div>
      <nav className="p-2 space-y-1">{nav.map(([k,i,t])=><button key={k} aria-current={page===k} onClick={()=>{setDssRoute(null);setPage(k)}} className={'w-full flex items-center gap-3 px-3 py-2 rounded text-sm text-left '+(page===k?'bg-teal-700 text-white':'text-slate-300 hover:bg-white/10')}><span aria-hidden>{i}</span>{open&&t}</button>)}</nav>
      {open&&<div className="mt-auto p-3 text-[11px] text-slate-400 border-t border-white/10">Star schema: Fact_Delivery_SLA</div>}
    </aside>
    <main className="flex-1 min-w-0">
      <header className="sticky top-0 z-30 bg-white border-b border-slate-300 px-5 py-2.5 flex items-center justify-between gap-3">
        <div><h1 className="font-semibold leading-tight">{TITLES[page][0]}</h1><p className="text-xs text-slate-500">{TITLES[page][1]} · Dữ liệu mẫu sinh ngẫu nhiên, sẽ thay bằng API từ kho dữ liệu</p></div>
        <div className="flex items-center gap-2"><div className="md:hidden flex gap-1">{nav.map(([k,,t])=><button key={k} className={'btn '+(page===k?'btn-main':'')} onClick={()=>{setDssRoute(null);setPage(k)}}>{t}</button>)}</div>
          {DEV&&<button className="btn" onClick={()=>setSim({error:!sim.error})}>{sim.error?'Tắt lỗi giả lập':'Giả lập lỗi'}</button>}</div>
      </header>
      <div className="px-5 py-4 pb-8 max-w-[1400px] mx-auto">
        {page==='dashboard'&&<Dashboard year={year} setYear={setYear} sim={sim} goDss={goDss}/>}
        {page==='olap'&&<Olap sim={sim}/>}
        {page==='dss'&&<Dss key={dssRoute||'-'} year={year} setYear={setYear} sim={sim} initRoute={dssRoute}/>}
      </div></main></div>}
export default App;
