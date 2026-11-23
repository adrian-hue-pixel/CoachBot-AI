from base64 import b64decode
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import coach

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(monkeypatch):
    st.cache_data.clear()  # AppTest reuses a synthetic session ID across test cases.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    test_app = AppTest.from_file(APP, default_timeout=10)
    test_app.secrets["GEMINI_API_KEY"] = ""
    test_app.secrets["GEMINI_MODEL"] = coach.DEFAULT_MODEL
    return test_app


def click(app, label):
    return next(button for button in app.button if button.label == label).click().run()


def navigate(app, page):
    return app.radio(key="cb_page").set_value(page).run()


def open_plan(app):
    app.run()
    click(app, "Build a plan")


def markup(app):
    return "\n".join([*(element.proto.body for element in app.get("html")),
                      *(element.value for element in app.markdown if 'data-cb-sport=' in element.value)])


def test_no_key_startup_and_submission(app, monkeypatch):
    generate = Mock()
    monkeypatch.setattr(coach, "generate", generate)
    app.run()
    assert '<span class="cb-hero-lead">Training plans</span>' in markup(app)
    assert '<span class="cb-hero-accent">for the way you play.</span>' in markup(app)
    assert app.radio(key="cb_page").value == "Home"
    click(app, "Build a plan")
    assert app.radio(key="cb_page").value == "Plan"
    assert tuple(app.selectbox[2].options) == tuple(coach.FEATURES)
    for _ in range(3):
        click(app, "Continue")
        assert not app.exception
    generate.assert_not_called()
    click(app, "Generate coaching plan")
    assert not app.exception
    assert "Demo mode" in app.info[0].value
    assert 'aria-label="Weekly timeline"' in markup(app)
    assert "Safety check · Passed" in markup(app)
    assert "cb_safety_outcomes" not in app.session_state
    generate.assert_not_called()


def test_public_gate_blocks_even_with_a_key(app, monkeypatch):
    generate = Mock()
    monkeypatch.setattr(coach, "generate", generate)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    open_plan(app)
    click(app, "Continue")
    click(app, "Continue")
    app.checkbox[0].check().run()
    click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    html = markup(app)
    assert 'role="alert"' in html
    assert 'role="img" aria-label="Safety shield"' in html
    assert "Pause training and tell a trusted adult." in html
    generate.assert_not_called()

    app.toggle[0].set_value(True).run()
    assert 'data-cb-motion="reduced"' in markup(app)
    assert "Pause training and tell a trusted adult." in markup(app)


def test_successful_plan_and_nutrition_chart(app, monkeypatch):
    result = {
        "summary": "Review meal ideas with a caregiver.",
        "rows": [{
            "when": "Monday", "action": "Consider a meal with rice, lentils and avocado.",
            "why": "These are familiar food options to discuss at home.",
            "carbs": "Rice", "protein": "Lentils", "fats": "Avocado",
        }],
        "review": "Review the ideas with a trusted adult.",
    }
    generate = Mock(return_value=result)
    monkeypatch.setattr(coach, "generate", generate)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    open_plan(app)
    app.selectbox[2].select("Weekly nutrition ideas").run()
    for _ in range(3):
        click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    html = markup(app)
    assert sum(result["summary"] in item.proto.body for item in app.get("html")) == 1
    assert 'aria-label="Weekly timeline"' in html
    assert html.count('<li class="cb-day ') == 7
    assert html.count("Unfilled day") == 6
    assert "These are familiar food options" in html
    assert "Load unspecified" not in html
    (chart,) = app.get("plotly_chart")
    figure = json.loads(chart.proto.spec)
    trace = figure["data"][0]
    assert trace["x"] == ["Carbs", "Protein", "Fats"]
    counts = trace["y"]
    if isinstance(counts, dict):
        counts = np.frombuffer(b64decode(counts["bdata"]), dtype=counts["dtype"]).tolist()
    assert counts == [1, 1, 1]
    assert figure["layout"]["transition"] == {"duration": 500, "easing": "cubic-in-out"}
    _, model, message, temperature = generate.call_args.args
    assert model == coach.DEFAULT_MODEL
    assert coach.SAFETY in message
    assert temperature == 0.8
    assert any(element.label == "Plan ready to review" for element in app.status)

    app.toggle[0].set_value(True).run()
    assert sum(result["summary"] in item.proto.body for item in app.get("html")) == 1
    assert "cb-summary-motion-copy" not in next(
        element.proto.body for element in app.get("html") if result["summary"] in element.proto.body
    )
    (chart,) = app.get("plotly_chart")
    assert json.loads(chart.proto.spec)["layout"]["transition"]["duration"] == 0
    generate.assert_called_once()

    for _ in range(3):
        click(app, "Back")
    app.selectbox[2].select("Tactical coaching").run()
    assert "Weekly timeline" not in markup(app)
    assert not app.get("plotly_chart")
    generate.assert_called_once()


