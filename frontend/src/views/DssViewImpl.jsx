import { useState } from "react";
import {
  byYear,
  routeStats,
  buildBrief,
  bench,
  attribution,
  p25cut,
  STAGES,
  simulate,
  bootCI,
  evid,
  LOW_SAMPLE,
} from "../data/mockData.jsx";
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

const BriefCard = ({ title, owner, note, children }) => (
  <section className="panel p-3 flex flex-col">
    <div className="font-semibold text-sm">{title}</div>
    <div className="text-[11px] text-slate-500 mb-1">Phụ trách: {owner}</div>
    {children}
    <p className="text-[11px] text-slate-500 mt-auto pt-2">{note}</p>
  </section>
);
const BriefRow = ({ main, sub, pill, onLog }) => (
  <div className="border-t border-slate-100 py-1.5 text-xs flex gap-2 justify-between">
    <div className="min-w-0">
      <div>
        <b>{main}</b> {pill}
      </div>
      <div className="text-slate-600">{sub}</div>
    </div>
    <button className="btn self-start shrink-0" onClick={onLog}>
      Ghi nhận
    </button>
  </div>
);
const NoItem = () => (
  <p className="text-xs text-slate-500 py-2">Không có mục nào đủ điều kiện.</p>
);
const ciTxt = (ci) => `CI 95%: ${num(ci.avLo, 0)}–${num(ci.avHi, 0)} đơn`;

