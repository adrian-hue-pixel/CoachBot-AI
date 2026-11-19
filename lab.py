"""Prompt Lab. Only aggregate, unblinded results reach the browser."""

from collections import Counter
from difflib import SequenceMatcher
from html import escape
from pathlib import Path
import re
from statistics import mean

import plotly.graph_objects as go
import streamlit as st

from ablation_data import available_ablation_runs, load_ablation_run, summarize_ablation
from lab_data import (CONTRAINDICATED, CRITERIA, EXPERIMENTS, RATINGS, VERSIONS,
                      available_runs, load_run, read_packets, read_scores)
from lab_stats import paired_summary, prompt_groups, rater_summary, temperature_summary
from lint_validation import HELD_OUT_SHA256, REGRESSION_CASES, benchmark_summary, held_out_cases
from safety import lint_output

RUNS_ROOT = Path(__file__).with_name("evaluation_runs")
ABLATION_ROOT = Path(__file__).with_name("ablation_runs")
COLORS = ("#83B9FE", "#F5B942", "#57D69A")


def offline_linter_summary(run, packets):
    groups = []
    for experiment, label in EXPERIMENTS.items():
        ids = [id_ for id_, row in run.conditions.items()
               if row["experiment"] == experiment and row["version"] == "V3" and row["status"] == "ok"]
        if not ids:
            continue
        flags = [lint_output(packets[id_][1], packets[id_][0]) for id_ in ids if id_ in packets]
        categories = Counter(category for result in flags for category in result)
        groups.append({
            "Experiment": label, "Successful V3": len(ids), "Packets checked": len(flags),
            "Flagged": sum(bool(result) for result in flags),
            "Rule hits": ", ".join(f"{key.replace('_', ' ')} ({count})" for key, count in sorted(categories.items())) or "None",
        })
    return groups


def _rounded(value, digits=4):
    return round(value, digits) if value is not None else None


def _table(rows):
    st.dataframe(rows, hide_index=True, width="stretch")


def _chart(figure, reduce_motion):
    figure.update_layout(transition={"duration": 0 if reduce_motion else 500, "easing": "cubic-in-out"},
                         margin={"l": 20, "r": 20, "t": 52, "b": 40},
                         legend={"orientation": "h", "yanchor": "bottom", "y": 1.03})
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def _rating_values(rows, version, criterion):
    return [row[criterion] for row in rows if row["version"] == version and row[criterion] is not None]


def _prompt_charts(rows, reduce_motion):
    means, radar, counts = go.Figure(), go.Figure(), go.Figure()
    criteria = list(RATINGS.values())
    table = []
    for index, (version, color) in enumerate(zip(VERSIONS, COLORS)):
        values = [_rating_values(rows, version, field) for field in RATINGS]
        aggregates = [mean(scores) if scores else None for scores in values]
        n = [len(scores) for scores in values]
        means.add_bar(name=version, x=criteria, y=aggregates, marker_color=color, customdata=n,
                      hovertemplate="%{x}<br>Mean %{y:.2f}<br>n=%{customdata}<extra>%{fullData.name}</extra>")
        radar.add_trace(go.Scatterpolar(name=version, theta=criteria + criteria[:1],
                                       r=aggregates + aggregates[:1], mode="lines+markers", line={"color": color}))
        amounts = _rating_values(rows, version, CONTRAINDICATED)
        counts.add_scatter(name=version, x=[index + (i - (len(amounts) - 1) / 2) * .035 for i in range(len(amounts))],
                           y=amounts, marker={"color": color, "size": 9}, mode="markers",
                           hovertemplate="%{y} actions<extra>%{fullData.name}</extra>")
        table.extend({"Version": version, "Criterion": criterion, "Mean": _rounded(score), "n": size}
                     for criterion, score, size in zip(criteria, aggregates, n, strict=True))
    means.update_layout(title="Mean rubric ratings", barmode="group",
                        yaxis={"title": "Rating", "range": [0, 5.25], "dtick": 1})
    radar.update_layout(title="Rubric profiles", polar={"radialaxis": {"range": [1, 5], "dtick": 1}})
    counts.update_layout(title="Contraindicated actions per response", yaxis={"title": "Count", "dtick": 1},
                         xaxis={"tickvals": [0, 1, 2], "ticktext": list(VERSIONS)}, showlegend=False)
    for figure in (means, radar, counts):
        _chart(figure, reduce_motion)
    with st.expander("Chart data"):
        _table(table)
        _table([{"Version": version, "Counts by response": ", ".join(map(str, amounts))}
                for version in VERSIONS if (amounts := _rating_values(rows, version, CONTRAINDICATED))])


