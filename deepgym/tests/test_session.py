"""Tests for deepgym.session -- live multi-turn episodes on the local backend."""

import pytest
from pydantic import ValidationError

from deepgym import ComputerUseEnvironment, DeepGym
from deepgym.exceptions import DeepGymError
from deepgym.models import Action, MultiTurnEnvironment, Observation, Trajectory
from deepgym.session import _signals_done

PASS_VERIFIER = (
    'import json\n'
    'print(json.dumps({"schema_version": "1.0", "score": 1.0, "passed": True, "details": "ok"}))\n'
)

FILE_VERIFIER = (
    'import json, pathlib\n'
    'ok = pathlib.Path("notes/out.txt").read_text() == "hello"\n'
    'print(json.dumps({"score": float(ok), "passed": ok}))\n'
)


@pytest.fixture(scope='module')
def dg() -> DeepGym:
    """Local DeepGym client."""
    return DeepGym(mode='local')


def _scripted(*actions: Action):
    """Return an agent that plays *actions* in order."""
    queue = list(actions)
    return lambda obs: queue.pop(0)


class TestActionValidation:
    """Actions must carry the arguments their type needs."""

    def test_default_is_code(self) -> None:
        assert Action(content='print(1)').action_type == 'code'

    def test_click_needs_coordinates(self) -> None:
        with pytest.raises(ValidationError, match='needs x and y'):
            Action(action_type='click', x=10)

    def test_drag_needs_end(self) -> None:
        with pytest.raises(ValidationError, match='to_x and to_y'):
            Action(action_type='drag', x=1, y=2)

    def test_scroll_needs_direction(self) -> None:
        with pytest.raises(ValidationError, match='scroll content'):
            Action(action_type='scroll', x=1, y=2, content='sideways')

    def test_key_needs_content(self) -> None:
        with pytest.raises(ValidationError, match='key needs content'):
            Action(action_type='key')

    @pytest.mark.parametrize('path', [None, '/etc/passwd', '../escape.txt', 'a/../../b'])
    def test_write_file_rejects_unsafe_paths(self, path: str | None) -> None:
        with pytest.raises(ValidationError, match='relative path'):
            Action(action_type='write_file', path=path, content='x')

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Action(action_type='teleport')


class TestEnvironmentModels:
    """Episode environment defaults and invariants."""

    def test_multi_turn_defaults(self) -> None:
        env = MultiTurnEnvironment(task='t')
        assert env.max_steps == 10
        assert env.desktop is False
        assert env.allowed_actions == {'code', 'bash', 'write_file', 'done'}

    def test_gui_actions_need_desktop(self) -> None:
        with pytest.raises(ValidationError, match='desktop=True'):
            MultiTurnEnvironment(task='t', allowed_actions={'click', 'done'})

    def test_computer_use_is_gui_only(self) -> None:
        env = ComputerUseEnvironment(task='t')
        assert env.type == 'computer-use'
        assert env.desktop is True
        assert 'bash' not in env.allowed_actions
        assert {'click', 'type', 'key', 'done'} <= env.allowed_actions

    def test_min_steps_validation(self) -> None:
        with pytest.raises(ValidationError):
            MultiTurnEnvironment(task='t', max_steps=0)


class TestSignalsDone:
    """Output-based done detection."""

    @pytest.mark.parametrize(
        ('output', 'expected'),
        [
            ('some output\nDONE\n', True),
            ('{"done": true}', True),
            ('{"done": false}', False),
            ('regular output', False),
            ('', False),
            ('{not valid json}', False),
        ],
    )
    def test_signals_done(self, output: str, expected: bool) -> None:
        assert _signals_done(output) is expected


