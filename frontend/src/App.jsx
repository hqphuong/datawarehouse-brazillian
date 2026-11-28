import { useEffect, useState } from "react";
import "./App.css";
import DashboardView from "./views/DashboardView.js";
import OlapView from "./views/OlapView.js";
import DssView from "./views/DssView.js";
import { DEV } from "./utils/utils.js";
import LoginView from "./components/LoginView.jsx";
import {
  getAuthSession,
  postAuthLogin,
  postAuthLogout,
} from "./data/api.js";
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
    [dssRoute, setDssRoute] = useState(null),
    [username, setUsername] = useState(null),
    [authChecking, setAuthChecking] = useState(true),
    [authError, setAuthError] = useState(""),
    [authAttempt, setAuthAttempt] = useState(0),
    [logoutPending, setLogoutPending] = useState(false),
    [logoutError, setLogoutError] = useState("");
  useEffect(() => {
    let active = true;
    getAuthSession()
      .then((result) => {
        if (!active) return;
        setUsername(result.authenticated ? result.username : null);
        setAuthError("");
      })
      .catch((error) => {
        if (active) setAuthError(error.message);
      })
      .finally(() => {
        if (active) setAuthChecking(false);
      });
    return () => {
      active = false;
    };
  }, [authAttempt]);

  const handleLogin = async (loginUsername, password) => {
    const result = await postAuthLogin(loginUsername, password);
    setUsername(result.username);
    setLogoutError("");
    setPage("dashboard");
  };

  const handleLogout = async () => {
    setLogoutError("");
    setLogoutPending(true);
    try {
      await postAuthLogout();
      setUsername(null);
      setDssRoute(null);
      setPage("dashboard");
    } catch (error) {
      setLogoutError(error.message || "Logout failed. Please try again.");
    } finally {
      setLogoutPending(false);
    }
  };

  if (authChecking) {
    return (
      <main
        className="min-h-screen flex items-center justify-center bg-[#f8fafc] p-4"
        aria-busy="true"
      >
        <div className="panel px-6 py-4 text-sm text-slate-600">
          Checking login session...
        </div>
      </main>
    );
  }
  if (authError) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-[#f8fafc] p-4">
        <section className="panel w-full max-w-md space-y-3 p-6 text-center">
          <h1 className="font-semibold text-slate-900">
            Authentication service unavailable
          </h1>
          <p className="text-sm text-red-800" role="alert">
            {authError}
          </p>
          <button
            className="btn btn-main"
            onClick={() => {
              setAuthError("");
              setAuthChecking(true);
              setAuthAttempt((attempt) => attempt + 1);
            }}
          >
            Retry
          </button>
        </section>
      </main>
    );
  }
  if (!username) return <LoginView onLogin={handleLogin} />;

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
          <div className="mt-auto p-2 border-t border-white/10">
            <div className="truncate px-3 pb-1 text-[11px] text-slate-400" title={username}>
              {username}
            </div>
            {logoutError && (
              <p className="px-3 pb-1 text-[11px] text-red-300" role="alert">
                {logoutError}
              </p>
            )}
            <button
              onClick={handleLogout}
              disabled={logoutPending}
              className="w-full flex items-center gap-3 px-3 py-2 rounded text-xs text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors text-left"
              title="Đăng xuất khỏi hệ thống"
            >
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"></path>
              </svg>
              <span>{logoutPending ? "Đang đăng xuất..." : "Đăng xuất"}</span>
            </button>
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