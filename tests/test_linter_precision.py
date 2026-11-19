from dataclasses import replace

import pytest

from coach import Profile
from lint_validation import (HELD_OUT_PATH, HELD_OUT_SHA256, REGRESSION_CASES, benchmark_summary,
                             held_out_cases, wilson_interval)
from safety import lint_output

ATHLETE = Profile(15, "Football", "Striker", "Review match decisions", "None")


@pytest.mark.parametrize("case", REGRESSION_CASES)
def test_labelled_linter_cases(case):
    athlete = replace(ATHLETE, restrictions=case.restrictions)
    flags = lint_output(case.text, athlete, sport_scope=case.sport_scope, rest_only=case.rest_only)
    assert bool(flags) == case.unsafe


def test_counts_and_metrics_are_computed_from_flags():
    result = benchmark_summary(REGRESSION_CASES)
    assert result["n"] == len(REGRESSION_CASES)
    assert result["tp"] + result["fp"] == result["precision_n"]
    assert result["tp"] + result["fn"] == result["recall_n"]
    assert result["precision"] == result["recall"] == 1
    assert result["precision_ci"][0] < 1
    assert wilson_interval(0, 0) is None
    assert wilson_interval(5, 10) == pytest.approx((0.2366, 0.7634), abs=0.0001)


def test_frozen_held_out_is_distinct_and_hash_pinned():
    from hashlib import sha256

    assert sha256(HELD_OUT_PATH.read_bytes()).hexdigest() == HELD_OUT_SHA256
    held = held_out_cases()
    assert len(held) == 24
    assert {case.text for case in held}.isdisjoint(case.text for case in REGRESSION_CASES)
    assert {case.unsafe for case in held} == {True, False}


def test_forbidden_movement_and_dosage_are_separate_checks():
    athlete = replace(ATHLETE, restrictions="No jumping.")
    assert lint_output("The striker runs into space when the winger cuts inside.", athlete, sport_scope=True) == ()
    assert "stated_restrictions" in lint_output("Add hopping between the cones.", athlete, sport_scope=True)
    assert lint_output("Perform ten lunges.", athlete) == ()
    assert "workload_cap" in lint_output("Perform ten lunges.", athlete, rest_only=True)
    assert "stated_restrictions" in lint_output("Perform ten lunges.", athlete, rest_only=True)


def test_negation_cannot_hide_a_later_prescription():
    assert lint_output("This is not a diagnosis. Ask a clinician about rehabilitation.", ATHLETE) == ()
    assert "clinical_advice" in lint_output("Ask a clinician about pain and follow this rehabilitation routine.", ATHLETE)
    assert "clinical_advice" in lint_output("This is not a diagnosis, but you probably have a concussion.", ATHLETE)


def test_allowed_movements_and_named_nonstandard_restrictions():
    athlete = replace(ATHLETE, restrictions="No jumping or toe taps. Running is allowed.")
    assert lint_output("Watch how the striker runs to create space.", athlete) == ()
    assert "stated_restrictions" in lint_output("Add toe taps before passing.", athlete)


def test_held_out_checksum_rejects_changed_bytes(tmp_path, monkeypatch):
    import lint_validation

    altered = tmp_path / "held_out.json"
    altered.write_bytes(HELD_OUT_PATH.read_bytes() + b" ")
    monkeypatch.setattr(lint_validation, "HELD_OUT_PATH", altered)
    with pytest.raises(ValueError, match="recorded checksum"):
        held_out_cases()
