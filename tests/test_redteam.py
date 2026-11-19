import json
from unittest.mock import Mock

import pytest

import coach
import redteam
from exercise_bank import CUES
from redteam_data import CATEGORIES, REPORT, load_redteam_report
from safety import INPUT_LIMITS, chat_request_action, input_too_long


def test_offline_suite_is_fixed_and_bundled_report_matches(monkeypatch):
    send = Mock(side_effect=AssertionError("Offline checks must not call Gemini."))
    monkeypatch.setattr(coach, "generate", send)
    rows = redteam.PROBES
    assert len(rows) == len(set(rows)) == 50
    assert {row.category for row in rows} == set(CATEGORIES)
    assert {row.field for row in rows} == set(INPUT_LIMITS)
    assert {row.expected for row in rows} == {"block", "refuse", "redirect"}
    assert redteam.run_offline() == json.loads(REPORT.read_text(encoding="utf-8"))
    report = load_redteam_report()
    assert sum(row["Cases"] for row in report) == 50
    send.assert_not_called()


@pytest.mark.parametrize("question", [
    "Where should I stand before the pass?",
    "பந்து எங்கு வரும்?",
    "गेंद कहाँ आएगी?",
    "When should I tell my coach I'm nervous about the match?",
])
def test_chat_control_questions_still_reach_generation_policy(question):
    assert chat_request_action(question, redteam.PROFILE, has_context=False) == "allow"


@pytest.mark.parametrize("field", INPUT_LIMITS)
def test_text_length_boundary(field):
    assert not input_too_long(field, "a" * INPUT_LIMITS[field])
    assert input_too_long(field, "a" * (INPUT_LIMITS[field] + 1))


def test_offline_mismatches_are_counted_by_category(monkeypatch):
    probe = next(probe for probe in redteam.PROBES if probe.category == "medical" and probe.field == "chat")
    monkeypatch.setattr(redteam, "PROBES", (probe,))
    monkeypatch.setattr(redteam, "chat_request_action", lambda *args, **kwargs: "allow")
    rows = redteam.run_offline()["categories"]
    assert rows["medical"] == {"cases": 1, "mismatches": 1}
    assert not any(row["cases"] or row["mismatches"] for key, row in rows.items() if key != "medical")


def test_live_smoke_sends_one_ordinary_catalog_request(monkeypatch):
    send = Mock(return_value={"rows": [{"exercise_id": "goalkeeper_roll", "cue": CUES["en"][0]}]})
    monkeypatch.setattr(coach, "generate", send)
    assert redteam.live_smoke("fictional-test-key", "gemini-test")
    send.assert_called_once()
    assert "fictional-test-key" not in send.call_args.args[2]
    assert all(probe.text not in send.call_args.args[2] for probe in redteam.PROBES)


def test_report_rejects_invalid_counts_and_unexpected_categories(tmp_path):
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    report = tmp_path / "report.json"
    data["categories"]["medical"]["mismatches"] = 100
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_redteam_report(report)
    data["categories"]["unrecognized"] = data["categories"].pop("medical")
    report.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_redteam_report(report)
