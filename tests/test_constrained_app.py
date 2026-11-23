from unittest.mock import Mock

import coach
from exercise_bank import CUES

from test_public_app import app, click, markup, navigate, open_plan


def _go_to_final_step(app):
    open_plan(app)
    assert next(item for item in app.selectbox if item.label == "Plan mode").value == "Constrained"
    for _ in range(3):
        click(app, "Continue")


def row(id_, cue=CUES["en"][0]):
    return {"exercise_id": id_, "cue": cue}


def test_constrained_defaults_to_bank_and_shows_review_notice(app, monkeypatch):
    send = Mock()
    monkeypatch.setattr(coach, "generate", send)
    _go_to_final_step(app)
    click(app, "Generate coaching plan")
    assert not app.exception
    assert any("Exercise bank not yet reviewed by a teacher." in item.value for item in app.warning)
    assert "Coaching cue" in markup(app)
    _, (verdict, plan) = app.session_state["cb_outcome"]
    assert verdict == "passed" and len(plan["rows"]) == 7
    assert any(item["load"] == "Rest" for item in plan["rows"])
    assert all(item["exercise_id"] for item in plan["rows"])
    send.assert_not_called()


def test_live_constrained_request_filters_known_exercises_and_keeps_profile_text_local(app, monkeypatch):
    send = Mock(return_value={"rows": [row("small_hops"), row("inside_pass"), row("easy_walk"), row("rest_break")]})
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    open_plan(app)
    click(app, "Continue")
    app.text_input[0].set_value("SENTINEL profile note").run()
    click(app, "Continue")
    app.text_input[0].set_value("No jumping.").run()
    click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    html = markup(app)
    assert ("Easy walk on a clear surface" in html and "Rest break" in html
            and "Small hops in place" not in html and "Stationary inside-foot passing" not in html)
    send.assert_called_once()
    call = send.call_args
    assert "SENTINEL" not in call.args[2] and "No jumping." not in call.args[2]
    schema = call.kwargs["response_schema"]["properties"]["rows"]["items"]["properties"]
    assert "small_hops" not in schema["exercise_id"]["enum"]
    assert "inside_pass" not in schema["exercise_id"]["enum"]


def test_unknown_ids_retry_then_render_static_fallback(app, monkeypatch):
    send = Mock(return_value={"rows": [row("easy_walk"), row("unregistered_activity")]})
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    _go_to_final_step(app)
    click(app, "Generate coaching plan")
    assert not app.exception
    html = markup(app)
    assert "Safety check · Fallback" in html and "Easy walk on a clear surface" not in html
    assert "unregistered_activity" not in html and not app.get("download_button")
    assert [call.args[-1] for call in send.call_args_list] == [.3, .2]


def test_constrained_live_sends_only_rest_choices_after_checkin_reduces_workload(app, monkeypatch):
    send = Mock(return_value={"rows": [row("easy_walk"), row("rest_break")]})
    monkeypatch.setattr(coach, "generate", send)
    app.secrets["GEMINI_API_KEY"] = "offline-test"
    app.run()
    navigate(app, "Check-ins")
    next(item for item in app.slider if item.label == "Soreness").set_value(3)
    click(app, "Save check-in")
    navigate(app, "Plan")
    click(app, "Continue")
    next(item for item in app.selectbox if item.label == "Preferred intensity").select("Moderate").run()
    click(app, "Continue")
    click(app, "Continue")
    click(app, "Generate coaching plan")
    assert not app.exception
    assert "Rest break" in markup(app) and "Easy walk on a clear surface" not in markup(app)
    send.assert_called_once()
    schema = send.call_args.kwargs["response_schema"]["properties"]["rows"]["items"]["properties"]
    assert "rest_break" in schema["exercise_id"]["enum"]
    assert "easy_walk" not in schema["exercise_id"]["enum"]
