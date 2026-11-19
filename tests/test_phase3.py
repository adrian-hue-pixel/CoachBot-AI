from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import Mock

import pytest

import coach
from checkins import CheckIn, checkin_rule, recent_checkins, workload_cap
from demo_data import demo_plan
from exports import calendar_plan, csv_plan, printable_plan
from hydration import hydration_schedule
from i18n import LANGUAGES, RULE_IDS, RULE_TITLES, gate_copy
from planning import public_gate
from safety import lint_output
from ui.components import validate_plan
from test_public_app import app, click, markup


@pytest.fixture
def profile():
    return coach.Profile(15, "Football", "Striker", "Review positioning", "None")


def test_checkin_requires_three_consecutive_increasing_days_and_never_raises_load(profile):
    today = date(2026, 11, 19)
    week = {today - timedelta(days=offset): CheckIn(3 - offset, 3, True) for offset in range(3)}
    assert checkin_rule(week) == "rising_soreness"
    assert public_gate(profile, "Full-body training", week) == "rising_soreness"
    assert public_gate(profile, "Tactical coaching", week) is None
    assert checkin_rule({today: CheckIn(4, 2, False)}) == "high_soreness"
    week.pop(today - timedelta(days=1))
    assert checkin_rule(week) is None
    assert workload_cap("Moderate", week) == "Light"
    assert workload_cap("Easy", {}) == "Light"
    assert workload_cap("Moderate", {}) == "Moderate"
    assert workload_cap("Moderate", {today: CheckIn(1, 8, False)}) == "Light"
    assert recent_checkins({today - timedelta(days=7): CheckIn(5, 9, True)}, today) == {}


@pytest.mark.parametrize("text, rule", [
    ("Aim for 2000 kcal per day.", "nutrition_targets"),
    ("Take creatine before the game.", "supplements"),
    ("Your ankle is a sprain.", "clinical_advice"),
    ("Train through pain.", "unsafe_load"),
    ("புரதத் தூள் எடுத்துக்கொள்", "supplements"),
    ("दर्द के बावजूद खेलो", "unsafe_load"),
])
def test_banned_targets_and_harmful_advice_are_flagged(text, rule):
    assert rule in lint_output(text)


def test_restrictions_and_load_are_enforced(profile):
    profile.restrictions = "No jumping or overhead movement."
    assert "stated_restrictions" in lint_output("Try a hop before practice.", profile)
    assert "stated_restrictions" in lint_output("Raise your arms above your head.", profile)
    profile.allergies = "Sesame and peanuts"
    assert "food_allergy" in lint_output("Discuss a peanut snack.", profile)
    assert "sport_scope" in lint_output("Discuss cricket field placement.", profile, sport_scope=True)
    sample = validate_plan({"summary": "Review positioning.", "review": "Discuss it.",
                            "rows": [{"when": "Monday", "action": "Take an easy activity.", "why": "Review it.", "load": "Moderate"}]})
    assert "workload_cap" in lint_output(sample, profile, cap="Light")


@pytest.mark.parametrize("invalid", ["Extreme", "moderate", {"label": "Rest"}, ["Light"], 2, None])
def test_validate_plan_normalizes_unexpected_load(invalid):
    source = {"summary": "Review positioning.", "review": "Discuss it.",
              "rows": [{"when": "Monday", "action": "Discuss game clips.", "why": "Review choices.", "load": invalid}]}
    validated = validate_plan(source)
    assert "load" not in validated["rows"][0]
    assert source["rows"][0]["load"] == invalid


@pytest.mark.parametrize("locale", LANGUAGES.values())
def test_static_gate_messages_and_all_demo_modules(profile, locale):
    assert len(RULE_TITLES[locale]) == len(RULE_IDS)
    for rule in RULE_IDS:
        assert all(gate_copy(locale, rule))
    for feature in coach.FEATURES:
        assert lint_output(validate_plan(demo_plan(profile, feature, locale)), profile) == ()


def test_reminders_and_export_encoding():
    assert hydration_schedule(time(23, 50), 60) == [
        ("Before", "23:35"), ("During", "00:20 (next day)"), ("After", "00:50 (next day)"),
    ]
    rows = [{"when": "Monday", "action": "=1+1", "why": "காரணம் " * 20}]
    assert b"'=1+1" in csv_plan(rows)
    ical = calendar_plan(rows, date(2026, 11, 20), datetime(2026, 11, 19, tzinfo=timezone.utc), "sample")
    assert all(len(line) <= 75 for line in ical.split(b"\r\n"))
    assert "காரணம்" in ical.replace(b"\r\n ", b"").decode()
    html = printable_plan({"summary": "<summary>", "rows": rows, "review": "Review."}, "Full-body training", True, "ta")
    assert b"&lt;summary&gt;" in html and b"Demo data" in html


def _plan(action="Discuss a match clip with your coach."):
    return {"summary": "Review positioning.", "review": "Discuss choices.",
            "rows": [{"when": "Monday", "action": action, "why": "Review with your coach.", "load": "Light"}]}


