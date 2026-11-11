

/* eslint-disable react-refresh/only-export-components */
import { pct, num, int } from '../utils/utils.js';

// Seeded sample data and analysis logic used by the BI Dashboard, OLAP, and DSS views.

/* ============ DỮ LIỆU MẪU (sinh ngẫu nhiên, KHÔNG phải số liệu Olist thật – thay bằng API) ============
   Mỗi dòng = một đơn-tuyến đã giao (route = bang người bán → bang khách hàng), cùng mẫu số với DSS trong báo cáo.
   delay > 0 là trễ; promise = total − delay (ngày cam kết = tổng thời gian hoàn tất − số ngày trễ). */
export const APP_MONTHS=[];for(let y=2017;y<=2018;y++)for(let m=1;m<=12;m++){if(y===2018&&m>8)break;APP_MONTHS.push(`${y}-${String(m).padStart(2,'0')}`)}
export const QUARTERS=[...new Set(APP_MONTHS.map(m=>m.slice(0,4)+'-Q'+Math.ceil(+m.slice(5)/3)))];
export const APP_YEARS=['2017','2018'];
export const TIME_OPTS={month:APP_MONTHS,quarter:QUARTERS,year:APP_YEARS};
export const LV_NAME={year:'Năm',quarter:'Quý',month:'Tháng'};
export const APP_STATES=['AL','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RS','SC','SE','SP','TO'];
export const APP_CATS=['bed_bath_table','health_beauty','sports_leisure','computers_accessories','furniture_decor','toys'];
export const PAYS=['credit_card','boleto','voucher','debit_card'];
export const SELLER_STATES=['SP','SP','SP','MG','PR','RJ'];
export function rng(s){return()=>{s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
export const RAW=(()=>{const r=rng(7),pick=a=>a[Math.floor(r()*a.length)],out=[];
  const heavy=['SP','SP','SP','SP','RJ','RJ','MG','MG','RS','PR','SC','BA','PE','CE',...APP_STATES];
  for(let i=0;i<1400;i++){const month=pick(APP_MONTHS),state=pick(heavy),si=Math.floor(r()*30);
    const far=['MA','AL','PI','SE','BA','PA','TO'].includes(state);
    const isLate=r()<(0.05+(far?0.12:0)+(['2017-11','2018-03'].includes(month)?0.05:0)+(si<3?0.08:0));
    const appr=+(0.1+r()*0.9).toFixed(1),prep=+(1+r()*3).toFixed(1),transit=+((far?9:4)+r()*7+(isLate?4:0)).toFixed(1);
    const total=+(appr+prep+transit).toFixed(1);
    const delay=isLate?+(0.5+r()*Math.max(0,Math.min(6,total-6))).toFixed(1):-+(0.1+r()*8).toFixed(1);
    const ss=SELLER_STATES[si%6];
    out.push({id:'ord_'+(9000+i),month,quarter:month.slice(0,4)+'-Q'+Math.ceil(+month.slice(5)/3),year:month.slice(0,4),
      state,seller_state:ss,route:ss+'→'+state,seller:'seller_'+String(si+1).padStart(2,'0'),category:pick(APP_CATS),payment:pick(PAYS),
      late:delay>0?1:0,delay,appr,prep,transit,total,promise:+(total-delay).toFixed(1),
      price:+(20+r()*180).toFixed(2),freight:+(8+r()*30).toFixed(1),review:Math.max(1,Math.min(5,Math.round(isLate?2.5+r()*2:4+r()*1.5)))})}
  return out})();
export const byYear=y=>RAW.filter(r=>y==='all'||r.year===y);

/* ============ LOGIC DSS (thuần hàm; thay bằng API /routes, /attribution, /scenario, /brief, /promise-policy, /sellers) ============
   Ngưỡng trong báo cáo (dữ liệu thật): min_orders=100, low_sample<200. Dữ liệu mẫu chỉ 1 400 dòng nên thu nhỏ lại. */
export const MIN_ORDERS=10,LOW_SAMPLE=30,MIN_SELLER=30,Z=1.96;
export const STAGES=[['appr','Duyệt thanh toán'],['prep','Người bán chuẩn bị'],['transit','Vận chuyển']];
export function wilson(k,n){if(!n)return[0,0];const p=k/n,z2=Z*Z,den=1+z2/n,c=p+z2/(2*n),m=Z*Math.sqrt(p*(1-p)/n+z2/(4*n*n));return[(c-m)/den,(c+m)/den]}
export function quant(v,q){if(!v.length)return 0;const s=[...v].sort((a,b)=>a-b),i=(s.length-1)*q,lo=Math.floor(i),hi=Math.ceil(i);return s[lo]+(s[hi]-s[lo])*(i-lo)}
export const mean=(a,k)=>a.length?a.reduce((s,r)=>s+r[k],0)/a.length:0;
export const bench=(rows,q)=>Object.fromEntries(STAGES.map(([k])=>[k,quant(rows.map(r=>r[k]),q)]));
export function routeStats(rows){
  const g={};rows.forEach(r=>(g[r.route]??=[]).push(r));
  const L=rows.length?rows.reduce((s,r)=>s+r.late,0)/rows.length:0;
  const list=Object.entries(g).filter(([,a])=>a.length>=MIN_ORDERS).map(([route,a])=>{
    const n=a.length,k=a.reduce((s,r)=>s+r.late,0),p=k/n,[lo,hi]=wilson(k,n);
    const level=L>0&&p>=2*L?'red':L>0&&p>=1.5*L?'yellow':'none',thr=(level==='red'?2:1.5)*L;
    return{route,n,k,p,lo,hi,level,low:n<LOW_SAMPLE,uncertain:level!=='none'&&lo<thr,rows:a}});
  return{L,list}}
/* Shapley 3 giai đoạn cho một đơn trễ: v(S)=1 nếu đơn vẫn trễ khi các giai đoạn ngoài S về mức benchmark. */
export function shapley(o,b){
  const e=STAGES.map(([k])=>Math.max(0,o[k]-b[k])),W=[2/6,1/6,2/6];
  const v=m=>{let d=o.delay;for(let i=0;i<3;i++)if(!((m>>i)&1))d-=e[i];return d>0?1:0};
  const phi=[0,1,2].map(i=>{let s=0;for(let m=0;m<8;m++){if((m>>i)&1)continue;const c=((m&1)+((m>>1)&1)+((m>>2)&1));s+=W[c]*(v(m|(1<<i))-v(m))}return s});
  return{phi,resid:v(0)}}
export function attribution(rows,b){const late=rows.filter(r=>r.late);if(!late.length)return null;
  const s=[0,0,0];let res=0;late.forEach(o=>{const x=shapley(o,b);x.phi.forEach((p,i)=>s[i]+=p);res+=x.resid});
  const n=late.length;return{n,appr:s[0]/n,prep:s[1]/n,transit:s[2]/n,resid:res/n}}
export const reduced=(r,cut)=>STAGES.reduce((x,[k])=>x+Math.min(cut[k]||0,r[k]),0);
export const simulate=(rows,cut)=>rows.reduce((s,r)=>s+((r.delay-reduced(r,cut))>0?1:0),0);
export function bootCI(rows,cut,B=300,seed=42){const rnd=rng(seed),n=rows.length,av=[],pp=[];
  for(let b=0;b<B;b++){let bf=0,af=0;for(let i=0;i<n;i++){const r=rows[Math.floor(rnd()*n)];bf+=r.late;af+=(r.delay-reduced(r,cut))>0?1:0}av.push(bf-af);pp.push((bf-af)/n*100)}
  return{avLo:quant(av,.025),avHi:quant(av,.975),ppLo:quant(pp,.025),ppHi:quant(pp,.975)}}
export const p25cut=(rows,b25)=>Object.fromEntries(STAGES.map(([k])=>[k,Math.max(0,+(mean(rows,k)-b25[k]).toFixed(1))]));
export function evid(ci,low){return low?['Cần thêm dữ liệu','more']:ci.avLo<=0?['Chưa đủ bằng chứng','warn']:['Ước lượng ổn định','ok']}
export function buildBrief(rows){
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

export const OLAP_DIMS={time:'Thời gian',route:'Tuyến (bang bán → bang khách)',state:'Bang khách hàng',category:'Danh mục sản phẩm',seller:'Người bán'};
export const NEXT={year:'quarter',quarter:'month'};
export const OLAP_MEAS={n:['Số đơn',a=>int(a.n)],late:['Số đơn trễ',a=>int(a.late)],rate:['Tỷ lệ trễ',a=>pct(a.rate)],appr:['Duyệt thanh toán TB (ngày)',a=>num(a.appr)],
  prep:['Người bán chuẩn bị TB (ngày)',a=>num(a.prep)],transit:['Vận chuyển TB (ngày)',a=>num(a.transit)],freight:['Phí vận chuyển TB (R$)',a=>num(a.freight,2)],gmv:['GMV (R$)',a=>int(Math.round(a.gmv))]};
export const MEAS_SQL={n:'COUNT(DISTINCT f.order_id)',late:'COUNT(DISTINCT CASE WHEN f.delay_days > 0 THEN f.order_id END)',
  rate:'COUNT(DISTINCT CASE WHEN f.delay_days > 0 THEN f.order_id END)::float / COUNT(DISTINCT f.order_id)',appr:'AVG(f.approval_time_days)',
  prep:'AVG(f.seller_prep_time_days)',transit:'AVG(f.carrier_transit_time_days)',freight:'AVG(f.freight_value)',gmv:'SUM(f.price)'};
export const DIM_SQL={route:"sl.state || '→' || c.state",state:'c.state',category:'p.category_name_english',seller:'f.seller_id'};
export const TL_SQL={year:'t.year',quarter:'t.year, t.quarter',month:'t.year, t.month'};
export function dateRange(level,from,to){
  const st=v=>level==='year'?`${v}-01-01`:level==='quarter'?`${v.slice(0,4)}-${String((+v.slice(6)-1)*3+1).padStart(2,'0')}-01`:`${v}-01`;
  const en=v=>{let y=+v.slice(0,4),m=level==='year'?12:level==='quarter'?+v.slice(6)*3:+v.slice(5);return `${y}-${String(m).padStart(2,'0')}-${new Date(y,m,0).getDate()}`};
  return `t.full_date BETWEEN '${st(from)}' AND '${en(to)}'`}
export const DEF_O={level:'month',from:APP_MONTHS[0],to:APP_MONTHS[APP_MONTHS.length-1],sstates:[],cstates:[],cats:[],lateOnly:false};
export const DEF_CFG={rows:'state',cols:'time',tl:'quarter',m:'rate'};
export const PRESETS=[{t:'Tỷ lệ trễ theo bang khách × quý',rows:'state',cols:'time',tl:'quarter',m:'rate'},{t:'Tỷ lệ trễ theo tuyến',rows:'route',cols:'none',tl:'year',m:'rate'},
  {t:'Vận chuyển TB theo năm → tháng (drill-down)',rows:'time',cols:'none',tl:'year',m:'transit'},{t:'Số đơn trễ theo người bán',rows:'seller',cols:'none',tl:'year',m:'late'},{t:'GMV theo danh mục',rows:'category',cols:'none',tl:'year',m:'gmv'}];
export const olapRows=(fl,drill)=>RAW.filter(r=>r[fl.level]>=fl.from&&r[fl.level]<=fl.to&&(!fl.sstates.length||fl.sstates.includes(r.seller_state))&&(!fl.cstates.length||fl.cstates.includes(r.state))
  &&(!fl.cats.length||fl.cats.includes(r.category))&&(!fl.lateOnly||r.late)&&drill.every(d=>r[d.level]===d.value));
