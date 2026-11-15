from etl import dss_models as M
o = M.load_orders()
df = M.route_priority(o, top=len(o))
print('columns:', list(df.columns))
print()
uncertain_count = 0
for _, r in df.iterrows():
    u = '***' if r['uncertain'] else ''
    print(f"{r['route']:<10} {r['level']:<6} late={r['late_rate']*100:.2f}% ci_low={r['ci_low']*100:.2f}% uncertain={r['uncertain']} low={r['low_sample']} {u}")
    if r['uncertain']:
        uncertain_count += 1
print(f"\nTotal uncertain: {uncertain_count}/{len(df)}")
print("uncertain field in df:", 'uncertain' in df.columns)

# Test default top=10 also has uncertain col
df10 = M.route_priority(o)
print("top-10 has uncertain:", 'uncertain' in df10.columns)
print("uncertain values in top-10:", list(df10['uncertain']))
