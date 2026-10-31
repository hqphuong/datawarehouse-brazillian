import React, { useState } from 'react';
import { Icon } from './components/Icon';
import { Select } from './components/Select';
import { TABS, QTRS, MONTHS, STATES } from './data/mockData';

import DashboardView from './views/DashboardView';
import DSSView from './views/DssView';
import OLAPView from './views/OLAPView';
import ETLView from './views/ETLView';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [f, setF] = useState({ year: 'All', quarter: 'All', month: 'All', state: 'All' });
  const [msg, setMsg] = useState(null);

  const toast = m => { setMsg(m); setTimeout(() => setMsg(null), 2800); };
  const set = k => v => setF({ ...f, [k]: v });

  return (
    <div className="flex min-h-screen w-full max-w-full bg-slate-50 font-sans w-full overflow-x-hidden m-0 p-0">
      {/* Sidebar: w-16 ở mobile/màn hẹp, w-60 ở desktop */}
      <aside className="w-16 md:w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col sticky top-0 h-screen z-20">
        <div className="h-16 flex items-center justify-center md:justify-start md:px-5 gap-2.5 border-b border-slate-100">
          <span className="w-8 h-8 rounded-lg bg-blue-50 text-blue-500 flex items-center justify-center">
            <Icon n="truck" size={17} />
          </span>
          <span className="hidden md:block font-semibold text-slate-800 text-sm">Olist Logistics DSS</span>
        </div>
        <nav className="p-3 space-y-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              title={t.label}
              className={`w-full flex items-center justify-center md:justify-start gap-3 px-3 py-2.5 rounded-xl text-sm transition ${
                activeTab === t.id ? 'bg-blue-50 text-blue-600 font-medium' : 'text-slate-500 hover:bg-slate-50'
              }`}
            >
              <Icon n={t.icon} />
              <span className="hidden md:inline">{t.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Content: Bỏ giới hạn max-w-[1400px] để mở rộng full màn hình */}
      <div className="flex-1 min-w-0 flex flex-col w-full">
        <header className="h-16 bg-white/90 backdrop-blur border-b border-slate-200 px-4 md:px-8 flex items-center justify-between gap-3 sticky top-0 z-10 w-full">
          <h1 className="text-base font-semibold text-slate-800 hidden lg:block">
            {TABS.find(t => t.id === activeTab)?.label}
          </h1>
          <div className="flex flex-wrap items-center gap-2 md:gap-3 ml-auto">
            <Select label="Year" value={f.year} onChange={set('year')} options={['All', '2016', '2017', '2018']} />
            <Select label="Quarter" value={f.quarter} onChange={set('quarter')} options={['All', ...QTRS]} />
            <Select label="Month" value={f.month} onChange={set('month')} options={['All', ...MONTHS]} />
            <Select label="State" value={f.state} onChange={set('state')} options={['All', ...STATES]} />
          </div>
        </header>

        {/* Nội dung chính phủ kín 100% độ rộng màn hình */}
        <main className="p-4 md:p-8 w-full flex-1">
          {activeTab === 'dashboard' && <DashboardView f={f} />}
          {activeTab === 'dss' && <DSSView toast={toast} />}
          {activeTab === 'olap' && <OLAPView />}
          {activeTab === 'etl' && <ETLView toast={toast} />}
        </main>
      </div>

      {/* Toast thông báo góc dưới */}
      {msg && (
        <div className="fixed bottom-6 right-6 animate-fadeIn bg-white border border-emerald-100 shadow-lg rounded-xl px-4 py-3 text-sm text-slate-700 flex items-center gap-2 z-50">
          <Icon n="check" size={16} className="text-emerald-500" />
          {msg}
        </div>
      )}
    </div>
  );
}