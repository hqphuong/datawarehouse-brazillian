/* eslint-disable react-refresh/only-export-components */
/* Các thành phần dùng chung của DSS Action Center theo bản thiết kế 6 khối. */
import { useEffect, useRef, useState } from "react";
import { LV, Pill } from "../utils/utils.js";

export const BLOCKS = [
  ["route", "1", "Tuyến ưu tiên", "Route Priority", "Tuyến nào trễ nhiều một cách đáng tin cậy, cần xử lý trước?", "Quản lý vận hành logistics"],
  ["attr", "2", "Giai đoạn nghẽn", "Attribution", "Trong các đơn trễ của tuyến, giai đoạn nào chiếm tỷ trọng lớn?", "Quản lý vận hành, đơn vị vận chuyển"],
  ["cut", "3", "Mức rút ngắn", "Feasible cut", "Rút ngắn bao nhiêu ngày thì tránh được bao nhiêu đơn trễ?", "Quản lý vận hành logistics"],
  ["promise", "4", "Ngày cam kết", "Promise policy", "Ngày cam kết hiện tại có phù hợp không?", "Chủ chính sách cam kết giao hàng"],
  ["seller", "5", "Người bán", "Seller scorecard", "Người bán nào cần được can thiệp?", "Bộ phận hỗ trợ người bán"],
  ["brief", "6", "Tổng hợp hành động", "Decision Brief", "Gom lại thành năm nhóm hành động, mỗi nhóm có người phụ trách.", "Tất cả"],
];
export const META = Object.fromEntries(BLOCKS.map((b) => [b[0], b]));

export const SG = {
  "ưu tiên": ["Ưu tiên", "bg-orange-100 text-orange-900"],
  "ổn định": ["Ổn định", "bg-teal-50 text-teal-900"],
  "cần thêm dữ liệu": ["Cần thêm dữ liệu", "bg-slate-100 text-slate-700"],
};
export const PS = {
  tight: ["Cam kết chặt", "bg-amber-100 text-amber-900"],
  ok: ["Phù hợp", "bg-teal-50 text-teal-900"],
  loose: ["Cam kết rộng", "bg-slate-100 text-slate-700"],
};

export const Badge = ({ n }) => (
  <span
    className="shrink-0 w-6 h-6 rounded-full bg-teal-700 text-white text-xs font-semibold grid place-items-center"
    aria-hidden="true"
  >
    {n}
  </span>
);

export const Block = ({ id, aside, children }) => {
  const [, n, title] = META[id];
  return (
    <section id={"dss-" + id} className="panel p-4 scroll-mt-28" aria-labelledby={"h-" + id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex gap-3 min-w-0 items-center">
          <Badge n={n} />
          <h2 id={"h-" + id} className="font-semibold leading-tight">{title}</h2>
        </div>
        {aside && <div className="flex flex-wrap items-center gap-1">{aside}</div>}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
};

export const Takeaway = ({ children }) => (
  <p className="text-sm bg-teal-50 border border-teal-100 rounded px-3 py-2 mb-3">{children}</p>
);
export const Note = ({ children }) => <p className="text-[11px] text-slate-500 mt-2">{children}</p>;
export const NoItem = () => <p className="text-xs text-slate-500 py-2">Không có mục nào đủ điều kiện.</p>;
export const KV = ({ k, children }) => (
  <div className="flex items-center justify-between gap-3 py-1.5 border-b border-slate-100 text-sm">
    <span className="text-slate-600">{k}</span><b>{children}</b>
  </div>
);
export const InlineError = ({ msg, retry }) => (
  <p className="text-xs text-red-700 bg-red-50 rounded px-2 py-1" role="alert">
    {msg}. <button className="underline" onClick={retry}>Tải lại</button>
  </p>
);
export const Status = ({ level }) => {
  const [text, color] = LV[level] || LV.none;
  return <Pill t={text} c={color} />;
};

/* Thanh tỷ trọng có dấu: mốc 0 ở giữa, φ âm vẽ sang trái. */
export function SignedBar({ v, max, color }) {
  const w = max > 0 ? Math.min(Math.abs(v || 0) / max, 1) * 50 : 0;
  return (
    <div className="relative h-3 bg-slate-100 rounded-sm" aria-hidden="true">
      <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300" />
      <div
        className="absolute inset-y-0 rounded-sm"
        style={v >= 0 ? { left: "50%", width: w + "%", background: color } : { right: "50%", width: w + "%", background: color }}
      />
    </div>
  );
}

export const TIPS = {
  ci: "Khoảng tin cậy 95% do API tính (Wilson). Tuyến không gắn cờ không có khoảng tin cậy trong /routes.",
  net: "Ròng = đơn chuyển sang đúng hạn trừ đơn trễ mới phát sinh.",
  review: "Tỷ lệ đơn có review ≤ 2 sao (API: bad_review_rate).",
};

/* Tooltip 1 dòng, fixed để không bị vùng cuộn cắt; mở được bằng focus bàn phím. */
export function Tip({ t, children }) {
  const [pos, setPos] = useState(null);
  const ref = useRef(null);
  const show = () => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    setPos({
      x: Math.min(Math.max(r.left + r.width / 2, 130), window.innerWidth - 130),
      y: r.bottom + 6,
    });
  };
  return (
    <span
      ref={ref}
      tabIndex={0}
      className="border-b border-dotted border-slate-400 cursor-help"
      onMouseEnter={show}
      onMouseLeave={() => setPos(null)}
      onFocus={show}
      onBlur={() => setPos(null)}
      onKeyDown={(e) => { if (e.key === "Escape") setPos(null); }}
    >
      {children}
      <span className="sr-only"> ({t})</span>
      {pos && (
        <span
          aria-hidden="true"
          style={{ position: "fixed", left: pos.x, top: pos.y, transform: "translateX(-50%)", maxWidth: 250 }}
          className="z-50 bg-slate-900 text-white text-[11px] font-normal leading-snug rounded px-2 py-1 shadow-lg"
        >
          {t}
        </span>
      )}
    </span>
  );
}

/* Popover đóng bằng Esc hoặc bấm ra ngoài. */
export function Pop({ label, children, w = "w-80" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const outside = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const escape = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button className="btn" aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen(!open)}>{label}</button>
      {open && (
        <div role="dialog" aria-label={label} className={"absolute right-0 mt-1 z-50 panel shadow-lg p-3 max-w-[92vw] " + w}>
          {children}
        </div>
      )}
    </div>
  );
}