class TestLocalEpisodes:
    """End-to-end episodes on the local backend."""

    def test_done_marker_ends_episode(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=5, final_verifier_code=PASS_VERIFIER)
        agent = _scripted(Action(content='print("step")'), Action(content='print("DONE")'))

        trajectory, result = dg.run_episode(env, agent)

        assert isinstance(trajectory, Trajectory)
        assert len(trajectory.steps) == 2
        assert trajectory.final_observation is not None
        assert trajectory.final_observation.done is True
        assert result.passed is True

    def test_done_action_ends_episode(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=5, final_verifier_code=PASS_VERIFIER)
        trajectory, _ = dg.run_episode(env, _scripted(Action(action_type='done')))
        assert len(trajectory.steps) == 1

    def test_max_steps_ends_episode(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=2, final_verifier_code=PASS_VERIFIER)
        calls: list[Observation] = []

        def agent(obs: Observation) -> Action:
            calls.append(obs)
            return Action(content='print("working")')

        trajectory, _ = dg.run_episode(env, agent)
        assert len(calls) == 2
        assert len(trajectory.steps) == 2

    def test_no_final_verifier_scores_zero(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=1)
        _, result = dg.run_episode(env, _scripted(Action(action_type='done')))
        assert result.score == 0.0
        assert result.passed is False

    def test_verifier_sees_state_left_by_actions(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=3, final_verifier_code=FILE_VERIFIER)
        agent = _scripted(
            Action(action_type='write_file', path='notes/out.txt', content='hel'),
            Action(action_type='bash', content='printf hello > notes/out.txt'),
            Action(action_type='done'),
        )
        _, result = dg.run_episode(env, agent)
        assert result.passed is True

    def test_files_and_setup_run_before_first_observation(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(
            task='t',
            files={'data/in.txt': 'seed'},
            setup_script='cat data/in.txt',
            final_verifier_code=PASS_VERIFIER,
        )
        with dg.session(env) as session:
            obs = session.start()
        assert obs.content.strip() == 'seed'
        assert obs.step == 0

    def test_planted_module_cannot_hijack_verifier(self, dg: DeepGym) -> None:
        fake = 'print(\'{"score": 1.0, "passed": true}\')\nraise SystemExit(0)\n'
        honest = 'import json\nprint(json.dumps({"score": 0.0, "passed": False}))\n'
        env = MultiTurnEnvironment(task='t', max_steps=2, final_verifier_code=honest)
        agent = _scripted(
            Action(action_type='write_file', path='json.py', content=fake),
            Action(action_type='done'),
        )
        _, result = dg.run_episode(env, agent)
        assert result.passed is False

    def test_step_verifier_rewards(self, dg: DeepGym) -> None:
        step_verifier = (
            'import os, pathlib\n'
            'out = pathlib.Path(os.environ["STEP_OUTPUT_PATH"]).read_text()\n'
            'print(0.5 if "good" in out else 0.0)\n'
        )
        env = MultiTurnEnvironment(
            task='t',
            max_steps=2,
            step_verifier_code=step_verifier,
            final_verifier_code=PASS_VERIFIER,
        )
        agent = _scripted(Action(content='print("good")'), Action(content='print("bad")'))
        trajectory, _ = dg.run_episode(env, agent)
        assert trajectory.step_rewards == [0.5, 0.0]
        assert trajectory.total_reward == 0.5

    def test_step_timeout_becomes_observation(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', max_steps=1, timeout_per_step=1)
        with dg.session(env) as session:
            session.start()
            obs, _, done = session.step(Action(action_type='bash', content='sleep 5'))
        assert 'timed out' in obs.content
        assert done is True


class TestSessionGuards:
    """Misuse fails loudly."""

    def test_disallowed_action_raises(self, dg: DeepGym) -> None:
        env = MultiTurnEnvironment(task='t', allowed_actions={'code', 'done'})
        with dg.session(env) as session:
            session.start()
            with pytest.raises(DeepGymError, match='not allowed'):
                session.step(Action(action_type='bash', content='ls'))

    def test_step_before_start_raises(self, dg: DeepGym) -> None:
        with dg.session(MultiTurnEnvironment(task='t')) as session:
            with pytest.raises(DeepGymError, match='not running'):
                session.step(Action(action_type='done'))

    def test_double_start_raises(self, dg: DeepGym) -> None:
        with dg.session(MultiTurnEnvironment(task='t')) as session:
            session.start()
            with pytest.raises(DeepGymError, match='already started'):
                session.start()

    def test_desktop_needs_daytona(self, dg: DeepGym) -> None:
        with dg.session(ComputerUseEnvironment(task='t')) as session:
            with pytest.raises(DeepGymError, match='Daytona'):
                session.start()

    def test_run_rejects_multi_turn_env(self, dg: DeepGym) -> None:
        with pytest.raises(DeepGymError, match='run_episode'):
            dg.run(MultiTurnEnvironment(task='t'), model_output='')
