import numpy as np
import pytest

from src.common import config
from src.scenario_model import dwell_seconds, compare
from src.policy_evaluation import conditional_energy, monetary_benefit


@pytest.fixture
def params():
    s = config('scenarios.yaml')
    return {**s['common'], **s['conditions']['Base']}


def test_no_policy_identity(params):
    b, p, saved, ratio = compare([0, 1, 30], [0, 20, 2], 0, params)
    np.testing.assert_array_equal(b, p)
    np.testing.assert_array_equal(saved, 0)


def test_parallel_boarding_can_help(params):
    _, _, saved, _ = compare(20, 0, .5, params)
    assert saved > 0


def test_heavy_alighting_can_make_policy_worse(params):
    _, _, saved, _ = compare(10, 40, .5, params)
    assert saved < 0


def test_fixed_and_accessibility_overhead_not_removed(params):
    assert dwell_seconds(0, 0, .5, params) == pytest.approx(5.6)


@pytest.mark.parametrize('b,a,r', [(-1, 0, .5), (1, -1, .5), (1, 1, 1.1), (np.nan, 1, .5)])
def test_impossible_inputs(b, a, r, params):
    with pytest.raises(ValueError):
        dwell_seconds(b, a, r, params)


def test_signed_energy_and_explicit_factor():
    result = conditional_energy(-3600, 'electric', 2, .4, .5, 'TEST_ONLY')
    assert result['energy_saved'] == -1
    assert result['co2_kg_saved'] == -.4
    with pytest.raises(ValueError):
        conditional_energy(100, 'diesel', 1, 1, 1, '')
    with pytest.raises(ValueError):
        monetary_benefit(10, 100, '')
