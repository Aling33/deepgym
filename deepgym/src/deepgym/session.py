"""Live episode sessions: one sandbox, many agent actions, one final score.

A Session keeps a sandbox alive across steps so agents can act on real state
(shell, files, or a desktop), then runs the final verifier against that state.

WARNING: LocalBackend runs agent actions on the host without isolation.
Use the Daytona backend for untrusted agents.
"""

from __future__ import annotations

import base64
import json
import logging
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Protocol

from deepgym.exceptions import (
    ActionError,
    DeepGymError,
    SandboxError,
    TimeoutError,
    VerifierError,
)
from deepgym.models import (
    Action,
    MultiTurnEnvironment,
    Observation,
    RunResult,
    Trajectory,
)
from deepgym.sandbox import (
    _extract_json_line,
    build_run_result,
    cleanup_sandbox,
    is_command_timeout,
    parse_verifier_output,
)

if TYPE_CHECKING:
    from daytona import Daytona, Sandbox

logger = logging.getLogger(__name__)

_DAYTONA_WORKDIR = '/tmp/deepgym'
_DISPLAY = ':0'
_STEP_OUTPUT = '_step_output.txt'


class ExecResult(NamedTuple):
    """Exit code and combined stdout/stderr of a shell command."""

    exit_code: int
    output: str


class StepResult(NamedTuple):
    """Outcome of one agent action."""

    observation: Observation
    reward: float
    done: bool


class SessionBackend(Protocol):
    """Where a session's actions actually run."""

    sandbox_id: str
    python: str

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> ExecResult:
        """Run a bash command in the work directory."""
        ...

    def write_file(self, path: str, content: bytes) -> None:
        """Write a file relative to the work directory."""
        ...

    def start_desktop(self) -> None:
        """Start the desktop so GUI actions and screenshots work."""
        ...

    def act(self, action: Action) -> None:
        """Apply a GUI action."""
        ...

    def screenshot(self) -> str:
        """Return the screen as a base64 PNG."""
        ...

    def close(self) -> None:
        """Release the sandbox."""
        ...