@pytest.mark.parametrize("retry_ok, label", [(True, "Regenerated"), (False, "Fallback")])
def test_linter_retry_records_actual_outcome(app, monkeypatch, retry_ok, label):
    draft = _plan("Take creatine before the game.")
    regenerate = Mock(side_effect=[draft, _plan() if retry_ok else draft])
    monkeypatch.setattr(coach, "generate", regenerate)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    assert "Safety check · Passed</p>" not in markup(app)
    next(item for item in app.selectbox if item.label == "Plan mode").select("Free-text V3").run()
    for _ in range(3):
        click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    assert f"Safety check · {label}" in markup(app)
    assert any(f"Safety check · {label}" in item.value for item in app.markdown)
    assert "creatine" not in markup(app)
    assert regenerate.call_count == 2
    assert regenerate.call_args.args[-1] == .2
    assert "supplements" in regenerate.call_args.args[-2]
    assert app.session_state["cb_safety_outcomes"][label.casefold()] == 1


def test_cache_is_session_local_and_cooldown_guards_new_live_work(app, monkeypatch):
    send = Mock(return_value=_plan())
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    next(item for item in app.selectbox if item.label == "Plan mode").select("Free-text V3").run()
    for _ in range(3):
        click(app, "Continue")
    click(app, "Generate coaching plan")
    click(app, "Generate coaching plan")
    send.assert_called_once()
    assert any(status.label == "Saved plan ready" for status in app.status)
    assert all("Safety check ·" not in item.value for item in app.markdown)
    next(item for item in app.selectbox if item.label == "Plan language").select("தமிழ்").run()
    click(app, "Generate coaching plan")
    send.assert_called_once()
    assert any("wait five seconds" in item.value for item in app.info)


def test_checkin_ui_blocks_physical_plan_with_static_reason(app, monkeypatch):
    send = Mock()
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    next(widget for widget in app.slider if widget.label == "Soreness").set_value(4)
    click(app, "Save check-in")
    assert 'aria-label="1 of 7 weekly check-ins complete"' in markup(app)
    assert "Soreness reached 4 of 5" in markup(app)
    for _ in range(3):
        click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    assert any(status.label == "Plan paused by profile rules" for status in app.status)
    assert "Safety check · Passed</p>" not in markup(app)
    send.assert_not_called()


def test_chat_refuses_health_question_before_gemini(app, monkeypatch):
    send = Mock()
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    for _ in range(3):
        click(app, "Continue")
    app.chat_input[0].set_value("What injury do I have?").run()
    assert not app.exception
    assert "Talk with a trusted adult and a qualified clinician" in markup(app)
    send.assert_not_called()


def test_demo_breathing_hydration_and_chat_need_no_api(app, monkeypatch):
    send = Mock()
    monkeypatch.setattr(coach, "generate", send)
    app.run()
    assert any("requestAnimationFrame" in frame.proto.srcdoc for frame in app.get("iframe"))
    click(app, "Show water reminders")
    assert "Before · 15:45" in [item.value for item in app.text]
    for _ in range(3):
        click(app, "Continue")
    for index in range(10):
        app.chat_input[0].set_value(f"How can I find space in game clip {index + 1}?").run()
        assert not app.exception
    assert len(app.session_state["cb_chat"]) == 10
    assert any("ten-turn chat limit" in item.value for item in app.info)
    app.chat_input[0].set_value("What about game decisions?").run()
    assert app.chat_input[0].proto.disabled
    assert len(app.session_state["cb_chat"]) == 10
    next(item for item in app.selectbox if item.label == "Plan language").select("हिन्दी").run()
    assert app.chat_input[0].proto.disabled
    assert app.session_state["cb_chat_turns"] == 10
    assert "cb_safety_outcomes" not in app.session_state
    send.assert_not_called()


@pytest.mark.parametrize("paused", [True, False])
def test_confetti_requires_seven_checkins_and_only_runs_once(app, paused):
    app.run()
    date_widget = next(item for item in app.date_input if item.label == "Check-in date")
    today = date_widget.value
    for offset in range(7):
        next(item for item in app.date_input if item.label == "Check-in date").set_value(
            today - timedelta(days=offset)
        )
        next(item for item in app.slider if item.label == "Soreness").set_value(4 if paused and offset == 0 else 1)
        click(app, "Save check-in")
        assert not app.exception
    assert any("Consistency badge" in item.value for item in app.success)
    frames = [item.proto.srcdoc for item in app.get("iframe")]
    assert any("canvas-confetti@1.9.4" in frame for frame in frames) is not paused
    app.run()
    assert all("canvas-confetti" not in item.proto.srcdoc for item in app.get("iframe"))


def test_tactical_live_chat_passes_with_unrelated_movement_restriction(app, monkeypatch):
    answer = "Watch how a teammate pivots while the striker runs into the space behind."
    send = Mock(return_value=answer)
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    click(app, "Continue")
    click(app, "Continue")
    next(item for item in app.text_input if item.label.startswith("Clinician instructions")).set_value("No jumping.").run()
    click(app, "Continue")
    app.chat_input[0].set_value("How can the striker find space for a pass?").run()
    assert not app.exception
    assert answer in markup(app) and "Safety check · Passed" in markup(app)
    send.assert_called_once()
