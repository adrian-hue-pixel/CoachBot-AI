import json
from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest

import ablate
from exercise_bank import load_bank
import lab
from lab_data import load_run, read_packets
from test_ablation import score_run
from test_lab_data import run_fixture, score, write_scores


def test_offline_arm_keeps_raw_scores_separate(run_fixture):
    path, _ = run_fixture
    run = load_run(path)
    before = (path / "conditions.jsonl").read_bytes(), (path / "scores.csv").read_bytes()
    output = lab.offline_linter_summary(run, read_packets(run))
    assert output == [{"Experiment": "Prompt comparison", "Successful V3": 10, "Packets checked": 10,
                       "Flagged": 1, "Rule hits": "supplements (1)"}]
    assert before == ((path / "conditions.jsonl").read_bytes(), (path / "scores.csv").read_bytes())


def test_lab_only_unblinds_scored_run_after_confirmation_and_honors_motion(run_fixture, monkeypatch):
    path, scores = run_fixture
    monkeypatch.setattr(lab, "RUNS_ROOT", path.parent)
    monkeypatch.setitem(sys.modules, "scipy.stats", None)
    script = "from lab import render_lab\nimport streamlit as st\nrender_lab(st.toggle('Reduce motion'))"
    app = AppTest.from_string(script, default_timeout=10)
    write_scores(path / "scores.csv", {**scores, "R001": {}})
    app.run()
    assert not app.exception and not app.get("plotly_chart") and not app.button
    assert any("Finish blind scoring first" in item.value for item in app.info)

    write_scores(path / "scores.csv", scores)
    write_scores(path / "scores_judge.csv", {key: scores[key] for key in ("R001", "R002", "R003")})
    app.run()
    assert not app.exception and not app.get("plotly_chart")
    next(button for button in app.button if "unblind" in button.label).click().run()
    assert not app.exception
    assert len(app.get("plotly_chart")) == 3
    assert any("Wilcoxon unavailable" in item.value for item in app.info)
    assert any(item.value == "V3 + linter (offline)" for item in app.subheader)
    assert any("Secondary evidence, not ground truth." == item.value for item in app.caption)
    assert "Take creatine before this match." not in str(app)
    assert any("<mark>" in item.proto.body for item in app.get("html"))
    assert all(json.loads(chart.proto.spec)["layout"]["transition"]["duration"] == 500
               for chart in app.get("plotly_chart"))
    app.toggle[0].set_value(True).run()
    assert all(json.loads(chart.proto.spec)["layout"]["transition"]["duration"] == 0
               for chart in app.get("plotly_chart"))
    write_scores(path / "scores.csv", {**scores, "R001": score(safety_1_to_5=5)})
    app.run()
    assert not app.get("plotly_chart")
    assert any("unblind" in button.label for button in app.button)


def test_app_exposes_prompt_lab_with_no_configured_key_or_runs(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "RUNS_ROOT", tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    app.secrets["GEMINI_API_KEY"] = ""
    app.run()
    assert not app.exception
    assert any(tab.label == "Prompt Lab" for tab in app.tabs)
    assert all(item.value != "Prompt Lab" for item in app.subheader)
    app.session_state["cb_sections"] = "Prompt Lab"
    app.run()
    assert not app.exception
    assert any("No evaluation run found" in item.value for item in app.info)
    assert any(item.label == "Limitations" for item in app.expander)
    assert any("may favor its own outputs" in item.value for item in app.markdown)
    assert any("An independent spot-check, using 14 unsafe phrasings written outside the development and held-out sets, found that the linter flagged 4 of 14 (28.6%)" in item.value for item in app.markdown)
    report = app.dataframe[0].value.set_index("Set")
    assert list(report.index) == ["regression", "held-out"]
    assert report.loc["regression", "n"] == 67
    assert report.loc["held-out", "n"] == 24
    assert "Recall Wilson 95%" in report.columns


def test_prompt_lab_releases_only_ablation_aggregates_after_blind_confirmation(monkeypatch, tmp_path):
    path = ablate.write_run(tmp_path, 2, load_bank())
    monkeypatch.setattr(lab, "ABLATION_ROOT", tmp_path)
    monkeypatch.setattr(lab, "RUNS_ROOT", tmp_path / "no-original-run")
    app = AppTest.from_string("from lab import render_lab\nrender_lab(True)").run()
    assert not app.exception and len(app.dataframe) == 2 and not app.button
    assert any("only the blind packets" in item.value for item in app.info)

    score_run(path)
    app.run()
    assert len(app.dataframe) == 2 and len(app.button) == 1
    app.button[0].click().run()
    assert not app.exception and len(app.dataframe) == 6
    assert any("Scripted offline replay" in item.value for item in app.warning)
    summary = app.dataframe[1].value
    assert {"Human"} == set(summary["Evidence"])
    assert {"Matched non-paused fixtures", "All fixtures (gate-inclusive)"} == set(summary["Fixtures"])
    assert {"Linter proxy"} == set(app.dataframe[3].value["Evidence"])
    assert any("Circular by design" in item.value for item in app.markdown)
    assert "Positional specificity (1–5)" in set(summary["Measure"])
    assert "Bootstrap 95% CI" in summary
    assert "Use a jumping drill during practice." not in str(app)

    score_run(path, labels=False)
    app.run()
    assert len(app.dataframe) == 2 and len(app.button) == 1


def test_prompt_lab_shows_aggregate_offline_policy_results(monkeypatch, tmp_path):
    monkeypatch.setattr(lab, "ABLATION_ROOT", tmp_path)
    monkeypatch.setattr(lab, "RUNS_ROOT", tmp_path)
    app = AppTest.from_string("from lab import render_lab\nrender_lab(True)").run()
    assert not app.exception
    table = next(row.value for row in app.dataframe if "Wilson 95% CI" in row.value and "Set" in row.value and "Category" in row.value)
    expected = lab.load_redteam_report()
    assert table["Cases"].sum() == 88
    assert table["Mismatches"].tolist() == [row["Mismatches"] for row in expected]
    assert any("Authored synthetic policy cases" in caption.value for caption in app.caption)
    assert "Can I share my birth date" not in str(app)
