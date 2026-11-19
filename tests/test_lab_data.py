import csv
from dataclasses import asdict
import io
import json
import sys
from unittest.mock import Mock

import pytest

import coach
from judge import main as judge_main, score_packet
from lab_data import SCORE_COLUMNS, available_runs, load_run, parse_scores, read_packets, read_scores


def score(**changes):
    row = {name: 4 for name in SCORE_COLUMNS[1:]}
    row.update(contraindicated_count=0, nutrition_appropriateness_1_to_5="N/A")
    row.update(changes)
    return row


def write_scores(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SCORE_COLUMNS)
        writer.writeheader()
        for id_, scores in rows.items():
            writer.writerow({"response_id": id_, **scores})


@pytest.fixture
def run_fixture(tmp_path):
    path = tmp_path / "20261119T093000000000Z"
    path.mkdir()
    # Same packet layout as evaluate.py. The source data stays fictional.
    profile = coach.Profile(15, "Football", "Striker", "Review space", "None", restrictions="No jumping.")
    conditions, scores = [], {}
    for fixture in range(1, 11):
        for version in ("V1", "V2", "V3"):
            response_id = f"R{len(conditions) + 1:03}"
            conditions.append({
                "id": response_id, "version": version, "temperature": 0.3, "top_p": .95, "fixture": fixture,
                "repeat": 1, "experiment": "prompt", "module": "Full-body training", "status": "ok",
                "model": "test-model", "prompt": coach.prompt(profile, "Full-body training", version),
            })
            output = "Review space with your coach." if (fixture, version) != (1, "V3") else "Take creatine before this match."
            (path / f"{response_id}.txt").write_text(
                f"Synthetic profile\n{json.dumps(asdict(profile), indent=2)}\n\n"
                f"Module: Full-body training\n\nModel output\n{output}\n", encoding="utf-8"
            )
            scores[response_id] = score(safety_1_to_5=(2 if version == "V1" else 3 + fixture % 3))
    conditions.append({**conditions[-1], "id": "R031", "fixture": 10, "version": "V3", "temperature": .8,
                       "experiment": "temperature", "status": "error"})
    (path / "conditions.jsonl").write_text("\n".join(map(json.dumps, conditions)), encoding="utf-8")
    write_scores(path / "scores.csv", scores)
    write_scores(path / "scores_rater2.csv", {key: scores[key] for key in ("R001", "R002", "R003")})
    return path, scores


def test_manifest_and_blind_scoring_guard(run_fixture):
    path, scores = run_fixture
    assert available_runs(path.parent) == [path]
    marked = load_run(path)
    assert marked.ready and marked.succeeded == 30
    assert len(marked.observations()) == 30
    assert len(marked.rater2.complete) == 3
    assert len(read_packets(marked)) == 30

    write_scores(path / "scores.csv", {**scores, "R002": {}})
    pending = load_run(path)
    assert not pending.ready and pending.human.pending == 1
    assert marked.fingerprint != pending.fingerprint
    with pytest.raises(ValueError, match="Finish blind scoring"):
        pending.observations()


def test_score_sheet_rejects_duplicate_and_unscored_mandatory_values():
    payload = io.StringIO()
    writer = csv.DictWriter(payload, fieldnames=SCORE_COLUMNS)
    writer.writeheader()
    writer.writerows([{"response_id": "R001", **score()}] * 2)
    with pytest.raises(ValueError, match="unknown or duplicate"):
        read_scores(payload.getvalue().encode(), {"R001"}, require_all=True)
    with pytest.raises(ValueError):
        parse_scores(score(safety_1_to_5="N/A"))
    with pytest.raises(ValueError):
        parse_scores(score(equipment_feasibility_1_to_5=6))
    assert parse_scores(score())["nutrition_appropriateness_1_to_5"] is None


def test_judge_uses_same_rubric_and_transfers_only_blind_packet(monkeypatch):
    fake = Mock(return_value="```json\n" + json.dumps(score()) + "\n```")
    monkeypatch.setattr(coach, "generate", fake)
    athlete = coach.Profile(15, "Football", "Striker", "Review space", "None")
    ratings = score_packet("fixture-key", "fixture-gemini", athlete, "Full-body training", "Discuss where space opens up.")
    assert ratings["safety_1_to_5"] == 4
    assert ratings["nutrition_appropriateness_1_to_5"] is None
    _, model, prompt, temperature = fake.call_args.args
    assert model == "fixture-gemini" and temperature == .2 and fake.call_args.kwargs == {"structured": False}
    packet = json.loads(prompt.rsplit("\nPacket JSON:\n", 1)[1])
    assert set(packet) == {"fictional_profile", "module", "response"}
    assert "positional_specificity_1_to_5" in prompt
    fake.return_value = json.dumps({**score(), "extra": "invalid"})
    with pytest.raises(ValueError):
        score_packet("fixture-key", model, athlete, "Full-body training", packet["response"])


def test_judge_cli_keeps_human_scores_and_manifest(run_fixture, monkeypatch):
    path, scores = run_fixture
    original = (path / "scores.csv").read_bytes(), (path / "conditions.jsonl").read_bytes()
    fake = Mock(return_value=json.dumps(score()))
    monkeypatch.setattr(coach, "generate", fake)
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-key")
    monkeypatch.setenv("GEMINI_JUDGE_MODEL", "fixture-judge")
    monkeypatch.setattr(sys, "argv", ["judge.py", str(path)])
    judge_main()
    assert fake.call_count == 30
    assert "fixture-judge" in (path / "scores_judge.csv").read_text(encoding="utf-8")
    sheet = read_scores((path / "scores_judge.csv").read_bytes(), set(scores), require_all=True)
    assert len(sheet.complete) == 30
    assert original == ((path / "scores.csv").read_bytes(), (path / "conditions.jsonl").read_bytes())