def _paired_statistics(rows):
    st.subheader("Paired V3 − V1 analysis")
    st.caption("Planned n=10 fictional profiles. Each row reports the number of matched profiles with both scores. "
               "The allergy challenge and temperature repeats sit outside this comparison.")
    result = paired_summary(rows)
    if any(row["notice"] == "Wilcoxon unavailable" for row in result):
        st.info("Wilcoxon unavailable for one or more criteria. The NumPy bootstrap intervals remain available.")
    _table([{
        "Criterion": CRITERIA[row["criterion"]], "Paired n": row["n"],
        "Mean difference": _rounded(row["mean_difference"]), "95% CI low": _rounded(row["lower"]),
        "95% CI high": _rounded(row["upper"]), "Rank-biserial r": _rounded(row["rank_biserial"]),
        "Wilcoxon W": _rounded(row["wilcoxon_w"]), "Raw p": _rounded(row["p"]),
        "Holm p": _rounded(row["holm_p"]), "Status": row["notice"],
    } for row in result])
    st.caption("Bootstrap intervals use 5,000 paired resamples of the mean difference. Signed-rank tests are two-sided. "
               "Intervals are per criterion. Holm correction applies to p-values across all six planned outcomes. Positive effects favor higher ratings, "
               "while positive contraindication counts indicate more contraindicated actions. Small samples limit inference.")


def _highlight(previous, updated):
    before = re.findall(r"\S+|\s+", previous)
    after = re.findall(r"\S+|\s+", updated)
    parts = []
    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    for operation, _, _, start, end in matcher.get_opcodes():
        body = escape("".join(after[start:end]))
        parts.append(f"<mark>{body}</mark>" if operation in ("replace", "insert") else body)
    return "".join(parts)


def _prompt_diff(rows):
    st.subheader("Prompt diff")
    fixtures = sorted({row["fixture"] for row in rows})
    chosen = st.selectbox("Fictional profile", fixtures, format_func=lambda value: f"Profile {value}", key="cb_lab_fixture")
    prompts = {row["version"]: row["prompt"] for row in rows if row["fixture"] == chosen}
    st.caption("Highlights show additions or replacements relative to the preceding available version.")
    previous = ""
    for column, version in zip(st.columns(3), VERSIONS, strict=True):
        with column:
            st.markdown(f"**{version}**")
            text = prompts.get(version)
            if text is None:
                st.caption("Prompt unavailable for this profile.")
                continue
            display = _highlight(previous, text) if previous else escape(text)
            st.html(f'<pre class="cb-prompt-diff">{display}</pre>')
            previous = text


def _agreement(run):
    if run.rater2:
        st.subheader("Human inter-rater agreement")
        _table([{"Criterion": CRITERIA[row["criterion"]], "Responses paired": row["n"],
                 "Quadratic-weighted κ": _rounded(row["kappa"])}
                for row in rater_summary(run.human.complete, run.rater2.complete)])
        st.caption("Ratings use the 1–5 scale. Each row includes responses both raters scored; N/A cells are omitted.")
    path = run.path / "scores_judge.csv"
    if path.is_file():
        st.subheader("Gemini judge comparison")
        st.caption("Secondary evidence, not ground truth.")
        try:
            other = read_scores(path.read_bytes(), set(run.human.complete), require_all=False)
        except (OSError, ValueError):
            st.warning("The judge score sheet could not be read.")
            return
        if not other.complete:
            st.info("The judge score sheet has no completed ratings.")
            return
        _table([{"Criterion": CRITERIA[row["criterion"]], "Responses paired": row["n"],
                 "Quadratic-weighted κ": _rounded(row["kappa"]), "Mean absolute difference": _rounded(row["mae"]),
                 "Mean judge − human": _rounded(row["bias"])}
                for row in rater_summary(run.human.complete, other.complete)])
        human = run.human.complete
        ids = sorted(human.keys() & other.complete.keys())
        differences = [other.complete[id_][CONTRAINDICATED] - human[id_][CONTRAINDICATED] for id_ in ids]
        if differences:
            st.caption(f"Contraindication counts · {len(differences)} paired responses · "
                       f"Mean absolute difference {mean(map(abs, differences)):.2f}")


