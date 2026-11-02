import json
from urllib.parse import urlencode

from django.test import TestCase

from .models import ActionLog


class DssApiTests(TestCase):
    def test_routes_default_top_10(self):
        res = self.client.get("/api/dss/routes")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertEqual(len(rows), 10)
        self.assertEqual(set(rows[0]), {
            "route", "orders", "late_orders", "late_rate", "level", "root_cause",
        })
        self.assertIn(rows[0]["level"], {"red", "amber"})
        self.assertIn("has_bottleneck", rows[0]["root_cause"])

    def test_routes_top_100_returns_all_flagged(self):
        res = self.client.get("/api/dss/routes?top=100")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 14)

    def test_routes_year_filter(self):
        res = self.client.get("/api/dss/routes?year=2018")
        self.assertEqual(res.status_code, 200)
        rows = res.json()
        self.assertTrue(all(r["orders"] > 0 for r in rows))

    def test_routes_bad_year(self):
        res = self.client.get("/api/dss/routes?year=abc")
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

    def test_scenario_sp_rj(self):
        res = self.client.get("/api/dss/scenario?" + urlencode({"route": "SP->RJ"}))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["orders"], 8108)
        self.assertAlmostEqual(body["baseline"], 0.155772, places=5)
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
