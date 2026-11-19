import csv
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ablate
from ablation_data import ARMS, SCORE_COLUMNS, load_ablation_run, summarize_ablation
import coach
from exercise_bank import CUES, load_bank
from verifier import CATEGORIES


def score_run(path, labels=True):
    sheet = path / "scores.csv"
    ids = [row["response_id"] for row in load_ablation_run(path).conditions]
    with sheet.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=SCORE_COLUMNS)
        writer.writeheader()
        for id_ in ids:
            writer.writerow({"response_id": id_, "positional_specificity_1_to_5": "3" if labels else "N/A",
                             **{category: ("0" if labels else "N/A") for category in CATEGORIES}})


def test_offline_replay_is_blind_and_keeps_human_and_proxy_denominators_separate(monkeypatch, tmp_path):
    send = Mock(side_effect=AssertionError("No API access in replay."))
    monkeypatch.setattr(coach, "generate", send)
    run_path = ablate.write_run(tmp_path, len(ablate.FIXTURES), load_bank())
    run = load_ablation_run(run_path)
    assert run.source == "replay" and run.model is None and not run.ready
    assert len(run.conditions) == len(ablate.FIXTURES) * len(ARMS)
    for packet in (run_path / "blind_packets").glob("*.txt"):
        content = packet.read_text()
        assert content.startswith("Synthetic profile") and not any(arm in content for arm in ARMS)
    assert all(not row["estimated_usd"] and row["latency_ms"] is None for row in run.conditions)
    with pytest.raises(ValueError):
        summarize_ablation(run)

    score_run(run_path)
    run = load_ablation_run(run_path)
    outcomes, violations = summarize_ablation(run)
    positional = next(row for row in outcomes if row["metric"] == "Positional specificity (1–5)")
    assert positional["source"] == "Human" and positional["n"] == 10 and positional["ci"] == (3.0, 3.0)
    v1 = [row for row in violations if row["arm"] == ARMS[0] and row["metric"] == "stated_restrictions"]
    assert [(row["source"], row["n"], row["mean"]) for row in v1] == [
        ("Human", 10, 0), ("Linter proxy", 10, 0.2),
    ]
    assert not any(row["source"] == "Linter proxy" and row["metric"] == "other" for row in violations)
    assert sum(row["gated"] for row in run.conditions if row["arm"] == ARMS[-1]) == 2
    assert any(row["fallback"] for row in run.conditions if row["arm"] == ARMS[3])
    send.assert_not_called()


def test_live_request_metrics_keep_shared_draws_costs_and_cooldown_distinct(tmp_path, monkeypatch):
    clock = [0.0]
    calls = []

    def advance(seconds):
        clock[0] += seconds

    def fake_generate(key, model, message, temperature, **kwargs):
        calls.append((clock[0], message))
        advance(0.25)
        kwargs["on_usage"](SimpleNamespace(prompt_token_count=20, candidates_token_count=5, thoughts_token_count=3))
        schema = kwargs.get("response_schema")
        if schema and "passed" in schema["properties"]:
            return {"passed": True, "categories": []}
        if schema:
            return {"rows": [{"exercise_id": "goalkeeper_roll", "cue": CUES["en"][0]}]}
        return "Goalkeeper: talk through a cross with a coach."

    monkeypatch.setattr(ablate, "monotonic", lambda: clock[0])
    monkeypatch.setattr(ablate, "sleep", advance)
    monkeypatch.setattr(coach, "generate", fake_generate)
    run_path = ablate.write_run(tmp_path, 1, load_bank(), ablate.Requests("mock-secret-key", "gemini-test"), (2., 3.))
    run = load_ablation_run(run_path)
    result = {row["arm"]: row for row in run.conditions}
    assert [when for when, _ in calls] == [0, 5, 10, 15]
    assert result[ARMS[1]]["input_tokens"] == result[ARMS[2]]["input_tokens"] == 20
    assert result[ARMS[3]]["input_tokens"] == 40 and result[ARMS[3]]["output_tokens"] == 16
    assert result[ARMS[3]]["latency_ms"] == 500
    assert result[ARMS[3]]["estimated_usd"] == pytest.approx(0.000128)
    assert result[ARMS[-1]]["role_named"]
    assert all("mock-secret-key" not in request for _, request in calls)
    assert all("mock-secret-key" not in p.read_text() for p in run_path.rglob("*") if p.is_file())


def test_partial_ablations_are_sealed_and_malformed_manifests_rejected(tmp_path):
    path = ablate.write_run(tmp_path, 1, load_bank())
    score_run(path, labels=False)
    run = load_ablation_run(path)
    assert run.ready
    outcomes, _ = summarize_ablation(run)
    assert all(not row["n"] and row["mean"] is None for row in outcomes if row["source"] == "Human")
    manifest_path = path / "conditions.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["conditions"][1]["response_id"] = manifest["conditions"][0]["response_id"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_ablation_run(path)
