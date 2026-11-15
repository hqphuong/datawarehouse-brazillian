"""Thu thap so that: uncertain, excess_ratio cho 14 tuyen, series SP->RJ&prep=5."""
from etl import dss_models as M
import numpy as np

o = M.load_orders()
overall = float(o.is_late.mean())
red_thr = overall * 2.0
amber_thr = overall * 1.5
sys_means = {s: float(o[s].mean()) for s in M.STAGES}

print(f"overall late rate: {overall:.6f}  ({overall*100:.4f}%)")
print(f"red threshold:   {red_thr:.6f}  ({red_thr*100:.4f}%)")
print(f"amber threshold: {amber_thr:.6f}  ({amber_thr*100:.4f}%)")
print(f"sys_means: {sys_means}")
print()

# 14 tuyen mac dinh (top=len(o), lay tat ca co co)
all_flagged = M.route_priority(o, top=len(o))
print(f"Total flagged routes: {len(all_flagged)}")
print()

# Wilson CI da co trong route_priority
# uncertain: ci_low < red_thr (neu level=red) hoac ci_low < amber_thr (neu level=amber)
# Theo 6 dieu kien:
# 1. red  & ci_low < red_thr  -> uncertain
# 2. amber & ci_low < amber_thr -> uncertain
# (+ low_sample rieng biet)

rows = []
for _, r in all_flagged.iterrows():
    rc = M.root_cause(o, r['route'])
    exc = rc['excess']
    ratios = {}
    for s in M.STAGES:
        d = abs(sys_means[s])
        ratios[s] = exc[s] / d if d > 1e-9 else 0.0

    stage_abs = rc['stage']
    stage_ratio = max(ratios, key=lambda k: ratios[k])

    # uncertain: ci_low nam duoi nguong level cua minh
    if r['level'] == 'red':
        uncertain = bool(r['ci_low'] < red_thr)
    else:  # amber
        uncertain = bool(r['ci_low'] < amber_thr)

    rows.append({
        'route': r['route'],
        'orders': int(r['orders']),
        'late_rate': float(r['late_rate']),
        'ci_low': float(r['ci_low']),
        'ci_high': float(r['ci_high']),
        'level': r['level'],
        'low_sample': bool(r['low_sample']),
        'uncertain': uncertain,
        'stage_abs': stage_abs,
        'stage_ratio': stage_ratio,
        'same_stage': stage_abs == stage_ratio,
        'exc_transit': round(exc['transit'], 4),
        'exc_prep': round(exc['prep'], 4),
        'exc_approval': round(exc['approval'], 4),
        'ratio_transit': round(ratios['transit'], 4),
        'ratio_prep': round(ratios['prep'], 4),
        'ratio_approval': round(ratios['approval'], 4),
    })

# In bang
hdr = f"{'route':<10} {'lvl':<6} {'late%':>7} {'ci_low%':>8} {'ci_hi%':>8} {'thr%':>7} {'low':>4} {'unc':>4} {'s_abs':<8} {'s_rat':<8} {'same':>5}"
print(hdr)
print("-"*95)
for r in rows:
    thr = red_thr if r['level'] == 'red' else amber_thr
    print(
        f"{r['route']:<10} {r['level']:<6} {r['late_rate']*100:>7.3f} "
        f"{r['ci_low']*100:>8.4f} {r['ci_high']*100:>8.4f} {thr*100:>7.4f} "
        f"{'T' if r['low_sample'] else 'F':>4} {'T' if r['uncertain'] else 'F':>4} "
        f"{r['stage_abs']:<8} {r['stage_ratio']:<8} {'T' if r['same_stage'] else 'F':>5}"
    )

n_uncertain = sum(1 for r in rows if r['uncertain'])
n_low_sample = sum(1 for r in rows if r['low_sample'])
n_both = sum(1 for r in rows if r['uncertain'] and r['low_sample'])
n_diff_stage = sum(1 for r in rows if not r['same_stage'])
print()
print(f"Uncertain: {n_uncertain}/{len(rows)}")
print(f"Low_sample: {n_low_sample}/{len(rows)}")
print(f"Both uncertain+low_sample: {n_both}/{len(rows)}")
print(f"Stage diff (abs vs ratio): {n_diff_stage}/{len(rows)}")

print()
print("SP->PI:", [(r['route'], r['uncertain'], r['ci_low']*100, red_thr*100 if r['level']=='red' else amber_thr*100) for r in rows if r['route']=='SP->PI'])
print("SP->SE:", [(r['route'], r['uncertain'], r['ci_low']*100, red_thr*100 if r['level']=='red' else amber_thr*100) for r in rows if r['route']=='SP->SE'])

print()
print("=== Excess transit range ===")
transit_excess = sorted([r['exc_transit'] for r in rows])
print(f"min={min(transit_excess):.4f}, max={max(transit_excess):.4f}, values={transit_excess}")

print()
print("=== Excess ratio table ===")
print(f"{'route':<10} {'exc_transit':>12} {'ratio_transit':>14} {'exc_prep':>10} {'ratio_prep':>11} {'exc_appr':>10} {'ratio_appr':>11}")
for r in rows:
    print(f"{r['route']:<10} {r['exc_transit']:>12.4f} {r['ratio_transit']:>14.4f} {r['exc_prep']:>10.4f} {r['ratio_prep']:>11.4f} {r['exc_approval']:>10.4f} {r['ratio_approval']:>11.4f}")

print()
print("=== goal_seek_cut for all 14 routes ===")
for r in rows:
    gsc = M.goal_seek_cut(o, r['route'], 'transit')
    print(f"  {r['route']}: transit_goal_cut={gsc}")

print()
print("=== series for SP->RJ&prep=5 (REAL) ===")
route = "SP->RJ"
cut = {"prep": 5.0, "transit": 0.0, "approval": 0.0}
bottleneck = M.root_cause(o, route)["stage"]
base_cut = {k: v for k, v in cut.items() if k != bottleneck}
result = M.scenario(o, route, cut)
series = M.sensitivity(o, route, bottleneck, base_cut=base_cut)
print(f"projected: {result['projected']:.15f}")
print(f"avoided: {result['avoided']}")
print("series:")
for pt in series:
    print(f'  {{"cut": {pt["cut"]}, "projected": {pt["projected"]:.15f}}}')
