"""Aggregate-only sensitivity of relative-effort-v1's mixed stress sources."""
import json
from datetime import date, timedelta
from unittest import TestCase

from tools.relative_effort_sensitivity import evaluate
from rideworks.relative_effort import classify


def ride(identity, day, stress, method="power", hours=1):
    status = {"power": "calculated", "session_power": "session_estimate",
              "hr": "hr_estimate"}[method]
    return dict(activity_id=str(identity), day=day, timezone_unknown=False,
                title="PRIVATE_RIDE_TITLE_SHOULD_NEVER_LEAK",
                selected=dict(method=method, status=status, stress=stress),
                power=dict(intervals=[dict(seconds=hours * 3600)]),
                session_power=dict(duration_seconds=hours * 3600),
                hr=dict(active_seconds=hours * 3600))


def past_six(method="power", start=date(2026, 10, 1), base=10):
    return [ride(f"{method}_{i}", (start + timedelta(days=i)).isoformat(),
                 base + 10*i, method=method) for i in range(6)]


class RelativeEffortSensitivityTests(TestCase):
    def test_single_method_unchanged_where_comparable(self):
        rides = past_six() + [ride("target", "2026-10-17", 40)]
        original = classify(rides)
        result = evaluate(rides)
        self.assertEqual(result["baseline_labels"]["Moderate"], 1)
        self.assertEqual(original["target"]["status"], "available")
        for alt in result["alternatives"].values():
            self.assertEqual(alt["both_rated"], 1)
            self.assertEqual(alt["changed"], 0)
            self.assertEqual(alt["alternate_not_rated"], 0)

    def test_hr_cohort_can_shift_two_bands_without_changing_model(self):
        rides = (past_six("power", base=10) +
                 past_six("hr", start=date(2026, 10, 8), base=100) +
                 [ride("hr_target", "2026-10-17", 60, method="hr")])
        original = classify(rides)["hr_target"]
        self.assertEqual(original["category"], "Moderate")
        result = evaluate(rides)
        for alt in result["alternatives"].values():
            self.assertGreaterEqual(alt["two_or_more_bands"], 1)
            self.assertGreaterEqual(alt["lower"], 1)
        self.assertEqual(classify(rides)["hr_target"]["category"], "Moderate")

    def test_less_than_six_same_family_is_unrated_not_zero(self):
        rides = (past_six() + [ride("hr_prior", "2026-10-12", 60, method="hr"),
                              ride("hr_target", "2026-10-17", 65, method="hr")])
        result = evaluate(rides)
        self.assertEqual(classify(rides)["hr_target"]["status"], "available")
        for alt in result["alternatives"].values():
            self.assertGreaterEqual(alt["alternate_not_rated"], 1)
            self.assertGreaterEqual(alt["by_method"]["hr"]["alternate_not_rated"], 1)

    def test_session_power_shares_family_but_not_exact_cohort(self):
        rides = past_six() + [ride("session", "2026-10-17", 35,
                                   method="session_power")]
        result = evaluate(rides)
        self.assertEqual(result["alternatives"]["family"]["both_rated"], 1)
        self.assertEqual(result["alternatives"]["exact"]["alternate_not_rated"], 1)

    def test_output_omits_rider_identifiers_titles_and_dates(self):
        rides = past_six() + [ride("SECRET_ID", "2026-10-17", 30)]
        payload = json.dumps(evaluate(rides))
        self.assertNotIn("SECRET_ID", payload)
        self.assertNotIn("PRIVATE_RIDE_TITLE", payload)
        self.assertNotIn("2026-10-17", payload)
        self.assertIn("baseline_labels", payload)