def test_wizard_preserves_answers_and_updates_illustration(app, monkeypatch):
    generate = Mock(return_value={
        "summary": "Talk through roles with your coach.",
        "rows": [{"when": "Monday", "action": "Rest and review clips.", "why": "Review position choices.", "load": "Rest"}],
        "review": "Review ahead of practice.",
    })
    monkeypatch.setattr(coach, "generate", generate)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    open_plan(app)
    app.selectbox[0].select("Basketball").run()
    app.selectbox[1].select("Forward").run()
    app.selectbox[2].select("No-equipment training").run()
    assert 'data-cb-sport="basketball"' in markup(app)
    assert 'aria-label="Illustrative basketball position map for Forward"' in markup(app)
    next(item for item in app.selectbox if item.label == "Plan mode").select("Free-text V3").run()
    click(app, "Continue")
    app.text_input[0].set_value("  Review court spacing  ").run()
    app.selectbox[0].select("School gym").run()
    navigate(app, "Check-ins")
    assert 'aria-label="0 of 7 weekly check-ins complete"' in markup(app)
    navigate(app, "Plan")
    assert app.text_input[0].value == "  Review court spacing  "
    assert app.selectbox[0].value == "School gym"
    app.selectbox[1].select("Moderate").run()
    click(app, "Continue")
    app.number_input[0].set_value(16).run()
    app.text_input[0].set_value("  Avoid jumping  ").run()
    click(app, "Back")
    assert app.text_input[0].value == "  Review court spacing  "
    assert app.selectbox[0].value == "School gym"
    click(app, "Continue")
    assert app.number_input[0].value == 16
    assert app.text_input[0].value == "  Avoid jumping  "
    click(app, "Continue")
    app.selectbox[0].select("Vegan").run()
    click(app, "Generate coaching plan")
    assert not app.exception
    profile = coach.Profile(
        16, "Basketball", "Forward", "Review court spacing", "None", intensity="Moderate",
        diet="Vegan", restrictions="Avoid jumping",
    )
    assert generate.call_args.args[2].startswith(coach.prompt(profile, "No-equipment training", "V3"))
    assert 'class="cb-load cb-load-rest">Rest</span>' in markup(app)


def test_optional_load_and_model_text_are_rendered_as_safe_html(app, monkeypatch):
    generate = Mock(return_value={
        "summary": "Review **positioning** and [options].",
        "rows": [{"when": "<Day>", "action": "<script>fixture</script>", "why": "Discuss choices.", "load": "Intense"}],
        "review": "Review the next practice.",
    })
    monkeypatch.setattr(coach, "generate", generate)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    open_plan(app)
    next(item for item in app.selectbox if item.label == "Plan mode").select("Free-text V3").run()
    for _ in range(3):
        click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    html = markup(app)
    assert "Load unspecified" in html
    assert "&lt;Day&gt;" in html and "&lt;script&gt;fixture&lt;/script&gt;" in html
    assert "<script>fixture</script>" not in html
    assert all(not item.proto.unsafe_allow_javascript for item in app.get("html"))
    assert "Intense" not in html
    assert not app.get("markdown") or all("&#91;options&#93;" not in item.value for item in app.markdown)


def test_overlong_profile_is_rejected_before_live_generation(monkeypatch):
    import planning

    send = Mock()
    monkeypatch.setattr(coach, "generate", send)
    profile = coach.Profile(15, "Football", "Goalkeeper", "Read crosses " * 20, "Ball and cones")
    with pytest.raises(planning.ProfileInputTooLong):
        planning.run_plan(profile, "Positional drills", "en", {}, "offline-test", "test-model")
    send.assert_not_called()
