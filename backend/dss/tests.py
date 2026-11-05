import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import TestCase, override_settings

from etl import dss_ml as ML
from etl import dss_models as M

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
        self.assertEqual(round(overall * 100, 2), 8.07)
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


class AtRiskApiTests(TestCase):
    def test_at_risk_default_limit_sorted_and_keys(self):
        res = self.client.get("/api/dss/at-risk")
        self.assertEqual(res.status_code, 200)
        body = res.json()

        self.assertEqual(len(body["orders"]), 20)
        self.assertEqual(set(body), {"orders", "meta"})
        self.assertEqual(
            set(body["orders"][0]),
            {"order_id", "route", "risk_score", "actual_late"},
        )

        scores = [row["risk_score"] for row in body["orders"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
        self.assertTrue(all(isinstance(row["actual_late"], bool) for row in body["orders"]))

    def test_at_risk_risk_score_matches_predict_orders(self):
        body = self.client.get("/api/dss/at-risk?limit=10").json()
        meta = body["meta"]

        o = M.load_orders()
        test = o[o["period"].isin(meta["test_periods"])]
        lookup = test.set_index(["order_id", "route"])
        keys = [(row["order_id"], row["route"]) for row in body["orders"]]
        selected = lookup.loc[keys].reset_index()

        expected = ML.predict_orders(selected)
        for row, score in zip(body["orders"], expected):
            self.assertAlmostEqual(row["risk_score"], float(score), places=12)

    def test_at_risk_only_test_period_and_actual_late_matches(self):
        body = self.client.get("/api/dss/at-risk?limit=50").json()
        meta = body["meta"]

        self.assertEqual(meta["cutoff_period"], 201804)
        self.assertEqual(meta["test_periods"], [201804, 201805, 201806, 201807, 201808])
        self.assertEqual(meta["test_rows"], 32378)
        self.assertAlmostEqual(meta["test_late_rate"], 0.05979368707146828, places=12)

        o = M.load_orders()
        test = o[o["period"].isin(meta["test_periods"])]
        late = test.set_index(["order_id", "route"])["is_late"]
        for row in body["orders"]:
            key = (row["order_id"], row["route"])
            self.assertIn(key, late.index)
            self.assertEqual(row["actual_late"], bool(late.loc[key]))

    def test_at_risk_metadata(self):
        meta = self.client.get("/api/dss/at-risk?limit=1").json()["meta"]

        for key in (
            "cutoff_period",
            "test_periods",
            "test_rows",
            "test_late_rate",
            "model_name",
            "threshold",
            "threshold_selected_on",
            "roc_auc",
            "pr_auc",
            "precision",
            "recall",
            "f1",
            "precision_at_k",
            "score_note",
            "note",
        ):
            self.assertIn(key, meta)

        self.assertEqual(meta["model_name"], "logistic_regression")
        self.assertEqual(meta["threshold_selected_on"], "validation")
        self.assertIn("không phải xác suất đã hiệu chỉnh", meta["score_note"])
        self.assertEqual(
            [row["k_fraction"] for row in meta["precision_at_k"]], [0.01, 0.05, 0.10]
        )
        self.assertIn("mô phỏng", meta["note"].lower())
        self.assertIn("không phụ thuộc bộ lọc năm", meta["note"].lower())

    def test_at_risk_limit_valid_and_invalid(self):
        for limit in (1, 37, 100):
            res = self.client.get(f"/api/dss/at-risk?limit={limit}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(res.json()["orders"]), limit)

        for bad in ("0", "-1", "101", "abc", "1.5", ""):
            res = self.client.get(f"/api/dss/at-risk?limit={bad}")
            self.assertEqual(res.status_code, 400)
            self.assertIn("error", res.json())

        # Không truyền limit -> mặc định 20 (đã kiểm ở test đầu), kiểm thêm 100.
        res = self.client.get("/api/dss/at-risk?limit=100")
        self.assertEqual(len(res.json()["orders"]), 100)

    def test_at_risk_missing_model_returns_503_without_touching_real_file(self):
        self.assertTrue(ML.MODEL_PATH.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "late_risk.joblib"
            with override_settings(DSS_ML_MODEL_PATH=str(missing)):
                res = self.client.get("/api/dss/at-risk")
            self.assertEqual(res.status_code, 503)
            self.assertIn("error", res.json())
            self.assertIn("etl\\dss_ml.py", res.json()["error"])
            self.assertFalse(missing.exists())

        # File thật vẫn còn và endpoint hoạt động lại bình thường.
        self.assertTrue(ML.MODEL_PATH.is_file())
        self.assertEqual(self.client.get("/api/dss/at-risk?limit=1").status_code, 200)

    def test_at_risk_model_is_cached_between_requests(self):
        ML.clear_model_cache(ML.MODEL_PATH)
        first = self.client.get("/api/dss/at-risk?limit=1")
        self.assertEqual(first.status_code, 200)

        key = str(ML.MODEL_PATH.resolve())
        self.assertIn(key, ML._MODEL_CACHE)

        # Nếu cố nạp lại từ đĩa, test sẽ fail; cache phải phục vụ yêu cầu thứ hai.
        with patch(
            "etl.dss_ml.joblib.load",
            side_effect=AssertionError("không được nạp lại mô hình"),
        ):
            second = self.client.get("/api/dss/at-risk?limit=1")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["orders"], second.json()["orders"])
