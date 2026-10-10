"""Live episode sessions: one sandbox, many agent actions, one final score.

A Session keeps a sandbox alive across steps so agents can act on real state
(shell, files, or a desktop), then runs the final verifier against that state.

WARNING: LocalBackend runs agent actions on the host without isolation.
Use the Daytona backend for untrusted agents.
"""

from __future__ import annotations

import json
import logging
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Protocol

from deepgym.exceptions import DeepGymError, SandboxError, TimeoutError, VerifierError
from deepgym.models import (
    Action,
    MultiTurnEnvironment,
    Observation,
    RunResult,
    Trajectory,
    VerifierResult,
)
from deepgym.sandbox import _extract_json_line, build_run_result, cleanup_sandbox

if TYPE_CHECKING:
    from daytona import Daytona, Sandbox

logger = logging.getLogger(__name__)

_DAYTONA_WORKDIR = '/tmp/deepgym'
_DISPLAY = ':0'
_STEP_VERIFIER = '_step_verifier.py'
_STEP_OUTPUT = '_step_output.txt'
_FINAL_VERIFIER = '_final_verifier.py'


class StepResult(NamedTuple):
    """Outcome of one agent action."""

    observation: Observation
    reward: float
    done: bool


class SessionBackend(Protocol):
    """Where a session's actions actually run."""

    sandbox_id: str
    python: str

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> str:
        """Run a shell command in the work directory and return combined output."""
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

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> str:
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
        return proc.stdout + ('\n' + proc.stderr if proc.stderr else '')

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

    def exec(self, command: str, timeout: int, env: dict[str, str] | None = None) -> str:
        """Run *command* in the sandbox work directory.

        Raises:
            TimeoutError: If the command exceeds *timeout* seconds.
            SandboxError: If the sandbox call itself fails.
        """
        try:
            response = self._sandbox.process.exec(
                command, cwd=_DAYTONA_WORKDIR, env={**self._env, **(env or {})}, timeout=timeout
            )
        except Exception as exc:
            if 'timeout' in str(exc).lower() or 'timed out' in str(exc).lower():
                raise TimeoutError(f'Command exceeded {timeout}s timeout') from exc
            raise SandboxError(f'Sandbox exec failed: {exc}') from exc
        return response.result

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
        """Apply a GUI action through Daytona computer use."""
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
            TimeoutError: If setup exceeds the per-step timeout.
        """
        if self._obs is not None:
            raise DeepGymError('Session already started; open a new session per episode')
        env = self._env
        for path, content in env.files.items():
            self._backend.write_file(path, content.encode('utf-8'))
        if env.desktop:
            self._backend.start_desktop()
        output = ''
        if env.setup_script:
            output = self._backend.exec(env.setup_script, env.timeout_per_step)
        if env.setup_code:
            output = self._run_python('_setup.py', env.setup_code)
        self._obs = self._observe(output, done=False)
        return self._obs

    def step(self, action: Action) -> StepResult:
        """Apply one action and return the new observation, step reward, and done flag.

        Raises:
            DeepGymError: If the session is not running or the action is not allowed.
        """
        if self._obs is None or self._done:
            raise DeepGymError('Session is not running; call start() or open a new session')
        if action.action_type not in self._env.allowed_actions:
            raise DeepGymError(
                f'Action {action.action_type!r} not allowed here. '
                f'Allowed: {sorted(self._env.allowed_actions)}'
            )

        self._step += 1
        output = self._apply(action)
        reward = self._step_reward(output) if self._env.step_verifier_code else 0.0
        done = (
            action.action_type == 'done'
            or _signals_done(output)
            or self._step >= self._env.max_steps
        )

        self._trajectory.steps.append((self._obs, action))
        self._trajectory.step_rewards.append(reward)
        self._trajectory.total_reward += reward
        self._done = done
        self._obs = self._observe(output, done=done)
        if done:
            self._trajectory.final_observation = self._obs
        return StepResult(self._obs, reward, done)

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
        start = time.perf_counter()
        self._backend.write_file(_FINAL_VERIFIER, self._env.final_verifier_code.encode('utf-8'))
        stdout = self._backend.exec(
            f'{self._backend.python} -I {_FINAL_VERIFIER}', self._env.timeout_per_step
        )
        json_str = _extract_json_line(stdout)
        if json_str is None:
            raise VerifierError(f'Final verifier did not produce valid JSON. output: {stdout!r}')
        try:
            result = VerifierResult.model_validate_json(json_str)
        except ValueError as exc:
            raise VerifierError(f'Failed to parse final verifier JSON: {exc}') from exc
        return build_run_result(result, (time.perf_counter() - start) * 1000, self.sandbox_id)

    def close(self) -> None:
        """Release the backend."""
        self._backend.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _apply(self, action: Action) -> str:
        """Execute *action* and return its text output."""
        timeout = self._env.timeout_per_step
        try:
            match action.action_type:
                case 'code':
                    return self._run_python('_step.py', action.content)
                case 'bash':
                    return self._backend.exec(action.content, timeout)
                case 'write_file':
                    self._backend.write_file(str(action.path), action.content.encode('utf-8'))
                    return f'wrote {action.path}'
                case 'wait':
                    time.sleep(min(action.amount, timeout))
                    return ''
                case 'done' | 'screenshot':
                    return ''
        except TimeoutError:
            return f'[timed out after {timeout}s]'
        self._backend.act(action)
        return ''

    def _run_python(self, filename: str, code: str) -> str:
        self._backend.write_file(filename, code.encode('utf-8'))
        return self._backend.exec(f'{self._backend.python} {filename}', self._env.timeout_per_step)

    def _observe(self, output: str, *, done: bool) -> Observation:
        screenshot = self._backend.screenshot() if self._env.desktop else None
        return Observation(content=output, step=self._step, done=done, screenshot=screenshot)

    def _step_reward(self, output: str) -> float:
        """Run the step verifier; a broken step verifier yields 0.0 for that step."""
        self._backend.write_file(_STEP_OUTPUT, output.encode('utf-8'))
        self._backend.write_file(_STEP_VERIFIER, self._env.step_verifier_code.encode('utf-8'))
        try:
            stdout = self._backend.exec(
                f'{self._backend.python} -I {_STEP_VERIFIER}',
                self._env.timeout_per_step,
                env={'STEP_OUTPUT_PATH': _STEP_OUTPUT, 'STEP_NUMBER': str(self._step)},
            ).strip()
        except TimeoutError:
            logger.warning('Step verifier timed out at step %d', self._step)
            return 0.0
        json_str = _extract_json_line(stdout)
        try:
            value = json.loads(json_str)['score'] if json_str else float(stdout)
            return max(0.0, min(1.0, float(value)))
        except (ValueError, TypeError, KeyError):
            logger.warning('Step verifier output unparseable at step %d', self._step)
            return 0.0


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
