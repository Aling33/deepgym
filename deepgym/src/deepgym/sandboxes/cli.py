"""Container CLIs (Apple ``container``, ``docker``) as sandboxes.

Each sandbox is one detached ``sleep infinity`` container. Commands go through
``<cli> exec`` and files through its stdin. The two CLIs take the same flags for
everything used here, so a provider only names its CLI and how it differs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from typing import ClassVar
from uuid import uuid4

from deepgym.exceptions import SandboxError
from deepgym.sandboxes.protocol import ExecResult, SandboxTimeoutError

DEFAULT_IMAGE = os.environ.get('DEEPGYM_CONTAINER_IMAGE', 'python:3.12-slim')
# Caps per sandbox, so hostile code can't starve the machine running the containers.
_LIMITS = ('--cpus', '2', '--memory', '2g')
_START_TIMEOUT_S = 300
# Exit codes from coreutils `timeout`: 124 after SIGTERM, 137 after the follow-up SIGKILL.
_TIMEOUT_EXIT_CODES = frozenset({124, 137})


class CliContainer:
    """A running container, deleted by :meth:`delete`."""

    cli: ClassVar[str]
    run_flags: ClassVar[tuple[str, ...]] = ()
    delete_args: ClassVar[tuple[str, ...]]
    network_blocked: ClassVar[bool]

    def __init__(self, image: str = DEFAULT_IMAGE) -> None:
        self.id = f'deepgym-{uuid4().hex[:12]}'
        started = self._cli(
            'run', '--detach', '--rm', '--name', self.id, '--label', 'deepgym=1',
            *_LIMITS, *self.run_flags, image, 'sleep', 'infinity',
            timeout=_START_TIMEOUT_S,
        )  # fmt: skip
        if started.returncode != 0:
            raise SandboxError(f'Failed to start container: {started.stderr.decode()[-1000:]}')

    @classmethod
    def available(cls) -> bool:
        """Return True if the CLI is installed and its daemon or service answers."""
        if shutil.which(cls.cli) is None:
            return False
        try:
            info = subprocess.run([cls.cli, 'info'], capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return False
        return info.returncode == 0

    def exec(
        self,
        command: str,
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Run *command* with sh in the container; output is stdout followed by stderr.

        Raises:
            SandboxTimeoutError: If the command outruns *timeout* seconds.
        """
        argv = ['exec']
        if cwd:
            argv += ['--workdir', cwd]
        for key, value in (env or {}).items():
            argv += ['--env', f'{key}={value}']
        argv.append(self.id)
        if timeout:
            argv += ['timeout', '--kill-after=2', str(timeout)]
        argv += ['sh', '-c', command]
        start = time.monotonic()
        try:
            done = self._cli(*argv, timeout=(timeout or 3600) + 15)
        except subprocess.TimeoutExpired as exc:
            raise SandboxTimeoutError(f'command exceeded {timeout}s') from exc
        if timeout and done.returncode in _TIMEOUT_EXIT_CODES:
            if time.monotonic() - start >= timeout:
                raise SandboxTimeoutError(f'command exceeded {timeout}s')
        output = done.stdout.decode('utf-8', 'replace') + done.stderr.decode('utf-8', 'replace')
        return ExecResult(done.returncode, output)

    def upload(self, content: bytes, path: str) -> None:
        """Write *content* to *path* inside the container, creating parent directories.

        Raises:
            SandboxError: If the write fails.
        """
        script = 'mkdir -p "$(dirname "$1")" && cat > "$1"'
        done = self._cli(
            'exec', '--interactive', self.id, 'sh', '-c', script, 'upload', path,
            input=content, timeout=120,
        )  # fmt: skip
        if done.returncode != 0:
            raise SandboxError(f'Failed to upload {path}: {done.stderr.decode()[-500:]}')

    def delete(self) -> None:
        """Stop and remove the container; errors are ignored (it may already be gone)."""
        try:
            self._cli(*self.delete_args, self.id, timeout=60)
        except (SandboxError, subprocess.TimeoutExpired):
            pass

    @classmethod
    def _cli(
        cls, *args: str, input: bytes | None = None, timeout: float
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [cls.cli, *args], input=input, capture_output=True, timeout=timeout, check=False
            )
        except FileNotFoundError as exc:
            raise SandboxError(f'{cls.cli} CLI not found') from exc
