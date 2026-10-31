import React from 'react';

export const Select = ({ value, onChange, options, label }) => (
  <label className="flex items-center gap-2 text-xs text-slate-500">
    <span className="hidden sm:inline">{label}</span>
    <select 
      value={value} 
      onChange={e => onChange(e.target.value)}
      className="bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200"
    >
      {options.map(o => <option key={o}>{o}</option>)}
    </select>
  </label>
);