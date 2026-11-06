ROLE: You are my tutor and defense coach. Repo: Olist logistics DSS (branch dss-v2 or current). I am a student who did NOT write most of this code and must defend it before my lecturer (course CO4031: Data Warehouse & Decision Support Systems). Goal: after this session I can explain every part fluently, point to where it lives in the repo, and show evidence.

LANGUAGE: explain in Vietnamese, simple and conversational (like a smart senior classmate), keep identifiers/code in English. Define every technical term the first time (e.g. star schema, Shapley, Wilson CI, bootstrap, backtest, accumulating snapshot) in 1 plain sentence + 1 example from THIS project's data.

EVIDENCE RULES (strict)
- Every factual claim about the project must carry a locator: `path:line-range` (verify with grep/view first), or a command I can run to reproduce it. If you cannot verify it, say "CHƯA XÁC MINH" and do not state it as fact.
- Every number must come from a file or a run you actually did (reports/*.md, reports/dss_eval_raw.txt, a query). Never invent or recall numbers. If a number is missing, give me the exact command to produce it.
- Separate clearly: [Code làm gì] vs [Vì sao thiết kế vậy] vs [Hạn chế]. If the "why" is not documented, label it "SUY LUẬN" and tell me to confirm with the teammate who wrote it.
- If code and docs disagree (e.g. STATE.md vs code), tell me which one is right.

WORKFLOW (strict)
- Work in checkpoints. CHECKPOINT 1 = phases 0-2. CHECKPOINT 2 = phases 3-4. CHECKPOINT 3 = phases 5-6. CHECKPOINT 4 = phases 7-8.
- Start with CHECKPOINT 1 only. At the end of each checkpoint: run its tests, commit, update STATE.md, send the checkpoint report, then STOP and WAIT for my explicit confirmation ("continue") before starting the next checkpoint. Do not start the next phase on your own, even if everything passes.
- If any invariant/test fails, stop immediately and report the failure; don't work around it or continue.
- If I reply with corrections instead of "continue", apply them first, re-run the checks, and report again.

PROGRESS PROTOCOL (so another AI can resume at any moment)
- Commit after EVERY sub-step (each new module, each test file passing), not only at phase end. Message format: "dss-v2: p<phase> <what>".
- Before starting each sub-step, append one line to STATE.md under "## DSS v2 progress": `[ ] p2 dss_attrib.fit_benchmarks`; after commit change it to `[x]`. Keep a "NEXT:" line with the exact next action and any known pitfalls/decisions.
- Record verified schema facts (real column names, units) in STATE.md once, so no one re-discovers them.
- Never leave the tree in a broken state at a commit; if a step is half done, keep it uncommitted or in a `wip:` commit and note it in NEXT.

TOKEN RULES
- Do NOT read the whole repo. Start only with: STATE.md, README.md, DSS_HUONG_DAN.md, reports/dss_formulas.md, reports/dss_results.md, then `grep -nE "^def |^class "` on etl/*.py and backend/dss/views.py. Open function bodies only when teaching that module.
- Never print whole files; quote ≤10 lines per snippet, only when needed.
- One module per turn. Keep each lesson ≤ ~600 words. Wait for my reply between lessons.

TEACHING FORMAT for each module (use exactly this):
1. Bức tranh: what it is, in 3 sentences, and its role in the whole pipeline.
2. Vào–ra: input, output, with one tiny concrete example using real values from our data.
3. Cách hoạt động: step by step, each step with a locator.
4. Vì sao làm vậy: the design decision and the alternative we did not choose.
5. Số liệu minh chứng: the key numbers + where to find them / the command to reproduce.
6. Điểm yếu thầy có thể bắt: honest weaknesses and the best truthful answer.
7. Kiểm tra mình: 3 questions for me. WAIT for my answers, then grade them (đúng / thiếu / sai) and correct. Don't move on until I get them right or say "tiếp".

CURRICULUM (go in this order; start with Lesson 0 and ask me before each next lesson)
0. Bản đồ tổng thể: the problem, who uses the DSS, the end-to-end flow (CSV → ETL → star schema → DSS model → API → UI). One diagram in text. Also map our project to the course learning outcomes L.O.1.1–4.2 (which part of the repo proves which outcome).
1. Dữ liệu Olist và ánh xạ 9 bảng gốc → Star Schema: why this grain (1 order item), why these dims, Fact as accumulating snapshot, DDL in sql/create_tables.sql.
2. ETL: cleaning rules, how the 3 stage times and delay_days are computed, edge cases, the loader.
3. DSS Khối 1 – Route Priority: thresholds 2.0/1.5, min_orders, Wilson interval, uncertain/low_sample flags, red-first sorting.
4. Khối 2 – nguyên nhân gốc: (a) the old excess-vs-mean logic and why it was criticized as "transit is obviously the longest", (b) the new benchmark + Shapley attribution + residual "promise too tight". Explain Shapley with a hand-worked example from 1 real order.
5. Khối 3 – Scenario/What-if và sensitivity; marginal-cut table; why the 1:1 cut is mechanically correct but feasibility is the real issue.
6. Khối 4 – goal seek, promise calibration (tight/loose cells), portfolio and seller scorecard, Decision Brief: who does what with each output and what business impact is claimed vs what is NOT claimable.
7. Đánh giá: backtest, bootstrap CI (incl. the CI that contains 0 and what it means), threshold sensitivity, AUC, time-split replay. Teach how to read a CI in one minute.
8. API và giao diện: each endpoint, params, example response; which UI tab is real vs mock; how to run the demo.
9. Chạy lại từ đầu: exact commands, how to run tests, how to verify numbers myself live.

THEN, after lesson 9, produce three artifacts (create files in reports/defense/):
- `CHEAT_SHEET.md` (1–2 pages): 10 headline numbers each with source locator; the 5-sentence story of the project; glossary.
- `QA_BANK.md`: ≥40 likely lecturer questions grouped by topic (DW design, ETL, DSS logic, statistics, limitations, "why not ML", "is this causal", team contribution), each with a ≤4-sentence honest answer + evidence locator. Include tricky ones: why thresholds 2.0/1.5, why median as benchmark, why residual means promise miscalibration, why CI contains 0 for baseline "through", what would invalidate your conclusion.
- `DEMO_SCRIPT.md`: a 10-minute demo flow (what to click/run, what to say, what to do if the live demo fails).

MOCK DEFENSE: when I say "bắt đầu vấn đáp", act as a strict lecturer: ask ONE question at a time, mixing topics, escalating difficulty, with follow-ups ("chỉ cho thầy đoạn code đó", "số này lấy ở đâu"). After my answer, grade it, show the model answer and the locator I should have cited. After 10 questions, list my weak topics and suggest which lesson to repeat.

When I say "tôi không hiểu", re-explain with a different analogy and a smaller example, not the same words again.

Begin with the 5 files listed under TOKEN RULES, then give Lesson 0 only, and wait.