class LocalBackend:
    """Run actions in a host temp directory. Dev/testing only: no isolation, no desktop."""

    sandbox_id = 'local-session'
    python = shlex.quote(sys.executable)

    def __init__(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix='deepgym_session_'))

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> ExecResult:
        """Run *command* with bash in the temp directory.

        Raises:
            TimeoutError: If the command exceeds *timeout* seconds.
        """
        proc_env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin', **(env or {})}
        try:
            proc = subprocess.run(
                ['bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self._dir,
                env=proc_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f'Command exceeded {timeout}s timeout') from exc
        return ExecResult(
            proc.returncode, proc.stdout + ('\n' + proc.stderr if proc.stderr else '')
        )

    def write_file(self, path: str, content: bytes) -> None:
        """Write *content* to *path* inside the temp directory."""
        target = self._dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def start_desktop(self) -> None:
        """Refuse: the local backend has no display."""
        raise DeepGymError('Desktop environments need the Daytona backend')

    def act(self, action: Action) -> None:
        """Refuse: the local backend has no display."""
        raise DeepGymError('GUI actions need the Daytona backend')

    def screenshot(self) -> str:
        """Refuse: the local backend has no display."""
        raise DeepGymError('Screenshots need the Daytona backend')

    def close(self) -> None:
        """Delete the temp directory."""
        shutil.rmtree(self._dir, ignore_errors=True)


class DaytonaBackend:
    """Run actions in a dedicated Daytona sandbox, including desktop control."""

    python = 'python3'

    def __init__(self, daytona: Daytona, env: MultiTurnEnvironment) -> None:
        from daytona import CreateSandboxFromSnapshotParams

        try:
            self._sandbox: Sandbox = daytona.create(
                CreateSandboxFromSnapshotParams(
                    snapshot=env.snapshot, ephemeral=True, network_block_all=True
                )
            )
        except Exception as exc:
            raise SandboxError(f'Failed to create sandbox: {exc}') from exc
        self._daytona = daytona
        self._env: dict[str, str] = {}
        self.sandbox_id = str(getattr(self._sandbox, 'id', 'unknown'))
        try:
            self._sandbox.fs.create_folder(_DAYTONA_WORKDIR, '755')
        except Exception as exc:
            self.close()
            raise SandboxError(f'Failed to create work dir: {exc}') from exc

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> ExecResult:
        """Run *command* with bash in the sandbox work directory.

        Raises:
            TimeoutError: If the command exceeds *timeout* seconds.
            SandboxError: If the sandbox call itself fails.
        """
        try:
            response = self._sandbox.process.exec(
                f'bash -c {shlex.quote(command)}',
                cwd=_DAYTONA_WORKDIR,
                env={**self._env, **(env or {})},
                timeout=timeout,
            )
        except Exception as exc:
            if is_command_timeout(exc):
                raise TimeoutError(f'Command exceeded {timeout}s timeout') from exc
            raise SandboxError(f'Sandbox exec failed: {exc}') from exc
        return ExecResult(response.exit_code, response.result)

    def write_file(self, path: str, content: bytes) -> None:
        """Upload *content* to *path* under the work directory."""
        try:
            self._sandbox.fs.upload_file(content, f'{_DAYTONA_WORKDIR}/{path}')
        except Exception as exc:
            raise SandboxError(f'Failed to write {path}: {exc}') from exc

    def start_desktop(self) -> None:
        """Start Xvfb, xfce, and VNC in the sandbox."""
        try:
            self._sandbox.computer_use.start()
        except Exception as exc:
            raise SandboxError(f'Failed to start desktop: {exc}') from exc
        self._env['DISPLAY'] = _DISPLAY

    def act(self, action: Action) -> None:
        """Apply a GUI action through Daytona computer use.

        Raises:
            ActionError: If the desktop rejects the input (e.g. an unknown key name).
            SandboxError: If the Daytona computer-use call fails for any other reason.
        """
        try:
            self._dispatch(action)
        except Exception as exc:
            # ponytail: Daytona reports bad input as a generic daemon 500, so match its wording.
            message = str(exc).lower()
            if 'invalid' in message or 'unsupported' in message:
                raise ActionError(f'{action.action_type} rejected: {exc}') from exc
            raise SandboxError(f'{action.action_type} failed: {exc}') from exc

    def _dispatch(self, action: Action) -> None:
        mouse = self._sandbox.computer_use.mouse
        keyboard = self._sandbox.computer_use.keyboard
        match action.action_type:
            case 'click':
                mouse.click(action.x, action.y)
            case 'double_click':
                mouse.click(action.x, action.y, double=True)
            case 'right_click':
                mouse.click(action.x, action.y, button='right')
            case 'move':
                mouse.move(action.x, action.y)
            case 'drag':
                mouse.drag(action.x, action.y, action.to_x, action.to_y)
            case 'scroll':
                mouse.scroll(action.x, action.y, action.content, action.amount)
            case 'type':
                keyboard.type(action.content)
            case 'key':
                keyboard.hotkey(action.content)

    def screenshot(self) -> str:
        """Return a full-resolution PNG so pixel coordinates match click targets."""
        from daytona import ScreenshotOptions

        try:
            shot = self._sandbox.computer_use.screenshot.take_compressed(
                ScreenshotOptions(fmt='png', scale=1.0)
            )
        except Exception as exc:
            raise SandboxError(f'Failed to take screenshot: {exc}') from exc
        return shot.screenshot

    def close(self) -> None:
        """Delete the sandbox."""
        cleanup_sandbox(self._sandbox, self._daytona)


class Session:
    """Run one episode of a multi-turn environment against a live backend.

    Usage::

        with dg.session(env) as session:
            obs = session.start()
            while not session.done:
                obs, reward, done = session.step(agent(obs))
            result = session.score()
    """

    def __init__(self, env: MultiTurnEnvironment, backend: SessionBackend) -> None:
        self._env = env
        self._backend = backend
        self._trajectory = Trajectory()
        self._obs: Observation | None = None
        self._step = 0
        self._done = False
        # One sandbox, one actor at a time: concurrent step/score/close calls queue up.
        self._lock = threading.Lock()

    @property
    def done(self) -> bool:
        """Whether the episode has ended."""
        return self._done

    @property
    def trajectory(self) -> Trajectory:
        """Everything that happened so far."""
        return self._trajectory

    @property
    def sandbox_id(self) -> str:
        """Identifier of the backing sandbox."""
        return self._backend.sandbox_id

    def start(self) -> Observation:
        """Write files, start the desktop, run setup, and return the first observation.

        Raises:
            DeepGymError: If the session was already started.
            SandboxError: If setup exits non-zero.
            TimeoutError: If setup exceeds ``setup_timeout``.
        """
        with self._lock:
            if self._obs is not None:
                raise DeepGymError('Session already started; open a new session per episode')
            env = self._env
            for path, content in env.files.items():
                self._backend.write_file(path, content.encode('utf-8'))
            if env.desktop:
                self._backend.start_desktop()
            output = ''
            if env.setup_script:
                output = _checked(
                    'Setup script', self._backend.exec(env.setup_script, env.setup_timeout)
                )
            if env.setup_code:
                output = _checked(
                    'Setup code', self._run_python('_setup.py', env.setup_code, env.setup_timeout)
                )
            self._obs = self._observe(output, done=False)
            return self._obs

    def step(self, action: Action) -> StepResult:
        """Apply one action and return the new observation, step reward, and done flag.

        Raises:
            DeepGymError: If the session is not running.
            ActionError: If the action is not allowed here or the desktop rejects it.
            VerifierError: If the step verifier fails; the episode is then over.
        """
        with self._lock:
            if self._obs is None or self._done:
                raise DeepGymError('Session is not running; call start() or open a new session')
            if action.action_type not in self._env.allowed_actions:
                raise ActionError(
                    f'Action {action.action_type!r} not allowed here. '
                    f'Allowed: {sorted(self._env.allowed_actions)}'
                )

            self._step += 1
            output, exit_code = self._apply(action)
            try:
                reward = self._step_reward(output) if self._env.step_verifier_code else 0.0
            except VerifierError:
                self._record(action, output, exit_code, reward=0.0, done=True)
                raise
            done = (
                action.action_type == 'done'
                or _signals_done(output)
                or self._step >= self._env.max_steps
            )
            return self._record(action, output, exit_code, reward=reward, done=done)

    def score(self) -> RunResult:
        """Run the final verifier against the current state.

        Raises:
            VerifierError: If the verifier output is not valid protocol JSON.
            TimeoutError: If the verifier exceeds the per-step timeout.
        """
        if not self._env.final_verifier_code:
            return RunResult(
                score=0.0,
                passed=False,
                output='No final verifier provided',
                stderr='',
                exit_code=0,
                execution_time_ms=0.0,
                sandbox_id=self.sandbox_id,
            )
        with self._lock:
            start = time.perf_counter()
            exit_code, stdout = self._backend.exec(
                _inline_python(self._backend.python, self._env.final_verifier_code),
                self._env.timeout_per_step,
            )
            result = parse_verifier_output(stdout, f'exit_code={exit_code}')
            elapsed_ms = (time.perf_counter() - start) * 1000
            return build_run_result(result, elapsed_ms, self.sandbox_id, exit_code=exit_code)

    def close(self) -> None:
        """Release the backend, waiting for any in-flight step to finish."""
        with self._lock:
            self._backend.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _apply(self, action: Action) -> tuple[str, int | None]:
        """Execute *action*; return its text output and exit code (None if not a command)."""
        timeout = self._env.timeout_per_step
        try:
            match action.action_type:
                case 'code':
                    exit_code, output = self._run_python('_step.py', action.content)
                    return output, exit_code
                case 'bash':
                    exit_code, output = self._backend.exec(action.content, timeout)
                    return output, exit_code
                case 'write_file':
                    self._backend.write_file(str(action.path), action.content.encode('utf-8'))
                    return f'wrote {action.path}', None
                case 'wait':
                    time.sleep(min(action.amount, timeout))
                    return '', None
                case 'done' | 'screenshot':
                    return '', None
        except TimeoutError:
            return f'[timed out after {timeout}s]', None
        self._backend.act(action)
        return '', None

    def _run_python(self, filename: str, code: str, timeout: int | None = None) -> ExecResult:
        self._backend.write_file(filename, code.encode('utf-8'))
        return self._backend.exec(
            f'{self._backend.python} {filename}', timeout or self._env.timeout_per_step
        )

    def _record(
        self, action: Action, output: str, exit_code: int | None, *, reward: float, done: bool
    ) -> StepResult:
        """Append the step to the trajectory and advance the current observation."""
        self._trajectory.steps.append((self._obs, action))
        self._trajectory.step_rewards.append(reward)
        self._trajectory.total_reward += reward
        self._done = done
        self._obs = self._observe(output, done=done, exit_code=exit_code)
        if done:
            self._trajectory.final_observation = self._obs
        return StepResult(self._obs, reward, done)

    def _observe(self, output: str, *, done: bool, exit_code: int | None = None) -> Observation:
        return Observation(
            content=output,
            step=self._step,
            done=done,
            screenshot=self._backend.screenshot() if self._env.desktop else None,
            metadata=None if exit_code is None else {'exit_code': exit_code},
        )

    def _step_reward(self, output: str) -> float:
        """Run the step verifier and return its score, clamped to [0, 1].

        Stderr is discarded so warnings can't break the plain-float form.

        Raises:
            VerifierError: If the step verifier times out or prints neither a float
                nor JSON with a score.
        """
        self._backend.write_file(_STEP_OUTPUT, output.encode('utf-8'))
        try:
            stdout = self._backend.exec(
                _inline_python(self._backend.python, self._env.step_verifier_code) + ' 2>/dev/null',
                self._env.timeout_per_step,
                env={'STEP_OUTPUT_PATH': _STEP_OUTPUT, 'STEP_NUMBER': str(self._step)},
            ).output.strip()
        except TimeoutError as exc:
            raise VerifierError(f'Step verifier timed out at step {self._step}') from exc
        json_str = _extract_json_line(stdout)
        try:
            value = json.loads(json_str)['score'] if json_str else float(stdout)
            return max(0.0, min(1.0, float(value)))
        except (ValueError, TypeError, KeyError) as exc:
            raise VerifierError(
                f'Step verifier output unparseable at step {self._step}: {stdout!r}'
            ) from exc


def run_episode(
    session: Session, agent: Callable[[Observation], Action]
) -> tuple[Trajectory, RunResult]:
    """Drive *session* with *agent* until done, then score it.

    Args:
        session: A fresh, unstarted session. It is closed afterwards.
        agent: Callable mapping an observation to the next action.

    Returns:
        Tuple of (trajectory, final_result).
    """
    with session:
        obs = session.start()
        while not session.done:
            obs = session.step(agent(obs)).observation
        return session.trajectory, session.score()


def _checked(what: str, result: ExecResult) -> str:
    """Return *result*'s output, or raise if the command failed."""
    if result.exit_code != 0:
        raise SandboxError(f'{what} exited {result.exit_code}: {result.output[-2000:]}')
    return result.output


def _inline_python(python: str, code: str) -> str:
    """Build a command that runs *code* isolated (-I) without writing it to disk.

    Verifiers never touch the sandbox filesystem, so an agent process can't swap
    the file between upload and execution.
    """
    encoded = base64.b64encode(code.encode('utf-8')).decode('ascii')
    loader = f"import base64;exec(compile(base64.b64decode('{encoded}'),'<verifier>','exec'))"
    return f'{python} -I -c "{loader}"'


def _signals_done(output: str) -> bool:
    """Return True if output has a line 'DONE' or a JSON line with "done": true."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == 'DONE':
            return True
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                if json.loads(stripped).get('done') is True:
                    return True
            except (json.JSONDecodeError, AttributeError):
                continue
    return False
