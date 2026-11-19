from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from lab_data import load_run
import run_evaluation
from test_lab_data import run_fixture


def test_wrapper_runs_two_models_and_keeps_manifests_separate(run_fixture, tmp_path, monkeypatch, capsys):
    source, _ = run_fixture
    output_root = tmp_path / "published"
    calls = []
    evaluator_before = run_evaluation.EVALUATOR.read_bytes()

    def run(command, *, cwd, env, check):
        model = env["GEMINI_MODEL"]
        assert env["GEMINI_API_KEY"] == "private-mock-key"
        assert check and Path(command[2]) == run_evaluation.EVALUATOR
        assert command[-3:] == ["--limit", "10", "--temperature-check"]
        calls.append(model)
        run_path = Path(cwd) / "evaluation_runs" / f"synthetic-{len(calls)}"
        run_path.mkdir(parents=True)
        rows = [json.loads(line) for line in (source / "conditions.jsonl").read_text().splitlines()]
        (run_path / "conditions.jsonl").write_text("\n".join(json.dumps({**row, "model": model}) for row in rows))
        (run_path / "scores.csv").write_bytes((source / "scores.csv").read_bytes())

    monkeypatch.setattr(run_evaluation.subprocess, "run", run)
    monkeypatch.setattr(run_evaluation, "git_revision", lambda: ("a" * 40, False))
    monkeypatch.setenv("GEMINI_API_KEY", "private-mock-key")
    monkeypatch.setattr(sys, "argv", ["run_evaluation.py", "--model", "first-model", "--model", "second-model",
                                     "--temperature-check", "--output-root", str(output_root)])
    run_evaluation.main()
    assert calls == ["first-model", "second-model"]
    for index, model in enumerate(calls, 1):
        run_path = output_root / f"synthetic-{index}"
        manifest_file = run_path / "run_manifest.json"
        raw = manifest_file.read_text()
        manifest = load_run(run_path).manifest
        assert "private-mock-key" not in raw
        assert manifest["model_id"] == model
        assert manifest["git_commit"] == "a" * 40 and not manifest["git_dirty"]
        assert manifest["seeds"] == {"evaluator_shuffle": 103, "analysis_bootstrap": 103, "gemini_request": None}
        assert manifest["evaluator_sha256"] == sha256(evaluator_before).hexdigest()
        assert manifest["planned_conditions"] == 43 and manifest["recorded_conditions"] == 31
        assert set(manifest["packages"]) >= {"google-genai", "numpy", "scipy"}
        assert len(manifest["prompt_sha256"]) == 31 and len(manifest["prompt_sha256"]["R001"]) == 64
        assert manifest["timestamp_utc"].endswith("+00:00")
        assert "Synthetic profile" not in raw
        manifest["prompt_sha256"]["R001"] = "b" * 64
        manifest_file.write_text(json.dumps(manifest))
        with pytest.raises(ValueError, match="does not match"):
            load_run(run_path)
    assert run_evaluation.EVALUATOR.read_bytes() == evaluator_before
    assert "private-mock-key" not in capsys.readouterr().out
    assert sorted(p.name for p in output_root.iterdir()) == ["synthetic-1", "synthetic-2"]


def test_wrapper_rejects_repeated_models_before_a_run(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_evaluation.py", "--model", "same", "--model", "same"])
    with pytest.raises(SystemExit) as error:
        run_evaluation.main()
    assert error.value.code == 2
