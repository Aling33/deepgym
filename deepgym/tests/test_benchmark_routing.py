"""Benchmark-backed and mixed environments must never silently score their placeholder verifier."""

import asyncio

import pytest

from deepgym import AsyncDeepGym, DeepGym, MixedEnvironment, load_environment
from deepgym.exceptions import DeepGymError
from deepgym.models import Environment, RunResult


def _reference(name: str) -> str:
    return load_environment(name).verifier_path.with_name('reference_solution.py').read_text()


class Delegating(Environment):
    """Stands in for SWE-bench Pro / Terminal-Bench: scoring lives in run_with_deepgym."""

    task: str = 't'
    verifier_code: str = 'return 0.0'

    def run_with_deepgym(self, dg: DeepGym, model_output: str, **kwargs: object) -> RunResult:
        score = 1.0 if kwargs.get('task_id') == 'ok' and model_output == 'patch' else 0.0
        return RunResult(
            score=score, passed=score == 1.0, output='', stderr='', exit_code=0,
            execution_time_ms=0.0, sandbox_id='delegated',
        )  # fmt: skip


@pytest.fixture()
def mixed() -> MixedEnvironment:
    return MixedEnvironment(
        environments=[(load_environment('coin_change'), 1.0), (load_environment('two_sum'), 1.0)]
    )


def test_sync_run_routes_mixed(mixed: MixedEnvironment) -> None:
    result = DeepGym(mode='local').run(mixed, _reference('two_sum'), env_name='two_sum')
    assert result.score == 1.0


def test_async_run_routes_mixed(mixed: MixedEnvironment) -> None:
    result = asyncio.run(
        AsyncDeepGym(mode='local').run(mixed, _reference('coin_change'), env_name='coin_change')
    )
    assert result.score == 1.0


def test_async_batch_routes_per_sample(mixed: MixedEnvironment) -> None:
    batch = asyncio.run(
        AsyncDeepGym(mode='local').run_batch(
            mixed,
            [_reference('coin_change'), _reference('two_sum')],
            env_name=['coin_change', 'two_sum'],
        )
    )
    assert [r.score for r in batch.results] == [1.0, 1.0]


def test_async_run_delegates_to_benchmark_runner() -> None:
    result = asyncio.run(AsyncDeepGym(mode='local').run(Delegating(), 'patch', task_id='ok'))
    assert result.score == 1.0
    assert result.sandbox_id == 'delegated'


def test_async_http_mode_refuses_benchmark_envs() -> None:
    client = AsyncDeepGym(api_url='http://127.0.0.1:9')
    with pytest.raises(DeepGymError, match='Benchmark-backed'):
        asyncio.run(client.run(Delegating(), 'patch'))
