from etl import dss_models as M
o = M.load_orders()
print(len(o), o.order_id.nunique(), round(o.is_late.mean(), 4))
print(M.route_priority(o)[["route", "orders", "late_orders", "late_rate", "level"]])
print(M.root_cause(o, "SP->RJ"))
print(M.scenario(o, "SP->RJ", {"prep": 1}))
print(M.goal_seek_promise(o, "SP->RJ", 0.05))
