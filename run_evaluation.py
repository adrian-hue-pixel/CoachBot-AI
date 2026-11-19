"""Run the unchanged fictional evaluator and publish one reproducibility manifest per model."""

import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

from coach import DEFAULT_MODEL
from evaluation_manifest import MODEL_ID, parse_run_manifest, prompt_hashes
from lab_data import read_conditions
from lab_stats import BOOTSTRAP_SEED

ROOT = Path(__file__).resolve().parent
EVALUATOR = ROOT / "evaluate.py"


def evaluator_shuffle_seed(source):
    seeds = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "shuffle":
            continue
        factory = node.func.value
        if (isinstance(factory, ast.Call) and isinstance(factory.func, ast.Attribute)
                and isinstance(factory.func.value, ast.Name) and factory.func.value.id == "random"
                and factory.func.attr == "Random" and len(factory.args) == 1 and isinstance(factory.args[0], ast.Constant)
                and type(factory.args[0].value) is int):
            seeds.append(factory.args[0].value)
    if len(seeds) != 1:
        raise ValueError("Could not identify the evaluator's fixed shuffle seed.")
    return seeds[0]


def package_versions():
    packages = {}
    for name in ("google-genai", "streamlit", "numpy", "pandas", "scipy", "plotly", "pytest", "playwright"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return packages


def git_revision():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.DEVNULL).strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() == ROOT:
            return git("rev-parse", "HEAD"), bool(git("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError):
        pass
    return None, None


def run_model(model, output_root, limit, temperature_check):
    if not MODEL_ID.fullmatch(model):
        raise ValueError("Use a valid model identifier.")
    evaluator_bytes = EVALUATOR.read_bytes()
    shuffle = evaluator_shuffle_seed(evaluator_bytes)
    commit, dirty = git_revision()
    packages = package_versions()
    started = datetime.now(timezone.utc).isoformat()
    output_root.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", str(EVALUATOR), "--limit", str(limit)]
    if temperature_check:
        command.append("--temperature-check")
    with TemporaryDirectory(dir=output_root, prefix=".evaluation-") as temp:
        environment = os.environ.copy() | {"GEMINI_MODEL": model}
        subprocess.run(command, cwd=temp, env=environment, check=True)
        (run,) = (Path(temp) / "evaluation_runs").iterdir()
        conditions = read_conditions((run / "conditions.jsonl").read_bytes())
        expected_count = 3 * limit + (3 if limit >= 7 else 0) + (10 if temperature_check else 0)
        if EVALUATOR.read_bytes() != evaluator_bytes:
            raise ValueError("The evaluator changed while it was running.")
        metadata = {
            "schema": 1, "model_id": model, "timestamp_utc": started, "python": platform.python_version(),
            "packages": packages, "git_commit": commit, "git_dirty": dirty,
            "evaluator_sha256": sha256(evaluator_bytes).hexdigest(),
            "seeds": {"evaluator_shuffle": shuffle, "analysis_bootstrap": BOOTSTRAP_SEED, "gemini_request": None},
            "settings": {"limit": limit, "temperature_check": temperature_check},
            "recorded_conditions": len(conditions), "planned_conditions": expected_count,
            "prompt_sha256": prompt_hashes(conditions),
        }
        raw = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
        parse_run_manifest(raw, conditions)
        (run / "run_manifest.json").write_bytes(raw)
        destination = output_root / run.name
        if destination.exists():
            raise FileExistsError("An evaluation run already uses the generated timestamp.")
        run.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Model identifier. Use up to two distinct identifiers.")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=10)
    parser.add_argument("--temperature-check", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("evaluation_runs"))
    args = parser.parse_args()
    models = args.model or [os.getenv("GEMINI_MODEL") or DEFAULT_MODEL]
    if not 1 <= len(models) <= 2 or len(set(models)) != len(models) or not all(MODEL_ID.fullmatch(model) for model in models):
        parser.error("Use one or two distinct model identifiers.")
    if not os.getenv("GEMINI_API_KEY"):
        parser.error("Set GEMINI_API_KEY in your environment.")
    for model in models:
        try:
            destination = run_model(model, args.output_root, args.limit, args.temperature_check)
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            parser.exit(1, f"Could not publish a run for {model} ({type(error).__name__}).\n")
        print(f"Review packets and manifest: {destination}")


if __name__ == "__main__":
    main()
