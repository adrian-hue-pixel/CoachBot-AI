"""Run six fictional profiles through CoachBot's offline planning workflow."""

from dataclasses import replace
from datetime import date, timedelta
import json

from streamlit.testing.v1 import AppTest

import coach
from checkins import CheckIn
from exercise_bank import CONSTRAINED, FREE_TEXT
from planning import public_gate, run_plan


def run_cases():
    striker = coach.Profile(15, "Football", "Striker", "Improve first touch", "Ball and cones")
    bowler = coach.Profile(15, "Cricket", "Fast bowler", "Read a batter's setup", "Ball and cones")
    guard = coach.Profile(16, "Basketball", "Point guard", "Read the passing lane", "None")
    restricted = replace(bowler, injury_status="Active injury or awaiting clearance",
                         restrictions="No impact or overhead movement.")
    today = date(2026, 11, 23)
    checkins = {
        today - timedelta(days=2): CheckIn(1, 4, False),
        today - timedelta(days=1): CheckIn(2, 4, False),
        today: CheckIn(3, 4, False),
    }
    cases = (
        ("Football striker", "Positional drills", striker, {}, CONSTRAINED, "passed"),
        ("Cricket fast bowler", "Tactical coaching", bowler, {}, FREE_TEXT, "passed"),
        ("Basketball point guard", "No-equipment training", guard, {}, CONSTRAINED, "passed"),
        ("Uncleared knee and shoulder restrictions", "Return-to-sport schedule",
         restricted, {}, FREE_TEXT, "awaiting_clearance"),
        ("Reported allergy", "Weekly nutrition ideas",
         replace(striker, allergies="Peanut"), {}, FREE_TEXT, "food_allergies"),
        ("Three rising soreness scores", "Full-body training",
         guard, checkins, CONSTRAINED, "rising_soreness"),
    )
    results = []
    for case, module, profile, entries, mode, expected in cases:
        observed = public_gate(profile, module, entries)
        rows = []
        if observed is None:
            observed, plan, _ = run_plan(profile, module, "en", entries, None,
                                         coach.DEFAULT_MODEL, mode=mode)
            rows = plan["rows"]
        results.append({
            "case": case,
            "module": module,
            "expected": expected,
            "observed": observed,
            "rows": len(rows),
            "first_action": rows[0]["action"] if rows else None,
        })
    return results


def main():
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from tools.assessment_demo import run_cases\n"
        "st.session_state.assessment_results = run_cases()"
    ).run()
    if app.exception:
        raise SystemExit("The offline assessment simulation failed to run.")
    results = app.session_state.assessment_results
    print(json.dumps({"mode": "offline_demo", "cases": results}, indent=2))
    return int(any(item["observed"] != item["expected"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
