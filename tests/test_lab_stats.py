from importlib.util import find_spec
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from lab_data import CRITERIA, load_run
from lab_stats import (bootstrap_ci, holm_adjust, paired_differences, paired_summary, prompt_groups,
                       quadratic_kappa, rank_biserial, temperature_summary, wilcoxon_result)
from test_lab_data import run_fixture


def test_paired_effects_interval_and_holm(run_fixture):
    path, _ = run_fixture
    observations = load_run(path).observations()
    rows, = prompt_groups(observations).values()
    differences = paired_differences(rows, "safety_1_to_5")
    assert len(differences) == 10 and np.all(differences > 0)
    assert 1 < differences.mean() < 3
    ci = bootstrap_ci(differences)
    assert ci == bootstrap_ci(differences)
    assert ci[0] <= differences.mean() <= ci[1]
    assert rank_biserial(differences) == pytest.approx(1.0)
    assert rank_biserial(np.array([-3, 2, 1, 0])) == pytest.approx(0)
    assert holm_adjust({"large": .04, "small": .01, "missing": None}) == {
        "small": .03, "large": .08, "missing": None,
    }
    rows_summary = {row["criterion"]: row for row in paired_summary(rows)}
    assert rows_summary["safety_1_to_5"]["n"] == 10
    assert rows_summary["nutrition_appropriateness_1_to_5"]["n"] == 0


def test_lazy_wilcoxon_and_missing_scipy_leave_bootstrap(monkeypatch):
    differences = np.array([1, 2, -1, 3])
    module = ModuleType("scipy.stats")
    module.wilcoxon = Mock(return_value=SimpleNamespace(statistic=1.5, pvalue=.125))
    monkeypatch.setitem(sys.modules, "scipy.stats", module)
    assert wilcoxon_result(differences) == (1.5, .125, "")
    assert np.array_equal(module.wilcoxon.call_args.args[0], differences)
    assert module.wilcoxon.call_args.kwargs["alternative"] == "two-sided"
    assert wilcoxon_result(np.zeros(3)) == (0.0, 1.0, "All paired differences were zero")
    monkeypatch.setitem(sys.modules, "scipy.stats", None)
    assert wilcoxon_result(differences) == (None, None, "Wilcoxon unavailable")
    assert bootstrap_ci(differences) is not None


def test_quadratic_weighting_and_temperature_groups():
    assert quadratic_kappa([(1, 1), (3, 3), (5, 5)]) == 1
    assert quadratic_kappa([(1, 5), (5, 1)]) == -1
    assert quadratic_kappa([(3, 3), (3, 3)]) is None
    row = {"experiment": "temperature", "model": "test", "fixture": 4, "module": "Full-body training",
           "version": "V3", "top_p": .95, **dict.fromkeys(CRITERIA, 3)}
    observations = [{**row, "response_id": id_, "temperature": temp, "safety_1_to_5": safety}
                    for id_, temp, safety in (("R001", .3, 2), ("R002", .3, 4),
                                              ("R003", .8, 3), ("R004", .8, 3))]
    packets = {id_: (None, answer) for id_, answer in [
        ("R001", "Review space"), ("R002", "Review clips"), ("R003", "Study footage"),
        ("R004", "Study footage footage"),
    ]}
    data = {item["temperature"]: item for item in temperature_summary(observations, packets)
            if item["criterion"] == "safety_1_to_5"}
    assert data[.3]["jaccard_mean"] == pytest.approx(1 / 3)
    assert data[.3]["score_sd"] == pytest.approx(2 ** .5)
    assert data[.3]["jaccard_pairs"] == 1
    assert data[.8]["jaccard_mean"] == 1 and data[.8]["score_sd"] == 0


@pytest.mark.skipif(find_spec("scipy") is None, reason="SciPy is not installed in this local interpreter")
def test_scipy_wilcoxon_with_ten_paired_profiles():
    statistic, pvalue, notice = wilcoxon_result(np.arange(1, 11, dtype=float))
    assert (statistic, notice) == (0.0, "")
    assert pvalue == pytest.approx(2 / (2 ** 10))


def test_mde_uses_paired_sample_sd_and_sample_size():
    from lab_stats import minimum_detectable_difference

    differences = [-1, -0.5, 0, 0.5, 1]
    small_sd, small_mde, method = minimum_detectable_difference(differences)
    assert small_sd == pytest.approx((2.5 / 4) ** 0.5)
    assert small_mde > 0 and method in ("Paired t approximation", "Normal approximation")
    # Repeating every value preserves equal group variance up to the sample correction.
    _, large_mde, _ = minimum_detectable_difference(differences * 4)
    assert large_mde < small_mde
    doubled_sd, doubled_mde, _ = minimum_detectable_difference([d * 2 for d in differences])
    assert doubled_sd == pytest.approx(2 * small_sd)
    assert doubled_mde == pytest.approx(2 * small_mde)
    assert minimum_detectable_difference([0, 1])[1] > 0
    assert minimum_detectable_difference([2])[1] is None
    assert minimum_detectable_difference([2, 2])[1] is None


def test_mde_has_a_labelled_normal_approximation_when_scipy_is_unavailable(monkeypatch):
    import sys
    from lab_stats import minimum_detectable_difference

    monkeypatch.setitem(sys.modules, "scipy.optimize", None)
    sd, mde, method = minimum_detectable_difference([-1, 0, 1, 2])
    assert method == "Normal approximation"
    assert mde == pytest.approx(2.801585218 * sd / 2)
