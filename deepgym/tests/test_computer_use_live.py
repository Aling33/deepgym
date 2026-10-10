"""Live computer-use episodes on Daytona: reference runs pass, doing nothing scores 0."""

import os

import pytest

from deepgym import DeepGym, load_environment
from tests.computer_use_trajectories import DONE, REFERENCE, variants

pytestmark = pytest.mark.skipif(
    not os.getenv('DAYTONA_API_KEY'), reason='needs DAYTONA_API_KEY for live sandboxes'
)

# First and last variant of each env; the full sweep is too slow for a test run.
CASES = [(name, v) for name in sorted(REFERENCE) for v in (0, len(variants(name)) - 1)]


@pytest.fixture(scope='module')
def dg() -> DeepGym:
    return DeepGym(mode='daytona')


@pytest.mark.parametrize(('name', 'variant'), CASES)
def test_reference_trajectory_passes(dg: DeepGym, name: str, variant: int) -> None:
    actions = iter(REFERENCE[name](variants(name)[variant]))
    env = load_environment(name, variant=variant)
    trajectory, result = dg.run_episode(env, lambda obs: next(actions))
    assert result.passed, result.output
    assert trajectory.steps[0][0].screenshot


def test_doing_nothing_scores_zero(dg: DeepGym) -> None:
    _, result = dg.run_episode(load_environment('settings_tabs'), lambda obs: DONE)
    assert result.score == 0.0
