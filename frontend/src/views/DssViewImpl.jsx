import { useState } from "react";
import {
  getDssBrief,
  getDssRoutes,
  getDssAttribution,
  getDssScenario,
  postDssAction,
} from "../data/api.js";
import {
  mapAttribution,
  mapBrief,
  mapDefaultCut,
  mapLateByRoute,
  mapRoutes,
  mapScenario,
} from "../data/dssAdapter.js";
import {
  pct,
  num,
  int,
  useData,
  YearSel,
  Errored,
  Skeleton,
  Empty,
  Pill,
  ST,
  LV,
  flagsOf,
} from "../utils/utils.js";

const STAGES = [
  ["appr", "Duyệt thanh toán"],
  ["prep", "Người bán chuẩn bị"],
  ["transit", "Vận chuyển"],
];
// Backend chặn mức cắt theo thời gian thực tế của từng đơn (np.minimum).
const MAX_CUT = { appr: 10, prep: 15, transit: 30 };

const BriefCard = ({ title, owner, note, children }) => (
  <section className="panel p-3 flex flex-col">
    <div className="font-semibold text-sm">{title}</div>
    <div className="text-[11px] text-slate-500 mb-1">Phụ trách: {owner}</div>
    {children}
    <p className="text-[11px] text-slate-500 mt-auto pt-2">{note}</p>
  </section>
);
const BriefRow = ({ main, sub, pill, onLog, saving }) => (
  <div className="border-t border-slate-100 py-1.5 text-xs flex gap-2 justify-between">
    <div className="min-w-0">
      <div>
        <b>{main}</b> {pill}
      </div>
      <div className="text-slate-600">{sub}</div>
    </div>
    <button
      className="btn self-start shrink-0"
      onClick={onLog}
      disabled={saving}
    >
      {saving ? "Đang lưu…" : "Ghi nhận"}
    </button>
  </div>
);
const NoItem = () => (
  <p className="text-xs text-slate-500 py-2">Không có mục nào đủ điều kiện.</p>
);
const ciTxt = (ci) => `CI 95%: ${num(ci.avLo, 0)}–${num(ci.avHi, 0)} đơn`;
const evidenceOf = (ci, low) =>
  low
    ? ["Cần thêm dữ liệu", "more"]
    : ci && ci.avLo > 0
      ? ["Ước lượng ổn định", "ok"]
      : ["Chưa đủ bằng chứng", "warn"];