export default function DssView({ year, setYear, sim, initRoute }) {
  const [sort, setSort] = useState("rate"),
    [sel, setSel] = useState(initRoute),
    [q, setQ] = useState(0.5),
    [cut, setCut] = useState({ appr: 0, prep: 0, transit: 0 }),
    [log, setLog] = useState([]);
  const { data, loading, error, retry } = useData(
    () => {
      const rows = byYear(year);
      return { rows, rs: routeStats(rows), brief: buildBrief(rows) };
    },
    [year],
    sim,
  );
  const rec = (g, l) =>
    setLog(
      [{ t: new Date().toLocaleTimeString("vi-VN"), g, l }, ...log].slice(
        0,
        50,
      ),
    );
  const head = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <YearSel year={year} setYear={setYear} />
      <p className="text-xs text-slate-500 max-w-3xl">
        Mọi số “tránh được” là mô phỏng theo luật trên dữ liệu mẫu, không phải
        tác động nhân quả và không thực thi hành động vận hành. Dữ liệu thật sẽ
        lấy từ API <code>/api/dss/*</code>.
      </p>
    </div>
  );
  if (error)
    return (
      <div className="space-y-3">
        {head}
        <Errored msg={error} retry={retry} />
      </div>
    );
  if (loading || !data)
    return (
      <div className="space-y-3">
        {head}
        <Skeleton h={260} />
        <Skeleton h={260} />
      </div>
    );
  const { rows, rs, brief } = data,
    { L, list } = rs;
  if (!list.length)
    return (
      <div className="space-y-3">
        {head}
        <Empty msg="Chưa có tuyến nào đủ số đơn để phân tích" />
      </div>
    );
  const ranked = [...list]
    .sort((a, b) => (sort === "rate" ? b.p - a.p : b.k - a.k))
    .slice(0, 10);
  const cur =
    list.find((s) => s.route === sel) || [...list].sort((a, b) => b.p - a.p)[0];
  const b = bench(rows, q),
    b25 = bench(rows, 0.25),
    att = attribution(cur.rows, b),
    cutDef = p25cut(cur.rows, b25);
  const mx = Object.fromEntries(
    STAGES.map(([k]) => [k, Math.ceil(Math.max(...cur.rows.map((r) => r[k])))]),
  );
  const c = Object.fromEntries(
      STAGES.map(([k]) => [k, Math.min(cut[k], mx[k])]),
    ),
    any = STAGES.some(([k]) => c[k] > 0);
  const after = simulate(cur.rows, c),
    avoided = cur.k - after,
    newRate = after / cur.n,
    ci = bootCI(cur.rows, c),
    [evT, evK] = evid(ci, cur.low);
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
                    (s.route === cur.route ? "pick" : "")
                  }
                  onClick={() => pick(s.route)}
                >
                  <td className="py-1.5 px-2 font-medium">
                    <button
                      className="text-left"
                      aria-pressed={s.route === cur.route}
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
                2. Giai đoạn nghẽn của tuyến {cur.route}
              </h2>
              <p className="text-xs text-slate-500">
                Tỷ trọng từng giai đoạn trong các đơn trễ của tuyến (Shapley
                trên 3 giai đoạn). Nhãn phân bổ mô tả, không phải kết luận nhân
                quả.
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
                Dựa trên {att.n} đơn trễ. Mỗi đơn so với phân vị q = {q} của
                từng giai đoạn trên toàn bộ dữ liệu đang xem.
              </p>
              {att.n < 10 && (
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
                Giả định 1 ngày rút ngắn = 1 ngày giao sớm hơn; mức rút của mỗi
                giai đoạn không vượt thời gian thực tế của đơn.
              </p>
            </div>
            <div className="flex gap-1">
              <button
                className="btn"
                onClick={() =>
                  setCut({
                    appr: Math.min(cutDef.appr, mx.appr),
                    prep: Math.min(cutDef.prep, mx.prep),
                    transit: Math.min(cutDef.transit, mx.transit),
                  })
                }
              >
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
                  max={mx[k]}
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
            {any ? (
              <>
                <div>
                  Tỷ lệ trễ: <b>{pct(cur.p)}</b> → <b>{pct(newRate)}</b>{" "}
                  <span className="text-slate-500">
                    (−{num((cur.p - newRate) * 100, 2)} điểm %, CI 95%: −
                    {num(ci.ppLo, 2)} đến −{num(ci.ppHi, 2)})
                  </span>
                </div>
                <div className="mt-1">
                  Ước tính tránh được <b>{avoided}</b> / {cur.k} đơn trễ{" "}
                  <span className="text-slate-500">({ciTxt(ci)})</span>{" "}
                  <Pill t={evT} c={ST[evK]} />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  CI từ bootstrap 300 lần (seed 42) chỉ phản ánh nhiễu lấy mẫu,
                  không chứng tỏ mục tiêu khả thi. CI chứa 0 thì kết luận là
                  “chưa đủ bằng chứng”.
                </p>
              </>
            ) : (
              <span className="text-slate-600">
                Kéo thanh trượt hoặc bấm “Đặt về mức P25” để xem ước tính cho
                tuyến {cur.route}.
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
              const [t, k] = evid(r.ci, r.low);
              return (
                <BriefRow
                  key={r.route}
                  main={r.route}
                  pill={<Pill t={t} c={ST[k]} />}
                  onLog={() => rec("Tuyến", r.route)}
                  sub={`Tránh ~${r.avoided}/${r.k} đơn trễ (${ciTxt(r.ci)}). Rút: duyệt ${num(r.cut.appr)} + chuẩn bị ${num(r.cut.prep)} + vận chuyển ${num(r.cut.transit)} ngày`}
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
              const [t, k] = evid(p.ci, p.low);
              return (
                <BriefRow
                  key={p.pay}
                  main={p.pay}
                  pill={<Pill t={t} c={ST[k]} />}
                  onLog={() => rec("Thanh toán", p.pay)}
                  sub={`Tránh ~${p.avoided} đơn trễ (${ciTxt(p.ci)}), rút duyệt ${num(p.cut)} ngày; ${int(p.n)} đơn`}
                />
              );
            })}
          </BriefCard>
          <BriefCard
            title="Chính sách cam kết (5 ô đầu, chỉ số ròng)"
            owner="Chủ chính sách cam kết giao hàng"
            note="Đổi định nghĩa trễ (cam kết = Q95 thời gian hoàn tất), không rút ngắn thời gian giao; chỉ hiển thị số ròng (NET). Cam kết quá dài không thực tế."
          >
            <p className="text-[11px] text-slate-600 pb-1">
              Ô tuyến: {brief.promCnt.tight} tight / {brief.promCnt.ok} ok /{" "}
              {brief.promCnt.loose} loose.
            </p>
            {brief.promTop.map((x) => (
              <BriefRow
                key={x.route}
                main={x.route}
                pill={x.need > 40 && <Pill t="Cam kết quá dài" c={ST.warn} />}
                onLog={() => rec("Chính sách cam kết", x.route)}
                sub={`Cam kết trung vị ${num(x.med)} → cần ${x.need} ngày: ròng +${x.net} đơn được phân loại lại là đúng hạn`}
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
                main={s.id}
                pill={
                  <Pill
                    t={s.prio ? "Ưu tiên" : "Chưa đủ bằng chứng"}
                    c={s.prio ? ST.ok : ST.warn}
                  />
                }
                onLog={() => rec("Người bán", s.id)}
                sub={`${s.k}/${s.n} đơn trễ (${pct(s.p)}), vượt mức hệ thống ~${num(s.excess, 0)} đơn`}
              />
            ))}
            {!brief.sellers.length && <NoItem />}
          </BriefCard>
          <BriefCard
            title="Cần thêm dữ liệu (tuyến gắn cờ, mẫu nhỏ)"
            owner="Quản lý vận hành logistics"
            note={`Tuyến đỏ/vàng nhưng dưới ${LOW_SAMPLE} đơn-tuyến; không tính là hành động ưu tiên chính. Thu thập thêm đơn rồi đánh giá lại.`}
          >
            {brief.more.map((s) => (
              <BriefRow
                key={s.route}
                main={s.route}
                pill={<Pill t={LV[s.level][0]} c={LV[s.level][1]} />}
                onLog={() => rec("Cần thêm dữ liệu", s.route)}
                sub={`${s.n} đơn, tỷ lệ trễ ${pct(s.p)}; cần thêm ít nhất ${LOW_SAMPLE - s.n} đơn`}
              />
            ))}
            {!brief.more.length && <NoItem />}
          </BriefCard>
          <section className="panel p-3">
            <div className="font-semibold text-sm">
              Nhật ký ghi nhận khuyến nghị
            </div>
            <p className="text-[11px] text-slate-500 mb-1">
              Chỉ ghi log, không thực thi hành động (sau này gửi POST
              /api/dss/actions).
            </p>
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