def _temperature(observations, packets):
    st.subheader("Temperature consistency")
    rows = temperature_summary(observations, packets)
    if not rows:
        st.info("This run has no scored temperature repeats.")
        return
    agreement = [row for row in rows if row["criterion"] == "safety_1_to_5"]
    _table([{"Model": row["model"], "Profile": row["fixture"], "Module": row["module"],
             "Version": row["version"], "Top-p": row["top_p"], "Temperature": row["temperature"],
             "Packets": row["packets_n"], "Repeat pairs": row["jaccard_pairs"],
             "Mean token-set Jaccard": _rounded(row["jaccard_mean"])} for row in agreement])
    _table([{"Model": row["model"], "Profile": row["fixture"], "Module": row["module"],
             "Version": row["version"], "Top-p": row["top_p"], "Temperature": row["temperature"],
             "Criterion": CRITERIA[row["criterion"]], "Scored repeats": row["scored_n"],
             "Score SD": _rounded(row["score_sd"])} for row in rows])
    st.caption("The pilot uses one fictional profile, with five planned repeats per temperature. "
               "Jaccard averages token-set overlap across every available repeat pair. Score SD uses the sample formula.")


def _limits():
    with st.expander("Limitations"):
        st.markdown(
            "- The app uses self-reported inputs and has no clinical validation.\n"
            "- The planned comparison includes n=10 fictional profiles. Missing or inapplicable scores can reduce the paired sample.\n"
            "- Model behavior can drift between runs. Results apply to the recorded model and settings.\n"
            "- The offline evaluator deliberately bypasses public safety gates to measure raw outputs from fictional profiles. "
            "Review packets stay local and this tab shows aggregates.\n"
            "- The Gemini judge shares the generator's model family by default. A judge from the same family may favor its own outputs.\n"
            "- Pre-call gates, prompt constraints and the check-in rule are the primary controls. The linter is a backstop for known phrasings. "
            "Named movement restrictions flag mentions even in tactical discussion.\n"
            "- An independent spot-check, using 14 unsafe phrasings written outside the development and held-out sets, found that the linter flagged 4 of 14 (28.6%). "
            "The synthetic benchmarks describe their own cases. Recall on real model outputs is pending human labelling under the README protocol."
        )


def _interval_text(interval):
    return f"{interval[0]:.1%}–{interval[1]:.1%}" if interval else "Undefined"


def _linter_benchmarks():
    with st.expander("Linter benchmarks"):
        sets = [("regression", REGRESSION_CASES)]
        try:
            sets.append(("held-out", held_out_cases()))
        except (OSError, ValueError, TypeError):
            st.warning("The frozen held-out file could not be verified.")
        results = []
        for label, cases in sets:
            stats = benchmark_summary(cases)
            results.append({
                "Set": label, "n": stats["n"], "Precision": _rounded(stats["precision"]),
                "Precision n": stats["precision_n"], "Precision Wilson 95%": _interval_text(stats["precision_ci"]),
                "Recall": _rounded(stats["recall"]), "Recall n": stats["recall_n"],
                "Recall Wilson 95%": _interval_text(stats["recall_ci"]),
                "TP": stats["tp"], "FP": stats["fp"], "TN": stats["tn"], "FN": stats["fn"],
            })
        _table(results)
        st.caption("The regression set guided tuning. The synthetic held-out set was frozen before tuning. "
                   "Precision measures how often a flag matched an unsafe label. Recall measures how many unsafe cases were flagged.")
        st.caption(f"Held-out SHA-256 · {HELD_OUT_SHA256}")


def _ablation_table(rows):
    return [{"Fixtures": row["cohort"], "Arm": row["arm"], "Measure": row["metric"].replace("_", " "),
             "Evidence": row["source"],
             "n": row["n"], "Mean or rate": _rounded(row["mean"], 6),
             "Bootstrap 95% CI": " to ".join(f"{bound:.6g}" for bound in row["ci"]) if row["ci"] else "Unavailable"}
            for row in rows]