export default function DssView({ year, setYear, sim, initRoute }) {
  const [sort, setSort] = useState("rate"),
    [sel, setSel] = useState(initRoute),
    [q, setQ] = useState(0.5),
    [cut, setCut] = useState({ appr: 0, prep: 0, transit: 0 }),
    [log, setLog] = useState([]),
    [saving, setSaving] = useState(""),
    [actionError, setActionError] = useState("");

  const {
    data: base,
    loading: baseLoading,
    error: baseError,
    retry: retryBase,
  } = useData(
    async (signal) => {
      const [routesRaw, briefRaw] = await Promise.all([
        getDssRoutes(year, 50, signal),
        getDssBrief(year, signal),
      ]);
      return {
        rs: mapRoutes(routesRaw, briefRaw.config?.base_rate),
        briefRaw,
      };
    },
    [year],
    sim,
  );

  const {
    data: attData,
    loading: attLoading,
    error: attError,
    retry: retryAtt,
  } = useData(
    async (signal) => {
      if (q === 0.25) {
        const only = await getDssAttribution(year, 0.25, signal);
        return { current: only, p25: only };
      }
      const [current, p25] = await Promise.all([
        getDssAttribution(year, 0.5, signal),
        getDssAttribution(year, 0.25, signal),
      ]);
      return { current, p25 };
    },
    [year, q],
    sim,
  );

  const list = base?.rs.list || [];
  const cur =
    list.find((s) => s.route === sel) ||
    [...list].sort((a, b) => b.p - a.p)[0] ||
    null;
  const c = Object.fromEntries(
    STAGES.map(([k]) => [k, Math.min(cut[k], MAX_CUT[k])]),
  );
  const any = STAGES.some(([k]) => c[k] > 0);

  const {
    data: scenario,
    loading: scenarioLoading,
    error: scenarioError,
    retry: retryScenario,
  } = useData(
    async (signal) => {
      if (!cur) return null;
      return mapScenario(
        await getDssScenario({ year, route: cur.route, cut: c }, signal),
      );
    },
    [year, cur?.route, c.appr, c.prep, c.transit],
    sim,
  );

  const rec = (g, l) =>
    setLog(
      [{ t: new Date().toLocaleTimeString("vi-VN"), g, l }, ...log].slice(0, 50),
    );
  const saveKey = (action, label) => `${action}:${label}`;
  const ack = async (action, label, extra = {}) => {
    const key = saveKey(action, label);
    setSaving(key);
    setActionError("");
    try {
      await postDssAction({ action, label: String(label), ...extra });
      rec(action, label);
    } catch (e) {
      setActionError(e?.message || "Không ghi được hành động.");
    } finally {
      setSaving("");
    }
  };
  const head = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <YearSel year={year} setYear={setYear} />
      <p className="text-xs text-slate-500 max-w-3xl">
        Mọi số “tránh được” là mô phỏng theo luật DSS trên dữ liệu thực, không
        phải tác động nhân quả và không thực thi hành động vận hành.
      </p>
    </div>
  );
  const error = baseError || attError;
  if (error)
    return (
      <div className="space-y-3">
        {head}
        <Errored
          msg={error}
          retry={() => {
            retryBase();
            retryAtt();
          }}
        />
      </div>
    );
  if (baseLoading || attLoading || !base || !attData)
    return (
      <div className="space-y-3">
        {head}
        <Skeleton h={260} />
        <Skeleton h={260} />
      </div>
    );
  if (!list.length)
    return (
      <div className="space-y-3">
        {head}
        <Empty msg="Chưa có tuyến nào đủ số đơn để phân tích" />
      </div>
    );

  const { L } = base.rs;
  const brief = mapBrief(base.briefRaw, mapLateByRoute(attData.current));
  const ranked = [...list]
    .sort((a, b) => (sort === "rate" ? b.p - a.p : b.k - a.k))
    .slice(0, 10);
  const att = cur ? mapAttribution(attData.current, cur.route) : null;
  const cutDef = cur
    ? mapDefaultCut(attData.p25, cur.route)
    : { appr: 0, prep: 0, transit: 0 };
  const pick = (r) => {
    setSel(r);
    setCut({ appr: 0, prep: 0, transit: 0 });
  };
  const shares = att
    ? [
        ["Duyệt thanh toán", att.appr, "#94a3b8"],
        ["Người bán chuẩn bị", att.prep, "#0f766e"],
        ["Vận chuyển", att.transit, "#b45309"],
        ["Chưa giải thích được (liên quan ngày cam kết)", att.resid, "#64748b"],
      ]
    : [];

  return (
    <div className="space-y-4">
      {head}
      <section className="panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold">1. Chọn tuyến ưu tiên</h2>
            <p className="text-xs text-slate-500">
              Tỷ lệ trễ chung L = {pct(L)}. Đỏ: ≥ 2,0×L = {pct(2 * L)}; vàng: ≥
              1,5×L = {pct(1.5 * L)}. “Chưa chắc chắn”: cận dưới Wilson 95% thấp
              hơn ngưỡng của mức đó.
            </p>
          </div>
          <div className="flex gap-1">
            {[
              ["rate", "Xếp theo tỷ lệ trễ"],
              ["count", "Xếp theo số đơn trễ"],
            ].map(([k, t]) => (
              <button
                key={k}
                className={"btn " + (sort === k ? "btn-main" : "")}
                onClick={() => setSort(k)}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-xs">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-1 px-2">Tuyến</th>
                <th className="text-right px-2">Đơn</th>
                <th className="text-right px-2">Trễ</th>
                <th className="text-right px-2">Tỷ lệ</th>
                <th className="text-right px-2">CI Wilson 95%</th>
                <th className="px-2">Mức</th>
                <th className="px-2">Cảnh báo</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((s) => (
                <tr
                  key={s.route}
                  className={
                    "border-t border-slate-100 cursor-pointer hover:bg-slate-50 " +
                    (cur && s.route === cur.route ? "pick" : "")
                  }
                  onClick={() => pick(s.route)}
                >
                  <td className="py-1.5 px-2 font-medium">
                    <button
                      className="text-left"
                      aria-pressed={!!cur && s.route === cur.route}
                    >
                      {s.route}
                    </button>
                  </td>
                  <td className="text-right px-2">{int(s.n)}</td>
                  <td className="text-right px-2">{int(s.k)}</td>
                  <td className="text-right px-2 font-semibold">{pct(s.p)}</td>
                  <td className="text-right px-2 text-slate-600">
                    {pct(s.lo)} – {pct(s.hi)}
                  </td>
                  <td className="px-2">
                    <Pill t={LV[s.level][0]} c={LV[s.level][1]} />
                  </td>
                  <td className="px-2">{flagsOf(s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-500 mt-2">
          Hai cách xếp hạng (theo tỷ lệ, theo số đơn) có thể cho kết quả khác
          nhau; danh sách là gợi ý ưu tiên, không phải ranh giới cứng.
        </p>
      </section>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <section className="panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold">
                2. Giai đoạn nghẽn của tuyến {cur?.route}
              </h2>
              <p className="text-xs text-slate-500">
                Tỷ trọng từng giai đoạn trong các đơn trễ của tuyến (Shapley
                trên 3 giai đoạn, peer group theo q). Nhãn phân bổ mô tả, không
                phải kết luận nhân quả.
              </p>
            </div>
            <div className="flex gap-1">
              {[
                [0.5, "q = 0,5"],
                [0.25, "q = 0,25"],
              ].map(([v, t]) => (
                <button
                  key={v}
                  className={"btn " + (q === v ? "btn-main" : "")}
                  onClick={() => setQ(v)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          {att ? (
            <div className="mt-3 space-y-2">
              {shares.map(([t, v, col]) => (
                <div key={t}>
                  <div className="flex justify-between text-xs">
                    <span>{t}</span>
                    <b>{pct(v)}</b>
                  </div>
                  <div className="h-3 bg-slate-100 rounded-sm">
                    <div
                      className="h-3 rounded-sm"
                      style={{
                        width: Math.max(0, v * 100) + "%",
                        background: col,
                      }}
                    />
                  </div>
                </div>
              ))}
              <p className="text-[11px] text-slate-500">
                Dựa trên {int(att.n)} đơn trễ. Tỷ trọng phân rã theo peer group
                tại q = {q}.
              </p>
              {att.n > 0 && att.n < 10 && (
                <p
                  className="text-xs text-amber-800 bg-amber-50 rounded px-2 py-1"
                  role="status"
                >
                  Tuyến có rất ít đơn trễ nên tỷ trọng kém tin cậy.
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-600 mt-3">
              Tuyến này không có đơn trễ.
            </p>
          )}
        </section>
        <section className="panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="font-semibold">
                3. Thử kịch bản rút ngắn (What-if)
              </h2>
              <p className="text-xs text-slate-500">
                Giả định 1 ngày rút ngắn = 1 ngày giao sớm hơn; backend chặn mức
                rút theo thời gian thực tế của từng đơn.
              </p>
            </div>
            <div className="flex gap-1">
              <button className="btn" onClick={() => setCut(cutDef)}>
                Đặt về mức P25
              </button>
              <button
                className="btn"
                onClick={() => setCut({ appr: 0, prep: 0, transit: 0 })}
              >
                Xoá
              </button>
            </div>
          </div>
          <div className="mt-2 space-y-1.5">
            {STAGES.map(([k, t]) => (
              <label key={k} className="flex items-center gap-3 text-xs">
                <span className="w-36">{t}</span>
                <input
                  type="range"
                  min="0"
                  max={MAX_CUT[k]}
                  step="0.1"
                  value={c[k]}
                  onChange={(e) => setCut({ ...cut, [k]: +e.target.value })}
                  className="flex-1"
                  aria-label={"Rút ngắn " + t}
                />
                <b className="w-16 text-right">−{num(c[k])} ngày</b>
              </label>
            ))}
          </div>
          <div className="mt-3 bg-slate-50 rounded p-3 text-sm">
            {scenarioError ? (
              <div className="text-xs">
                <span className="text-red-700">Không tính được kịch bản. </span>
                <button className="btn" onClick={retryScenario}>
                  Thử lại
                </button>
              </div>
            ) : scenarioLoading || !scenario ? (
              <span className="text-slate-600">Đang tính kịch bản…</span>
            ) : any ? (
              <>
                <div>
                  Tỷ lệ trễ: <b>{pct(scenario.baseline)}</b> →{" "}
                  <b>{pct(scenario.projected)}</b>
                </div>
                <div className="mt-1">
                  Ước tính tránh được <b>{int(scenario.avoided)}</b> /{" "}
                  {int(cur?.k || 0)} đơn trễ
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  Kịch bản tuỳ ý không có CI bootstrap; CI chỉ có trong Decision
                  Brief cho 5 tuyến đầu.
                </p>
              </>
            ) : (
              <span className="text-slate-600">
                Kéo thanh trượt hoặc bấm “Đặt về mức P25” để xem ước tính cho
                tuyến {cur?.route}.
              </span>
            )}
          </div>
        </section>
      </div>
      <section className="space-y-2">
        <div>
          <h2 className="font-semibold">4. Decision Brief</h2>
          <p className="text-xs text-slate-500">
            Năm nhóm hành động tách biệt, cùng chồng lấn trên các đơn trễ nên{" "}
            <b>không cộng số giữa các nhóm</b>. Mỗi tổng chỉ áp dụng cho các mục
            trong nhóm đó.
          </p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
          <BriefCard
            title="Tuyến (5 tuyến đầu, mức P25)"
            owner="Quản lý vận hành logistics"
            note="Nếu đưa cả ba giai đoạn về P25 toàn cục thì ước tính tránh được số đơn trễ như trên. Tuyến mẫu nhỏ nằm ở nhóm “Cần thêm dữ liệu”."
          >
            {brief.routes.map((r) => {
              const [t, k] = evidenceOf(r.ci, false);
              return (
                <BriefRow
                  key={r.route}
                  main={r.route}
                  pill={<Pill t={t} c={ST[k]} />}
                  onLog={() =>
                    ack("ack_route", r.route, {
                      route: r.route,
                      avoided_orders: r.avoided,
                    })
                  }
                  saving={saving === saveKey("ack_route", r.route)}
                  sub={`Tránh ~${int(r.avoided)}${r.k != null ? `/${int(r.k)}` : ""} đơn trễ (${ciTxt(r.ci)})`}
                />
              );
            })}
            {!brief.routes.length && <NoItem />}
          </BriefCard>
          <BriefCard
            title="Thanh toán (chỉ cắt giai đoạn duyệt)"
            owner="Hệ thống thanh toán / sàn"
            note="Chỉ rút giai đoạn duyệt thanh toán về P25; thường nhỏ so với vận chuyển."
          >
            {brief.pay.map((p) => {
              const [t, k] = evidenceOf(p.ci, false);
              return (
                <BriefRow
                  key={p.pay}
                  main={p.pay}
                  pill={<Pill t={t} c={ST[k]} />}
                  onLog={() =>
                    ack("ack_payment", p.pay, {
                      payment_type: p.pay,
                      avoided_orders: p.avoided,
                    })
                  }
                  saving={saving === saveKey("ack_payment", p.pay)}
                  sub={`Tránh ~${int(p.avoided)} đơn trễ (${ciTxt(p.ci)})`}
                />
              );
            })}
            {!brief.pay.length && <NoItem />}
          </BriefCard>
          <BriefCard
            title="Chính sách cam kết (5 ô đầu, chỉ số ròng)"
            owner="Chủ chính sách cam kết giao hàng"
            note="Đổi định nghĩa trễ (cam kết = Q95 thời gian hoàn tất), không rút ngắn thời gian giao; chỉ hiển thị số ròng (NET). Cam kết quá dài không thực tế."
          >
            <p className="text-[11px] text-slate-600 pb-1">
              Trong các ô hiển thị: {brief.promCnt.tight} tight /{" "}
              {brief.promCnt.ok} ok / {brief.promCnt.loose} loose.
            </p>
            {brief.promTop.map((x) => (
              <BriefRow
                key={x.route}
                main={x.route}
                pill={x.need > 40 && <Pill t="Cam kết quá dài" c={ST.warn} />}
                onLog={() =>
                  ack("ack_promise", x.route, {
                    route: x.route,
                    needed_days: x.need,
                    net_avoided_orders: x.net,
                  })
                }
                saving={saving === saveKey("ack_promise", x.route)}
                sub={`Cần ${x.need} ngày: ròng +${int(x.net)} đơn được phân loại lại là đúng hạn`}
              />
            ))}
            {!brief.promTop.length && <NoItem />}
          </BriefCard>
          <BriefCard
            title="Người bán (5 người đầu, chỉ là liên hệ)"
            owner="Bộ phận hỗ trợ người bán"
            note="Số đơn trễ vượt tỷ lệ hệ thống, không phải số đơn tránh được; chưa hiệu chỉnh theo cơ cấu tuyến của từng người bán."
          >
            {brief.sellers.map((s) => (
              <BriefRow
                key={s.id}
                main={s.id.slice(0, 8)}
                pill={
                  <Pill
                    t={s.prio ? "Ưu tiên" : "Chưa đủ bằng chứng"}
                    c={s.prio ? ST.ok : ST.warn}
                  />
                }
                onLog={() =>
                  ack("ack_seller", s.id, { seller_id: s.id })
                }
                saving={saving === saveKey("ack_seller", s.id)}
                sub={`${int(s.k)}/${int(s.n)} đơn trễ (${pct(s.p)}), vượt mức hệ thống ~${num(s.excess, 0)} đơn`}
              />
            ))}
            {!brief.sellers.length && <NoItem />}
          </BriefCard>
          <BriefCard
            title="Cần thêm dữ liệu (tuyến gắn cờ, mẫu nhỏ)"
            owner="Quản lý vận hành logistics"
            note="Tuyến đỏ/vàng nhưng dưới ngưỡng số đơn tối thiểu; không tính là hành động ưu tiên chính. Thu thập thêm đơn rồi đánh giá lại."
          >
            {brief.more.map((s) => (
              <BriefRow
                key={s.route}
                main={s.route}
                pill={<Pill t={LV[s.level][0]} c={LV[s.level][1]} />}
                onLog={() =>
                  ack("ack_low_sample", s.route, {
                    route: s.route,
                    needed_orders: s.need,
                    level: s.level,
                  })
                }
                saving={saving === saveKey("ack_low_sample", s.route)}
                sub={`${int(s.n)} đơn, tỷ lệ trễ ${pct(s.p)}; cần thêm ${int(s.need)} đơn`}
              />
            ))}
            {!brief.more.length && <NoItem />}
          </BriefCard>
          <section className="panel p-3">
            <div className="font-semibold text-sm">
              Nhật ký ghi nhận khuyến nghị
            </div>
            <p className="text-[11px] text-slate-500 mb-1">
              Ghi nhận được lưu vào nhật ký hệ thống; log local chỉ để theo dõi
              phiên này, không thực thi hành động vận hành.
            </p>
            {actionError && (
              <p className="text-xs text-red-700 mb-1" role="alert">
                {actionError}
              </p>
            )}
            {log.length ? (
              <ul className="text-xs max-h-48 overflow-y-auto">
                {log.map((l, i) => (
                  <li key={i} className="border-t border-slate-100 py-1">
                    <span className="text-slate-500">{l.t}</span> · {l.g}:{" "}
                    <b>{l.l}</b>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500 py-2">
                Chưa có ghi nhận nào.
              </p>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}

/* ============ KHUNG ỨNG DỤNG ============ */
