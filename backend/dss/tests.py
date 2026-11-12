import json
from urllib.parse import urlencode

from django.test import TestCase

from etl import dss_models as M

from . import views
from .models import ActionLog


class DssApiTests(TestCase):
    def test_routes_default_top_10(self):
        res = self.client.get("/api/dss/routes")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertEqual(len(rows), 10)
        self.assertEqual(set(rows[0]), {
            "route", "orders", "late_orders", "late_rate", "level", "root_cause",
            "ci_low", "ci_high", "low_sample", "uncertain",
        })
        self.assertIn(rows[0]["level"], {"red", "amber"})
        self.assertIn("has_bottleneck", rows[0]["root_cause"])

    def test_routes_default_top_contains_all_red(self):
        rows = self.client.get("/api/dss/routes").json()
        all_rows = self.client.get("/api/dss/routes?top=100").json()

        red = {r["route"] for r in all_rows if r["level"] == "red"}
        self.assertTrue(red)
        self.assertLessEqual(red, {r["route"] for r in rows})
        self.assertEqual(rows[0]["level"], "red")

    def test_routes_wilson_fields_and_low_sample(self):
        rows = self.client.get("/api/dss/routes").json()
        for row in rows:
            self.assertIn("ci_low", row)
            self.assertIn("ci_high", row)
            self.assertIn("low_sample", row)
            self.assertLessEqual(0.0, row["ci_low"])
            self.assertLessEqual(row["ci_low"], row["late_rate"])
            self.assertLessEqual(row["late_rate"], row["ci_high"])
            self.assertLessEqual(row["ci_high"], 1.0)
            self.assertIsInstance(row["low_sample"], bool)
            self.assertEqual(row["low_sample"], row["orders"] < 200)

    def test_routes_uncertain_uses_overall_rate_not_test_prevalence(self):
        """Cờ uncertain dùng tỷ lệ trễ chung ≈ 8,07%, không dùng 5,98% của tập kiểm tra.

        Cờ không đổi level, thứ tự, stage, has_bottleneck, và không trùng low_sample.
        """
        test_prevalence = 0.05979368707146828
        orders = M.load_orders()
        overall = float(orders["is_late"].mean())
        self.assertEqual(round(overall * 100, 2), 8.16)
        self.assertEqual(round(test_prevalence * 100, 2), 5.98)
        self.assertGreater(abs(overall - test_prevalence), 0.02)

        rows = self.client.get("/api/dss/routes?top=100").json()
        self.assertEqual(len(rows), 14)
        red_thr = overall * 2.0
        amber_thr = overall * 1.5
        disagree = 0
        for row in rows:
            self.assertIsInstance(row["uncertain"], bool)
            if row["late_rate"] >= red_thr:
                self.assertEqual(row["level"], "red")
                threshold = red_thr
                wrong = test_prevalence * 2.0
            else:
                self.assertEqual(row["level"], "amber")
                self.assertGreaterEqual(row["late_rate"], amber_thr)
                threshold = amber_thr
                wrong = test_prevalence * 1.5
            expected = row["ci_low"] < threshold
            self.assertIs(row["uncertain"], expected)
            if (row["ci_low"] < wrong) is not expected:
                disagree += 1

            cause = M.root_cause(orders, row["route"])
            subset = orders[orders["route"] == row["route"]]
            excess = {
                stage: float(subset[stage].mean() - orders[stage].mean())
                for stage in M.STAGES
            }
            self.assertEqual(row["root_cause"]["stage"], max(excess, key=excess.get))
            self.assertIs(
                row["root_cause"]["has_bottleneck"], max(excess.values()) > 0
            )
            self.assertEqual(row["root_cause"]["stage"], cause["stage"])
            self.assertIs(row["root_cause"]["has_bottleneck"], cause["has_bottleneck"])
            self.assertNotIn("uncertain", row["root_cause"])

        self.assertGreater(disagree, 0)

        pairs = {(row["low_sample"], row["uncertain"]) for row in rows}
        self.assertIn((False, True), pairs)
        self.assertIn((True, False), pairs)

        levels = [row["level"] for row in rows]
        n_red = levels.count("red")
        self.assertEqual(levels, ["red"] * n_red + ["amber"] * (len(levels) - n_red))
        for level in ("red", "amber"):
            late_orders = [row["late_orders"] for row in rows if row["level"] == level]
            self.assertEqual(len(late_orders), len(set(late_orders)))
            self.assertEqual(late_orders, sorted(late_orders, reverse=True))

        uncertain_first = sorted(
            rows,
            key=lambda row: (
                0 if row["level"] == "red" else 1,
                0 if row["uncertain"] else 1,
                -row["late_orders"],
            ),
        )
        self.assertNotEqual(
            [row["route"] for row in rows],
            [row["route"] for row in uncertain_first],
        )

    def test_routes_top_100_returns_all_flagged(self):
        res = self.client.get("/api/dss/routes?top=100")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 14)

    def test_routes_year_filter(self):
        res = self.client.get("/api/dss/routes?year=2018")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertTrue(all(r["orders"] > 0 for r in rows))

    def test_routes_year_uses_full_period_base_rate(self):
        """?year= chỉ lọc tuyến; ngưỡng đỏ/vàng vẫn theo L toàn giai đoạn."""
        rows = self.client.get("/api/dss/routes?year=2018&top=100").json()
        self.assertTrue(rows)
        for row in rows:
            if row["late_rate"] >= views.BASE_RATE * 2.0:
                self.assertEqual(row["level"], "red")
            elif row["late_rate"] >= views.BASE_RATE * 1.5:
                self.assertEqual(row["level"], "amber")
            else:
                self.fail(f"tuyến {row['route']} bị gắn cờ dưới ngưỡng toàn kỳ")

    def test_brief_config_exposes_full_period_base_rate(self):
        body = self.client.get("/api/dss/brief").json()
        self.assertAlmostEqual(body["config"]["base_rate"], views.BASE_RATE, places=12)
        self.assertEqual(
            body["config"]["base_rate_label"],
            "overall rate of the full period",
        )

    def test_routes_bad_year(self):
        res = self.client.get("/api/dss/routes?year=abc")
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_scenario_sp_rj(self):
        res = self.client.get("/api/dss/scenario?" + urlencode({"route": "SP->RJ"}))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["orders"], 8016)
        self.assertAlmostEqual(body["baseline"], 0.157061, places=5)
        self.assertAlmostEqual(body["projected"], body["baseline"], places=12)
        self.assertEqual(body["bottleneck"], "transit")
        self.assertIs(body["has_bottleneck"], True)
        self.assertEqual(len(body["series"]), 6)
        self.assertNotIn("NaN", res.content.decode())

    def test_scenario_with_cut(self):
        res = self.client.get("/api/dss/scenario?" + urlencode({"route": "SP->RJ", "prep": 5}))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertLess(body["projected"], body["baseline"])
        self.assertGreater(body["avoided"], 0)

    def test_scenario_missing_route(self):
        res = self.client.get("/api/dss/scenario")
        self.assertEqual(res.status_code, 400)

    def test_scenario_unknown_route(self):
        res = self.client.get("/api/dss/scenario?" + urlencode({"route": "XX->YY"}))
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_promise_sp_rj(self):
        res = self.client.get("/api/dss/promise?" + urlencode({"route": "SP->RJ", "target": 0.05}))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["extra_days"], 15)
        self.assertLessEqual(body["late_after"], 0.05)

    def test_promise_missing_route(self):
        res = self.client.get("/api/dss/promise")
        self.assertEqual(res.status_code, 400)

    def test_actions_post_and_get(self):
        payload = {
            "action": "extend_promise",
            "route": "SP->RJ",
            "level": "amber",
            "extra_days": 15,
        }
        res = self.client.post(
            "/api/dss/actions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True})
        self.assertEqual(ActionLog.objects.count(), 1)
        row = ActionLog.objects.get()
        self.assertEqual(row.action, "extend_promise")
        self.assertEqual(row.route, "SP->RJ")
        self.assertEqual(row.level, "amber")
        self.assertEqual(json.loads(row.detail)["extra_days"], 15)

        listing = self.client.get("/api/dss/actions")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)

    def test_actions_reject_invalid_json(self):
        res = self.client.post(
            "/api/dss/actions",
            data="{not-json",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ActionLog.objects.count(), 0)

    def test_scenario_series_matches_projected_with_base_cut(self):
        """series[transit_cut].projected phải bằng projected khi cut kết hợp prep+transit."""
        from urllib.parse import urlencode
        params = urlencode({"route": "SP->RJ", "prep": 2, "transit": 1})
        res = self.client.get(f"/api/dss/scenario?{params}")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # bottleneck là transit; series[1] ứng với transit_cut=1, prep=2 cố định
        self.assertEqual(body["bottleneck"], "transit")
        series = body["series"]
        self.assertEqual(series[1]["cut"], 1)
        self.assertAlmostEqual(series[1]["projected"], body["projected"], places=12)

    def test_brief_endpoint_includes_action_groups_and_notes(self):
        res = self.client.get("/api/dss/brief")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("route_actions", body)
        self.assertIn("seller_actions", body)
        self.assertIn("low_sample_actions", body)
        self.assertTrue(
            any("đổi định nghĩa trễ, không rút ngắn thời gian giao" in note
                for note in body["notes"])
        )

    def test_attribution_endpoint_accepts_supported_quantiles(self):
        for q in ("0.25", "0.5"):
            res = self.client.get(f"/api/dss/attribution?q={q}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["q"], float(q))
            self.assertIn("rows", res.json())
            self.assertIn("shares_in_late_orders", res.json()["systemwide"])

    def test_attribution_endpoint_ranked_routes_peer_fields(self):
        res = self.client.get("/api/dss/attribution?q=0.5")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["grain"], "order-route")
        self.assertIn("ranked_routes", body)
        rows = body["ranked_routes"]
        self.assertTrue(rows)
        required = {
            "route", "order_routes", "orders", "late_rate",
            "expected_late_rate", "excess_pp", "excess_order_routes",
            "share_promise", "top_stage", "benchmark_peer_share",
        }
        self.assertLessEqual(required, set(rows[0]))
        excess = [row["excess_pp"] for row in rows]
        self.assertEqual(excess, sorted(excess, reverse=True))
        for row in rows[:10]:
            self.assertAlmostEqual(
                row["late_rate"],
                row["expected_late_rate"] + row["phi_total"],
                places=10,
            )
            self.assertAlmostEqual(row["excess_pp"], row["phi_total"] * 100, places=8)
            self.assertGreaterEqual(row["order_routes"], row["orders"])
            self.assertIn(row["top_stage"], {"approval", "prep", "transit"})
            self.assertGreaterEqual(row["orders"], 30)

    def test_attribution_endpoint_rejects_q75_with_reason(self):
        res = self.client.get("/api/dss/attribution?q=0.75")
        self.assertEqual(res.status_code, 400)
        self.assertIn("q=0.75 bị loại", res.json()["error"])

    def test_promise_policy_endpoint_labels_service_levels(self):
        res = self.client.get("/api/dss/promise-policy")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(
            body["label"], "mức phục vụ, không phải khuyến nghị đặt promise"
        )
        self.assertEqual(
            {row["service_level"] for row in body["rows"]},
            {0.85, 0.9, 0.95},
        )
        self.assertIn("không rút ngắn thời gian giao", body["note"])

    def test_sellers_endpoint_returns_single_seller_scorecard(self):
        res = self.client.get("/api/dss/sellers")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["rows"])
        self.assertIn("segment", body["rows"][0])
        self.assertGreater(body["summary"]["n_orders_single_seller"], 0)

    def test_portfolio_endpoint_reports_half_late_order_coverage(self):
        res = self.client.get("/api/dss/portfolio")
        self.assertEqual(res.status_code, 200)
        coverage = res.json()["coverage_50_percent"]
        self.assertEqual(coverage["k"], 102)
        self.assertAlmostEqual(coverage["covered_share"], 0.5010, places=4)