def _ablation():
    with st.expander("Layered-defence ablation"):
        st.caption("Exploratory study · One module and up to ten fictional fixtures.")
        runs = available_ablation_runs(ABLATION_ROOT)
        if not runs:
            st.info("No ablation run found. Run the fictional study and complete its blind score sheet.")
            return
        path = st.selectbox("Ablation run", runs, format_func=lambda value: value.name, key="cb_ablation_run")
        try:
            run = load_ablation_run(path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
            st.warning("The ablation run or its blind score sheet could not be read.")
            return
        st.caption(f"Blind scoring · {len(run.scores)} of {len(run.conditions)} complete.")
        if not run.ready:
            st.info("Give raters only the blind packets and score sheet. Use N/A for unavailable labels before unblinding.")
            return
        if st.session_state.get("cb_ablation_unblinded") != run.fingerprint:
            if not st.button("Confirm ablation scoring is complete and unblind", key="cb_ablation_unblind"):
                return
            st.session_state.cb_ablation_unblinded = run.fingerprint
        paused = len(run.paused_fixtures)
        st.caption(f"Gate-inclusive n={run.fixture_count} per arm. Matched n={run.fixture_count - paused} per arm, "
                   f"excluding the same {paused} pre-call pauses from all arms. Intervals resample profiles within each arm.")
        if run.schema == 1:
            st.warning("Legacy run with the original packet layouts. Generate a new run for the uniform packet format.")
        if run.source == "replay":
            st.warning("Scripted offline replay. These results exercise the study workflow. Gemini latency, usage and cost were not measured.")
        else:
            st.caption(f"Model · {run.model}. Latency excludes the cooldown. USD estimates use the rates supplied for the run.")
        results = []
        for exclude, cohort in ((True, "Matched non-paused fixtures"), (False, "All fixtures (gate-inclusive)")):
            outcomes, violations = summarize_ablation(run, exclude_paused=exclude)
            results.extend({**row, "cohort": cohort} for row in (*outcomes, *violations))
        st.markdown("**Human labels · Safety and positional specificity**")
        human = [row for row in results if row["source"] == "Human"]
        if not any(row["n"] for row in human):
            st.info("No human labels were available for this run.")
        _table(_ablation_table(human))
        st.markdown("**Latency, token use and pipeline outcomes**")
        _table(_ablation_table(row for row in results if row["source"] in ("Measured", "Price estimate", "Pipeline")))
        st.markdown("**Linter proxy · Circular by design**")
        st.caption("The same linter helps produce some arms and rates their outputs here. These proxy rates are not independent safety evidence.")
        _table(_ablation_table(row for row in results if row["source"] == "Linter proxy"))
        st.markdown("**Literal role mentions · Text-match proxy**")
        st.caption("A role mention alone does not measure useful role advice.")
        _table(_ablation_table(row for row in results if row["source"] == "Literal-match proxy"))
        st.caption("The constrained arm includes the pre-call profile gates. Raw and layered free-text arms bypass them on fictional inputs. "
                   "Wording may still suggest an arm. Present fallback rates alongside specificity. "
                   "The Gemini verifier may share the generator’s biases.")


def render_lab(reduce_motion):
    with st.container(key="cb_lab"):
        st.subheader("Prompt Lab")
        _limits()
        _linter_benchmarks()
        _ablation()
        live = st.session_state.get("cb_safety_outcomes")
        if live:
            with st.expander("Live safety checks this session"):
                _table([{"Passed": live["passed"], "Regenerated": live["regenerated"], "Fallback": live["fallback"]}])
        runs = available_runs(RUNS_ROOT)
        if not runs:
            st.info("No evaluation run found. Run the offline evaluator and complete the blind score sheet to unlock comparisons.")
            return
        run_path = st.selectbox("Evaluation run", runs, format_func=lambda value: value.name, key="cb_lab_run")
        try:
            run = load_run(run_path)
        except (OSError, ValueError, TypeError):
            st.warning("The run could not be read. Check its manifest and rubric score sheets.")
            return
        st.caption(f"Human scoring · {len(run.human.complete)} of {run.succeeded} successful responses complete. "
                   f"{len(run.conditions) - run.succeeded} generation errors.")
        if run.rater2 is not None:
            st.caption(f"Second rater · {len(run.rater2.complete)} completed responses and {run.rater2.pending} pending.")
        sealed = st.session_state.get("cb_unblinded_run") == run.fingerprint
        if not run.ready:
            st.info("Finish blind scoring first. Use the numbered review packets and the rubric sheet. "
                    "Enter N/A for inapplicable ratings.")
            return
        if not sealed:
            if not st.button("Confirm blind scoring is complete and unblind", key="cb_lab_unblind"):
                return
            st.session_state.cb_unblinded_run = run.fingerprint

        observations = run.observations()
        packets = read_packets(run)
        if len(packets) < run.succeeded:
            st.warning("Some review packets are unavailable. Packet-based analyses use the available responses.")
        groups = prompt_groups(observations)
        if groups:
            group = st.selectbox("Prompt comparison cohort", list(groups), format_func=lambda item: " · ".join(item),
                                 key="cb_lab_cohort")
            rows = groups[group]
            _prompt_charts(rows, reduce_motion)
            _paired_statistics(rows)
            _prompt_diff(rows)
        st.subheader("V3 + linter (offline)")
        st.caption("The linter checks the stored V3 responses for measurement only. Raw V1/V2/V3 scores stay separate.")
        offline = offline_linter_summary(run, packets)
        if offline:
            _table(offline)
        else:
            st.info("This run has no successful V3 responses.")
        _temperature(observations, packets)
        _agreement(run)
