"""Daytona (extra ``daytona``): cloud or self-hosted sandboxes.

:class:`DaytonaSandbox` is the provider the judge uses. ``create_sandbox`` and
``cleanup_sandbox`` hand out raw Daytona sandboxes for code that needs Daytona's
full API (desktop sessions, SWE-bench Pro).
"""

from __future__ import annotations

import logging
import shlex
from collections.abc import Mapping
from typing import TYPE_CHECKING

from deepgym.exceptions import SandboxError
from deepgym.models import Environment
from deepgym.sandboxes.protocol import ExecResult, SandboxTimeoutError

if TYPE_CHECKING:
    from daytona import Daytona, Sandbox

logger = logging.getLogger(__name__)


def create_sandbox(env: Environment, daytona: Daytona) -> Sandbox:
    """Create a raw Daytona sandbox from ``env.snapshot``, or a Debian Python 3.12 image.

    Raises:
        SandboxError: If the daytona SDK is missing or creation fails.
    """
    try:
        from daytona import CreateSandboxFromImageParams, CreateSandboxFromSnapshotParams, Image
    except ImportError as exc:
        raise SandboxError(
            "daytona is required. Install it with: pip install 'deepgym[daytona]'"
        ) from exc
    if env.snapshot:
        params = CreateSandboxFromSnapshotParams(snapshot=env.snapshot, ephemeral=True)
    else:
        params = CreateSandboxFromImageParams(image=Image.debian_slim('3.12'), ephemeral=True)
    try:
        return daytona.create(params)
    except Exception as exc:
        raise SandboxError(f'Failed to create sandbox: {exc}') from exc


def cleanup_sandbox(sandbox: Sandbox, daytona: Daytona, *, wait: bool = False) -> None:
    """Delete a raw Daytona sandbox, logging rather than raising errors."""
    try:
        daytona.delete(sandbox, wait=wait)
    except Exception:
        logger.warning('Failed to clean up sandbox %s', getattr(sandbox, 'id', '?'))


def is_timeout(exc: Exception) -> bool:
    """Return True if a Daytona exec failed because the command outran its timeout."""
    try:
        from daytona import DaytonaProcessExecutionTimeoutError
    except ImportError:
        return False
    return isinstance(exc, DaytonaProcessExecutionTimeoutError)


class DaytonaSandbox:
    """A Daytona sandbox for one judge run, deleted by :meth:`delete`."""

    network_blocked = False

    def __init__(self, daytona: Daytona, env: Environment) -> None:
        self._daytona = daytona
        self._sandbox = create_sandbox(env, daytona)
        self.id = str(getattr(self._sandbox, 'id', 'unknown'))

    def exec(
        self,
        command: str,
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Run *command* with sh as the sandbox's default user (root or a sudoer).

        Raises:
            SandboxTimeoutError: If the command outruns *timeout* seconds.
        """
        try:
            response = self._sandbox.process.exec(
                f'sh -c {shlex.quote(command)}',
                cwd=cwd,
                env=dict(env) if env else None,
                timeout=timeout,
            )
        except Exception as exc:
            if is_timeout(exc):
                raise SandboxTimeoutError(f'command exceeded {timeout}s') from exc
            raise
        return ExecResult(response.exit_code, response.result)

    def upload(self, content: bytes, path: str) -> None:
        """Write *content* to *path* in the sandbox."""
        self._sandbox.fs.upload_file(content, path)

    def delete(self) -> None:
        """Delete the sandbox without waiting; errors are logged."""
        cleanup_sandbox(self._sandbox, self._daytona)
