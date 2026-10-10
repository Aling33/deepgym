"""Live computer-use episodes on Daytona: reference runs pass, doing nothing scores 0."""

import os

import pytest

from deepgym import DeepGym, load_environment
from tests.computer_use_trajectories import DONE, REFERENCE

pytestmark = pytest.mark.skipif(
    not os.getenv('DAYTONA_API_KEY'), reason='needs DAYTONA_API_KEY for live sandboxes'
)


@pytest.fixture(scope='module')
def dg() -> DeepGym:
    return DeepGym(mode='daytona')


@pytest.mark.parametrize('name', sorted(REFERENCE))
def test_reference_trajectory_passes(dg: DeepGym, name: str) -> None:
    actions = iter(REFERENCE[name])
    trajectory, result = dg.run_episode(load_environment(name), lambda obs: next(actions))
    assert result.passed, result.output
    assert trajectory.steps[0][0].screenshot


def test_doing_nothing_scores_zero(dg: DeepGym) -> None:
    _, result = dg.run_episode(load_environment('settings_tabs'), lambda obs: DONE)
    assert result.score == 0.0