export function CopyBtn({ text, label = "mã người bán" }) {
  const [done, setDone] = useState(false);
  const copy = async (e) => {
    e.stopPropagation();
    const value = String(text);
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); } catch { /* clipboard không sẵn */ }
      document.body.removeChild(area);
    }
    setDone(true);
    setTimeout(() => setDone(false), 1500);
  };
  return (
    <button
      type="button"
      className="btn ml-1 !px-1.5 !py-0 text-[11px] align-middle"
      onClick={copy}
      title={"Sao chép " + label + " đầy đủ"}
      aria-label={"Sao chép " + label}
    >
      {done ? "Đã chép ✓" : "Chép"}
    </button>
  );
}

/* Mỗi dòng Decision Brief: xem chi tiết + ghi nhận (chỉ ghi log).
 * Mục đã ghi nhận biến mất khỏi Brief, chỉ còn trong popup "Đã ghi nhận". */
export function BriefList({ rows, done, onRec, onView, busy = false }) {
  const visible = rows.filter((r) => !done(r));
  if (!visible.length) {
    return rows.length ? (
      <p className="text-xs text-slate-500 py-2">Đã ghi nhận hết các mục của nhóm này.</p>
    ) : (
      <NoItem />
    );
  }
  return (
    <>
      {visible.map((r) => (
        <div key={r.key} className="border-t border-slate-100 py-2 text-xs flex gap-2 items-start">
          {r.view ? (
            <button
              className="text-left min-w-0 flex-1 rounded hover:bg-slate-50"
              onClick={() => onView(r.view)}
              title="Bấm để xem chi tiết"
            >
              <div><b title={r.full}>{r.main}</b> {r.pill}</div>
              <div className="text-slate-600">{r.sub}</div>
            </button>
          ) : (
            <div className="min-w-0 flex-1">
              <div><b title={r.full}>{r.main}</b> {r.pill}</div>
              <div className="text-slate-600">{r.sub}</div>
            </div>
          )}
          {r.copy && <CopyBtn text={r.copy} />}
          <button
            className="btn shrink-0"
            disabled={busy}
            title="Chỉ ghi log, không thực thi"
            onClick={() => onRec(r)}
          >
            Ghi nhận khuyến nghị
          </button>
        </div>
      ))}
    </>
  );
}

export function BriefGroup({ title, owner, src, children }) {
  return (
    <section className="panel p-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-sm">{title}</h3>
        <button
          className="text-[11px] text-teal-800 underline shrink-0"
          onClick={() => document.getElementById("dss-" + src)?.scrollIntoView({ behavior: "smooth", block: "start" })}
        >
          Từ khối {META[src][1]}
        </button>
      </div>
      <div className="text-[11px] text-slate-500 mb-1" title={owner}>Phụ trách: {owner}</div>
      {children}
    </section>
  );
}
