// src/hooks/useData.js
import { useState, useEffect } from 'react';

export function useData(compute, deps, sim) {
  const [st, setSt] = useState({ loading: true, error: null, data: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let ok = true; setSt(s => ({ ...s, loading: true, error: null }));
    const t = setTimeout(() => {
      if (!ok) return;
      if (sim?.error) return setSt({ loading: false, error: 'Không kết nối được máy chủ dữ liệu.', data: null });
      try { setSt({ loading: false, error: null, data: compute() }); } catch (e) { setSt({ loading: false, error: e.message, data: null }); }
    }, 250);
    return () => { ok = false; clearTimeout(t); };
  }, [...deps, tick, sim?.error]);
  return { ...st, retry: () => setTick(t => t + 1) };
}