"""Sandbox providers and the code that runs on them, against fakes (no provider needed).

Live runs on real providers are in test_sandboxes_live.py.
"""

import importlib
import subprocess
import sys
import types
from collections.abc import Mapping

import pytest

from deepgym.exceptions import DeepGymError, SandboxError
from deepgym.judge import JudgeJob
from deepgym.models import Environment
from deepgym.sandbox import run_judge_in_sandbox
from deepgym.sandboxes import ExecResult, SandboxTimeoutError, open_sandbox
from deepgym.sandboxes.apple import AppleContainer
from deepgym.sandboxes.docker import DockerContainer
from deepgym.session import SandboxBackend


class FakeSandbox:
    """Records commands; answers from a script of (substring, result) pairs."""

    def __init__(self, network_blocked: bool, answers: list[tuple[str, str]]) -> None:
        self.id = 'fake'
        self.network_blocked = network_blocked
        self.answers = answers
        self.commands: list[str] = []
        self.uploads: list[str] = []
        self.deleted = False

    def exec(
        self,
        command: str,
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        self.commands.append(command)
        for needle, output in self.answers:
            if needle in command:
                return ExecResult(0, output)
        return ExecResult(0, '')

    def upload(self, content: bytes, path: str) -> None:
        self.uploads.append(path)

    def delete(self) -> None:
        self.deleted = True


# ---------------------------------------------------------------------------
# Container CLIs
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, b'out', b'')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    return calls


def test_docker_runs_offline_and_removes_with_rm(cli_calls: list[list[str]]) -> None:
    box = DockerContainer(image='img')
    box.exec('echo hi', cwd='/w', env={'A': '1'}, timeout=5)
    box.upload(b'x', '/p/f')
    box.delete()
    run, exec_, upload, delete = cli_calls
    assert run[:2] == ['docker', 'run'] and {'--network', '--pids-limit', '--memory'} <= set(run)
    assert exec_ == [
        'docker', 'exec', '--workdir', '/w', '--env', 'A=1', box.id,
        'timeout', '--kill-after=2', '5', 'sh', '-c', 'echo hi',
    ]  # fmt: skip
    assert upload[:3] == ['docker', 'exec', '--interactive']
    assert delete == ['docker', 'rm', '--force', box.id]
    assert box.network_blocked


def test_apple_adds_netns_caps_and_deletes(cli_calls: list[list[str]]) -> None:
    box = AppleContainer(image='img')
    box.delete()
    assert '--cap-add' in cli_calls[0] and 'CAP_SYS_ADMIN' in cli_calls[0]
    assert cli_calls[1] == ['container', 'delete', '--force', box.id]
    assert not box.network_blocked


def test_cli_timeout_exit_becomes_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(argv, 124 if argv[1] == 'exec' else 0, b'', b'')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    box = DockerContainer(image='img')
    clock = iter([0.0, 10.0])
    monkeypatch.setattr('deepgym.sandboxes.cli.time.monotonic', lambda: next(clock))
    with pytest.raises(SandboxTimeoutError):
        box.exec('sleep 99', timeout=5)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(DeepGymError, match='Unknown sandbox provider'):
        open_sandbox('nope')  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Modal and E2B, against stand-ins for their SDKs
# ---------------------------------------------------------------------------


def _install(monkeypatch: pytest.MonkeyPatch, name: str, attrs: dict) -> None:
    module = types.ModuleType(name)
    for attr, value in attrs.items():
        setattr(module, attr, value)
    monkeypatch.setitem(sys.modules, name, module)


def test_modal_blocks_network_and_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict = {}

    class Process:
        stdout = types.SimpleNamespace(read=lambda: 'out')
        stderr = types.SimpleNamespace(read=lambda: 'err')

        def wait(self) -> int:
            return 3

    class Sandbox:
        object_id = 'sb-1'
        filesystem = types.SimpleNamespace(write_bytes=lambda data, path: created.update(w=path))

        @staticmethod
        def create(*args: str, **kwargs: object) -> 'Sandbox':
            created.update(args=args, **kwargs)
            return Sandbox()

        def exec(self, *args: str, **kwargs: object) -> Process:
            created.setdefault('execs', []).append(args)
            return Process()

        def terminate(self) -> None:
            created['terminated'] = True

    _install(monkeypatch, 'modal', {
        'App': types.SimpleNamespace(lookup=lambda name, create_if_missing: name),
        'Image': types.SimpleNamespace(debian_slim=lambda python_version: 'image'),
        'Sandbox': Sandbox,
        'exception': types.SimpleNamespace(Error=Exception),
    })  # fmt: skip
    monkeypatch.delitem(sys.modules, 'deepgym.sandboxes.modal.sandbox', raising=False)
    module = importlib.import_module('deepgym.sandboxes.modal.sandbox')

    box = module.ModalSandbox()
    assert created['block_network'] is True and created['args'] == ('sleep', 'infinity')
    assert box.exec('false') == ExecResult(3, 'outerr')
    box.upload(b'x', '/a/b/c.txt')
    box.delete()
    assert created['execs'][-1][:2] == ('sh', '-c') and 'mkdir -p /a/b' in created['execs'][-1][2]
    assert created['w'] == '/a/b/c.txt' and created['terminated']


