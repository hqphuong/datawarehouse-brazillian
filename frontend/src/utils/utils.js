import { useEffect, useRef, useState } from 'react';

export function agg(a){const n=a.length,s=k=>a.reduce((x,y)=>x+y[k],0),m=k=>n?s(k)/n:null;
  return{n,late:s('late'),rate:m('late'),appr:m('appr'),prep:m('prep'),transit:m('transit'),total:m('total'),freight:m('freight'),review:m('review'),gmv:s('price')}}
const vn=(x,d)=>x.toFixed(d).replace('.',',');
export const pct=v=>v==null?'\u2014':vn(v*100,1)+'%',num=(v,d=1)=>v==null?'\u2014':vn(v,d),int=v=>v.toLocaleString('vi-VN');

export const DEV=new URLSearchParams(location.search).has('dev');
export function useData(compute,deps,sim){
  const depsKey=JSON.stringify(deps);
  const computeRef=useRef(compute);
  const [st,setSt]=useState({key:null,loading:true,error:null,data:null});
  const [tick,setTick]=useState(0);
  useEffect(()=>{computeRef.current=compute},[compute]);
  useEffect(()=>{let ok=true;const controller=new AbortController();
    const t=setTimeout(()=>{if(!ok)return;
      if(sim.error)return setSt({key:depsKey,loading:false,error:'Không kết nối được máy chủ dữ liệu.',data:null});
      Promise.resolve().then(()=>computeRef.current(controller.signal)).then(data=>{
        if(ok)setSt({key:depsKey,loading:false,error:null,data})
      }).catch(e=>{
        if(ok&&!controller.signal.aborted)setSt({key:depsKey,loading:false,error:e?.message||'Không tải được dữ liệu.',data:null})
      })},250);
    return()=>{ok=false;controller.abort();clearTimeout(t)}},[depsKey,tick,sim.error]);
  return{
    loading:st.key!==depsKey||st.loading,
    error:st.key===depsKey?st.error:null,
    data:st.key===depsKey?st.data:null,
    retry:()=>setTick(t=>t+1)
  };
}

/* ============ THÀNH PHẦN CHUNG ============ */

export { MultiSelect, YearSel, Skeleton, Errored, Empty, Pill, ST, LV, flagsOf } from './components.jsx';
