"""The solution runs isolated from the judge: reward hacks fail, slow cases fail alone.

Runs locally. File-isolation checks need sandbox-exec (macOS) or bwrap (Linux)
and are skipped where neither works.
"""

import time

import pytest

from deepgym import DeepGym, load_environment
from deepgym.judge import local_isolation_kind
from deepgym.models import Environment

needs_sandbox = pytest.mark.skipif(
    local_isolation_kind() == 'none', reason='no sandbox-exec or bwrap on this machine'
)

WRONG = 'def coin_change(coins, amount):\n    return 0\n'


@pytest.fixture(scope='module')
def dg() -> DeepGym:
    return DeepGym(mode='local')


def _score(dg: DeepGym, solution: str, env: Environment | None = None) -> float:
    return dg.run(env or load_environment('coin_change'), solution).score


def _env(verify_body: str, **kwargs: object) -> Environment:
    """A verify()-style environment; *verify_body* sees ``sol`` = load_solution(...)."""
    source = (
        'from deepgym_solution import load_solution, run_solution\n\n'
        'def verify(solution_path, test_cases_path=None):\n'
        '    sol = load_solution(solution_path)\n'
        + ''.join(f'    {line}\n' for line in verify_body.strip().splitlines())
    )
    return Environment(task='t', verifier_code=source, **kwargs)