def test_e2b_runs_as_root_offline_and_maps_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class ExitError(Exception):
        exit_code, stdout, stderr = 2, 'o', 'e'

    class SlowError(Exception):
        pass

    seen: dict = {}

    class Commands:
        def run(self, cmd: str, **kwargs: object) -> object:
            seen.update(kwargs)
            if cmd == 'fail':
                raise ExitError()
            if cmd == 'slow':
                raise SlowError()
            return types.SimpleNamespace(exit_code=0, stdout='ok', stderr='')

    class Client:
        sandbox_id = 'e2b-1'
        commands = Commands()

        @staticmethod
        def create(**kwargs: object) -> 'Client':
            seen['create'] = kwargs
            return Client()

    _install(monkeypatch, 'e2b', {
        'Sandbox': Client,
        'CommandExitException': ExitError,
        'TimeoutException': SlowError,
    })  # fmt: skip
    monkeypatch.delitem(sys.modules, 'deepgym.sandboxes.e2b.sandbox', raising=False)
    module = importlib.import_module('deepgym.sandboxes.e2b.sandbox')

    box = module.E2BSandbox()
    assert seen['create']['allow_internet_access'] is False
    assert box.exec('ok') == ExecResult(0, 'ok') and seen['user'] == 'root'
    assert box.exec('fail') == ExecResult(2, 'oe')
    with pytest.raises(SandboxTimeoutError):
        box.exec('slow', timeout=1)


# ---------------------------------------------------------------------------
# Judge and sessions on any provider
# ---------------------------------------------------------------------------

_JOB = JudgeJob.for_environment(Environment(task='t', verifier_code='return 1.0'), '')


def test_judge_fails_closed_when_it_cannot_go_offline() -> None:
    box = FakeSandbox(network_blocked=False, answers=[('useradd', '0 999 987 /usr/bin/python3 0')])
    with pytest.raises(SandboxError, match='network'):
        run_judge_in_sandbox(box, _JOB)


def test_judge_trusts_a_provider_that_blocks_the_network() -> None:
    box = FakeSandbox(
        network_blocked=True,
        answers=[
            ('useradd', '0 999 987 /usr/bin/python3 0'),
            ('DEEPGYM_DEADLINE', '{"score": 1.0, "passed": true}'),
        ],
    )
    assert run_judge_in_sandbox(box, _JOB).verifier_result.score == 1.0


def test_session_runs_as_agent_and_joins_netns_only_when_needed() -> None:
    blocked = FakeSandbox(network_blocked=True, answers=[('useradd', '997 997')])
    SandboxBackend(blocked).exec('ls', timeout=5)
    assert blocked.commands[-1].startswith('setpriv --reuid=997 --regid=997')

    open_ = FakeSandbox(network_blocked=False, answers=[('useradd', '997 997'), ('setsid', '42')])
    SandboxBackend(open_).exec('ls', timeout=5)
    assert open_.commands[-1].startswith('nsenter --net=/proc/42/ns/net -- setpriv')


def test_session_write_file_is_staged_then_written_as_agent() -> None:
    box = FakeSandbox(network_blocked=True, answers=[('useradd', '997 997')])
    SandboxBackend(box).write_file('a/b.py', b'x')
    staged = box.uploads[-1]
    assert staged.startswith('/opt/deepgym-staging/')
    assert box.commands[-1].startswith('setpriv --reuid=997')
    assert f'< {staged}' in box.commands[-1] and '/tmp/deepgym/a/b.py' in box.commands[-1]


def test_session_closes_sandbox_when_setup_fails() -> None:
    box = FakeSandbox(network_blocked=True, answers=[('useradd', 'garbage')])
    box.exec = lambda command, **kw: ExecResult(1, 'useradd: not found')  # type: ignore[method-assign]
    with pytest.raises(SandboxError, match='session user'):
        SandboxBackend(box)
    assert box.deleted
