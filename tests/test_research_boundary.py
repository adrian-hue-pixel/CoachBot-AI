import ast
from collections import Counter
import csv
import json
import os
from pathlib import Path
import sys

import pytest

import evaluate

ROOT = Path(__file__).resolve().parents[1]


def test_public_app_never_imports_offline_runners():
    violations = []
    for folder, subfolders, filenames in os.walk(ROOT):
        subfolders[:] = [
            name for name in subfolders
            if not name.startswith(".") and name not in {"tests", "__pycache__", "evaluation_runs", "venv"}
        ]
        for filename in filenames:
            source = Path(folder) / filename
            if source.suffix != ".py" or source == ROOT / "evaluate.py":
                continue
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.Import | ast.ImportFrom):
                    modules.extend(alias.name for alias in node.names)
                    if isinstance(node, ast.ImportFrom):
                        modules.append(node.module or "")
                if isinstance(node, ast.Call) and node.args:
                    function = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    target = node.args[0]
                    if function in {"__import__", "import_module", "run_module", "run_path"} and isinstance(target, ast.Constant):
                        modules.append(str(target.value).removesuffix(".py").replace("/", "."))
                if any({"evaluate", "run_evaluation", "ablate", "judge", "redteam"}.intersection(name.split(".")) for name in modules):
                    violations.append(f"{source.relative_to(ROOT)}:{node.lineno}")
    assert not violations


def test_evaluator_has_only_inline_literal_profiles():
    tree = ast.parse((ROOT / "evaluate.py").read_text(encoding="utf-8"))
    fixtures = next(
        node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "PROFILES" for target in node.targets)
    )
    assert isinstance(fixtures, ast.List)
    assert len(fixtures.elts) == 10
    for fixture in fixtures.elts:
        assert isinstance(fixture, ast.Call) and isinstance(fixture.func, ast.Name)
        assert fixture.func.id == "Profile"
        assert all(isinstance(arg, ast.Constant) for arg in fixture.args)
        assert all(isinstance(keyword.value, ast.Constant) for keyword in fixture.keywords)


def test_evaluator_only_sends_synthetic_cases_and_keeps_output_layout(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(sys, "argv", ["evaluate.py", "--temperature-check"])
    calls = []

    def generate_stub(api_key, model, message, temperature, *, structured):
        calls.append((model, message, temperature, structured))
        return "Synthetic review output."

    monkeypatch.setattr(evaluate, "generate", generate_stub)
    evaluate.main()

    (run,) = (tmp_path / "evaluation_runs").iterdir()
    with (run / "conditions.jsonl").open(encoding="utf-8") as conditions:
        cases = [json.loads(line) for line in conditions]
    with (run / "scores.csv").open(encoding="utf-8", newline="") as scores:
        assert [row["response_id"] for row in csv.DictReader(scores)] == [case["id"] for case in cases]
    assert len(cases) == len(calls) == len(list(run.glob("R*.txt"))) == 43
    assert Counter(case["experiment"] for case in cases) == {"prompt": 30, "allergy": 3, "temperature": 10}
    for case, (model, message, temperature, structured) in zip(cases, calls, strict=True):
        profile = evaluate.PROFILES[case["fixture"] - 1]
        assert message == case["prompt"] == evaluate.prompt(profile, case["module"], case["version"])
        assert model == case["model"] == evaluate.DEFAULT_MODEL
        assert temperature == case["temperature"]
        assert structured is False


def test_evaluator_rejects_a_profile_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    monkeypatch.setattr(sys, "argv", ["evaluate.py", "--profile", "athlete.json"])
    with pytest.raises(SystemExit, match="2"):
        evaluate.main()
    assert not (tmp_path / "evaluation_runs").exists()
