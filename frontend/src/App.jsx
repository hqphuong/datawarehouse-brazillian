import { useState } from "react";
import "./App.css";
import DashboardView from "./views/DashboardView.js";
import OlapView from "./views/OlapView.js";
import DssView from "./views/DssView.js";
import { DEV } from "./utils/utils.js";

const TITLES = {
  dashboard: [
    "Tổng quan giao hàng và SLA",
    "Giám sát nhanh: vấn đề lớn đến đâu, đang tăng hay giảm, tập trung ở tuyến nào",
  ],
  olap: [
    "Truy vấn đa chiều (OLAP)",
    "Tự khám phá: trễ ở đâu, khi nào, với nhóm nào",
  ],
  dss: ["DSS Action Center", "Nên xem xét làm gì và kết quả ước tính ra sao"],
};
export default function App() {
  const [page, setPage] = useState("dashboard"),
    [open, setOpen] = useState(true),
    [year, setYear] = useState("all"),
    [sim, setSim] = useState({ error: false }),
    [dssRoute, setDssRoute] = useState(null);
  const nav = [
    ["dashboard", "▦", "BI Dashboard"],
    ["olap", "▤", "OLAP"],
    ["dss", "◆", "DSS"],
  ];
  const goDss = (r) => {
    setDssRoute(r || null);
    setPage("dss");
  };
  return (
    <div className="min-h-screen flex">
      <aside
        className={
          (open ? "w-52" : "w-14") +
          " hidden md:flex shrink-0 flex-col bg-[#14232e] text-slate-100 sticky top-0 h-screen transition-all"
        }
      >
        <div className="px-3 py-4 flex items-center justify-between border-b border-white/10">
          {open ? (
            <div>
              <div className="font-semibold">Olist DSS</div>
              <div className="text-[11px] text-slate-400">Giao hàng trễ</div>
            </div>
          ) : (
            <span className="mx-auto font-semibold">DSS</span>
          )}
          <button
            aria-label="Thu gọn menu"
            className="px-1.5 rounded hover:bg-white/10"
            onClick={() => setOpen(!open)}
          >
            {open ? "‹" : "›"}
          </button>
        </div>
        <nav className="p-2 space-y-1">
          {nav.map(([k, i, t]) => (
            <button
              key={k}
              aria-current={page === k}
              onClick={() => {
                setDssRoute(null);
                setPage(k);
              }}
              className={
                "w-full flex items-center gap-3 px-3 py-2 rounded text-sm text-left " +
                (page === k
                  ? "bg-teal-700 text-white"
                  : "text-slate-300 hover:bg-white/10")
              }
            >
              <span aria-hidden>{i}</span>
              {open && t}
            </button>
          ))}
        </nav>
        {open && (
          <div className="mt-auto p-3 text-[11px] text-slate-400 border-t border-white/10">
            Star schema: Fact_Delivery_SLA
          </div>
        )}
      </aside>
      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 bg-white border-b border-slate-300 px-5 py-2.5 flex items-center justify-between gap-3">
          <div>
            <h1 className="font-semibold leading-tight">{TITLES[page][0]}</h1>
            <p className="text-xs text-slate-500">
              {TITLES[page][1]} · Dashboard và OLAP dùng dữ liệu backend; DSS
              hiện vẫn dùng dữ liệu mẫu
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="md:hidden flex gap-1">
              {nav.map(([k, , t]) => (
                <button
                  key={k}
                  className={"btn " + (page === k ? "btn-main" : "")}
                  onClick={() => {
                    setDssRoute(null);
                    setPage(k);
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
            {DEV && (
              <button
                className="btn"
                onClick={() => setSim({ error: !sim.error })}
              >
                {sim.error ? "Tắt lỗi giả lập" : "Giả lập lỗi"}
              </button>
            )}
          </div>
        </header>
        <div className="px-5 py-4 pb-8 max-w-[1400px] mx-auto">
          {page === "dashboard" && (
            <DashboardView
              year={year}
              setYear={setYear}
              sim={sim}
              goDss={goDss}
            />
          )}
          {page === "olap" && <OlapView sim={sim} />}
          {page === "dss" && (
            <DssView
              key={dssRoute || "-"}
              year={year}
              setYear={setYear}
              sim={sim}
              initRoute={dssRoute}
            />
          )}
        </div>
      </main>
    </div>
  );
}