class TestRewardHacksFail:
    """Classic in-process hacks that used to work against verifiers that import the solution."""

    def test_reference_scores_full(self, dg: DeepGym) -> None:
        reference = load_environment('coin_change').verifier_path.with_name('reference_solution.py')
        assert _score(dg, reference.read_text()) == 1.0

    def test_fake_score_line_then_exit(self, dg: DeepGym) -> None:
        hack = 'import os\nprint(\'{"score": 1.0, "passed": true}\', flush=True)\nos._exit(0)\n'
        assert _score(dg, hack) == 0.0

    def test_fake_score_line_at_exit(self, dg: DeepGym) -> None:
        hack = (
            'import atexit\n'
            'atexit.register(lambda: print(\'{"score": 1.0, "passed": true}\'))\n' + WRONG
        )
        assert _score(dg, hack) < 1.0

    def test_object_that_equals_everything(self, dg: DeepGym) -> None:
        hack = (
            'class Anything:\n'
            '    def __eq__(self, other):\n'
            '        return True\n'
            'def coin_change(coins, amount):\n'
            '    return Anything()\n'
        )
        assert _score(dg, hack) == 0.0

    def test_int_subclass_that_equals_everything(self, dg: DeepGym) -> None:
        hack = (
            'class Sneaky(int):\n'
            '    def __eq__(self, other):\n'
            '        return True\n'
            'def coin_change(coins, amount):\n'
            '    return Sneaky(0)\n'
        )
        assert _score(dg, hack) < 1.0

    def test_patching_the_judge_does_nothing(self, dg: DeepGym) -> None:
        hack = 'import __main__\n__main__.ref_coin_change = lambda coins, amount: 0\n' + WRONG
        assert _score(dg, hack) < 1.0

    @needs_sandbox
    def test_cannot_read_judge_files_or_import_deepgym(self, dg: DeepGym) -> None:
        env = _env(
            """
from pathlib import Path
secret = Path(__file__).with_name('secret.txt')
secret.write_text('s3cret')
leaks = []
for probe, arg in (('read', str(secret)), ('import_deepgym', None)):
    try:
        getattr(sol, probe)(*([arg] if arg else []))
        leaks.append(probe)
    except Exception:
        pass
return {'score': 0.0 if leaks else 1.0, 'passed': not leaks, 'details': str(leaks)}
"""
        )
        solution = (
            'def read(path):\n'
            '    return open(path).read()\n'
            'def import_deepgym():\n'
            '    import deepgym\n'
        )
        result = dg.run(env, solution)
        assert result.passed, result.output

    def test_host_secrets_not_visible(self, dg: DeepGym, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('DG_TEST_SECRET', 'hunter2')
        env = _env("return {'score': 0.0 if sol.leaked() else 1.0, 'passed': not sol.leaked()}")
        solution = 'import os\ndef leaked():\n    return "DG_TEST_SECRET" in os.environ\n'
        assert dg.run(env, solution).passed


class TestRuntime:
    """Calls behave like local calls, with failures contained per case."""

    def test_slow_case_fails_alone(self, dg: DeepGym) -> None:
        env = _env(
            """
ok = 0
for n in (1, 2, 3):
    try:
        ok += sol.double(n) == 2 * n
    except TimeoutError:
        pass
return ok / 3
""",
            case_timeout=1,
            timeout=20,
        )
        solution = 'def double(n):\n    while n == 2:\n        pass\n    return 2 * n\n'
        assert dg.run(env, solution).score == pytest.approx(2 / 3)

    def test_deadline_ends_run_with_partial_credit(self, dg: DeepGym) -> None:
        env = _env(
            """
ok = 0
for n in range(20):
    try:
        ok += sol.spin(n) == n
    except TimeoutError:
        pass
return {'score': ok / 20, 'passed': False}
""",
            case_timeout=5,
            timeout=2,
        )
        start = time.monotonic()
        result = dg.run(env, 'def spin(n):\n    while True:\n        pass\n')
        assert result.score == 0.0
        assert time.monotonic() - start < 12

    def test_crash_in_one_case_recovers(self, dg: DeepGym) -> None:
        env = _env(
            """
ok = 0
for n in (1, 2, 3):
    try:
        ok += sol.f(n) == n
    except Exception:
        pass
return ok / 3
"""
        )
        solution = 'import os\ndef f(n):\n    if n == 2:\n        os._exit(1)\n    return n\n'
        assert dg.run(env, solution).score == pytest.approx(2 / 3)

    def test_builtin_exceptions_keep_their_type(self, dg: DeepGym) -> None:
        env = _env(
            """
try:
    sol.f()
except ValueError as exc:
    return str(exc) == 'bad input'
return False
"""
        )
        assert dg.run(env, 'def f():\n    raise ValueError("bad input")\n').passed

    def test_plain_data_round_trips(self, dg: DeepGym) -> None:
        env = _env(
            """
value = {'t': (1, 2.5, None), 's': {1, 2}, 'b': bytes([0, 255]), 'inf': float('inf'), 7: [True]}
return sol.echo(value) == value
"""
        )
        assert dg.run(env, 'def echo(x):\n    return x\n').passed

    def test_objects_stay_remote(self, dg: DeepGym) -> None:
        env = _env(
            """
counter = sol.Counter(5)
counter.add(2)
return counter.value() == 7 and sol.LIMIT == 10
"""
        )
        solution = (
            'LIMIT = 10\n'
            'class Counter:\n'
            '    def __init__(self, start):\n'
            '        self.n = start\n'
            '    def add(self, k):\n'
            '        self.n += k\n'
            '    def value(self):\n'
            '        return self.n\n'
        )
        assert dg.run(env, solution).passed

    def test_solution_prints_do_not_break_calls(self, dg: DeepGym) -> None:
        env = _env('return sol.f(3) == 9')
        solution = 'def f(x):\n    print("noise " * 1000)\n    return x * x\n'
        assert dg.run(env, solution).passed

    def test_missing_function_is_attribute_error(self, dg: DeepGym) -> None:
        env = _env("return not hasattr(sol, 'nope') and hasattr(sol, 'f')")
        assert dg.run(env, 'def f():\n    pass\n').passed

    def test_import_error_surfaces(self, dg: DeepGym) -> None:
        env = _env('return 1.0')
        result = dg.run(env, 'def broken(:\n')
        assert result.score == 0.0
        assert 'SyntaxError' in result.output

    def test_run_solution_writes_only_in_cwd(self, dg: DeepGym) -> None:
        verifier = (
            'import tempfile\n'
            'from pathlib import Path\n'
            'from deepgym_solution import run_solution\n\n'
            'def verify(solution_path):\n'
            '    work = tempfile.mkdtemp()\n'
            "    proc = run_solution(solution_path, cwd=work, env={'OUT': work})\n"
            "    inside = Path(work, 'ok.txt').read_text() == 'ok'\n"
            "    outside = Path(__file__).with_name('pwned.txt').exists()\n"
            "    return inside and not outside and 'done' in proc.stdout\n"
        )
        solution = (
            'import os, pathlib, sys\n'
            'pathlib.Path(os.environ["OUT"], "ok.txt").write_text("ok")\n'
            'try:\n'
            '    pathlib.Path(sys.argv[0]).parent.parent.joinpath("pwned.txt").write_text("x")\n'
            'except OSError:\n'
            '    pass\n'
            'print("done")\n'
        )
        assert dg.run(Environment(task='t', verifier_code=verifier), solution).passed


class TestVerifierModes:
    """Verifier shape comes from parsing (or an explicit mode), not text search."""

    def test_script_with_helper_printer_and_future_import(self, dg: DeepGym) -> None:
        source = (
            'from __future__ import annotations\n'
            'import json, sys\n'
            'def emit(result: dict) -> None:\n'
            '    sys.stdout.write(json.JSONEncoder().encode(result) + "\\n")\n'
            'if __name__ == "__main__":\n'
            '    emit({"score": 1.0, "passed": True})\n'
        )
        env = Environment(task='t', verifier_code=source)
        assert dg.run(env, '').passed

    def test_body_with_future_import(self, dg: DeepGym) -> None:
        env = Environment(
            task='t', verifier_code='from __future__ import annotations\nreturn 1.0\n'
        )
        assert dg.run(env, '').passed

    def test_explicit_mode_wins(self, dg: DeepGym) -> None:
        env = Environment(task='t', verifier_code='return 0.25\n', verifier_mode='body')
        assert dg.run(env, '').score == 0.25


class TestSupportFiles:
    """Verifiers can import shared helper modules."""

    def test_helper_module_is_importable(self, dg: DeepGym) -> None:
        env = Environment(
            task='t',
            verifier_code='from scoring import half\n\ndef verify(solution_path):\n    return half()\n',
            support_files={'scoring.py': 'def half():\n    return 0.5\n'},
        )
        assert dg.run(env, '').score == 0.5

    def test_nested_helper_package(self, dg: DeepGym) -> None:
        env = Environment(
            task='t',
            verifier_code='from lib.scoring import full\n\ndef verify(solution_path):\n    return full()\n',
            support_files={
                'lib/__init__.py': '',
                'lib/scoring.py': 'def full():\n    return 1.0\n',
            },
        )
        assert dg.run(env, '').passed

    @needs_sandbox
    def test_solution_cannot_read_support_files(self, dg: DeepGym) -> None:
        env = Environment(
            task='t',
            verifier_code=(
                'from pathlib import Path\n'
                'from deepgym_solution import load_solution\n\n'
                'def verify(solution_path):\n'
                '    sol = load_solution(solution_path)\n'
                '    try:\n'
                '        sol.read(str(Path(__file__).with_name("answers.py")))\n'
                '        return 0.0\n'
                '    except Exception:\n'
                '        return 1.0\n'
            ),
            support_files={'answers.py': 'ANSWER = 42\n'},
        )
        assert dg.run(env, 'def read(p):\n    return open(p).read()\n').passed


class TestRegistrySupportFiles:
    """metadata.json can list shared helpers; paths can't escape the environments root."""

    def _bench(self, root, support: list[str]) -> None:
        import json

        (root / '_shared').mkdir(parents=True, exist_ok=True)
        (root / '_shared' / 'scoring.py').write_text('def score(x):\n    return float(x == 4)\n')
        env_dir = root / 'env1'
        env_dir.mkdir(exist_ok=True)
        (env_dir / 'task.md').write_text('square 2')
        (env_dir / 'verifier.py').write_text(
            'from deepgym_solution import load_solution\n'
            'from scoring import score\n\n'
            'def verify(solution_path):\n'
            '    return score(load_solution(solution_path).sq(2))\n'
        )
        (env_dir / 'metadata.json').write_text(
            json.dumps({'support_files': support, 'case_timeout': 3})
        )

    def test_shared_helper_loads(
        self, dg: DeepGym, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr('deepgym.registry._get_cache_dir', lambda: tmp_path)
        self._bench(tmp_path / 'bench', ['../_shared/scoring.py'])
        env = load_environment('bench/env1')
        assert env.case_timeout == 3
        assert dg.run(env, 'def sq(x):\n    return x * x\n').passed

    def test_escaping_the_root_is_rejected(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr('deepgym.registry._get_cache_dir', lambda: tmp_path / 'cache')
        (tmp_path / 'cache').mkdir()
        (tmp_path / 'outside.py').write_text('SECRET = 1\n')
        self._bench(tmp_path / 'cache' / 'bench', ['../../../outside.py'])
        with pytest.raises(ValueError, match='not a file under'):
            load_environment('bench/env1')
