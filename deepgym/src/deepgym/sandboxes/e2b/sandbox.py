"""E2B (extra ``e2b``): Firecracker microVMs on E2B's cloud, created with
``allow_internet_access=False`` so E2B itself stops all egress. Needs E2B_API_KEY.

The default template's user is ``user``; every call here passes ``user='root'``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from e2b import (
    CommandExitException,
    SandboxNotRunningException,
    SandboxUnreachableException,
    TimeoutException,
)
from e2b import Sandbox as E2BClient

from deepgym.exceptions import SandboxError
from deepgym.sandboxes.protocol import ExecResult, SandboxTimeoutError

logger = logging.getLogger(__name__)

# E2B deletes a sandbox this long after creation even if delete() never runs.
LIFETIME_S = 3600


class E2BSandbox:
    """A running E2B sandbox with no network."""

    network_blocked = True

    def __init__(self, template: str | None = None) -> None:
        self._sandbox = E2BClient.create(
            template=template, timeout=LIFETIME_S, allow_internet_access=False
        )
        self.id = self._sandbox.sandbox_id

    def exec(
        self,
        command: str,
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """Run *command* as root; output is stdout followed by stderr.

        Raises:
            SandboxTimeoutError: If the command outruns *timeout* seconds.
        """
        try:
            result = self._sandbox.commands.run(
                command,
                user='root',
                cwd=cwd,
                envs=dict(env) if env else None,
                timeout=timeout or LIFETIME_S,
            )
        except CommandExitException as exc:
            # E2B raises on any non-zero exit; that's an ordinary result here.
            return ExecResult(exc.exit_code, exc.stdout + exc.stderr)
        except (SandboxNotRunningException, SandboxUnreachableException) as exc:
            # Both subclass TimeoutException, but mean the sandbox is gone.
            raise SandboxError(f'E2B sandbox {self.id} is not reachable: {exc}') from exc
        except TimeoutException as exc:
            raise SandboxTimeoutError(f'command exceeded {timeout}s') from exc
        return ExecResult(result.exit_code, result.stdout + result.stderr)

    def upload(self, content: bytes, path: str) -> None:
        """Write *content* to *path* as root (E2B creates parent directories)."""
        self._sandbox.files.write(path, content, user='root')

    def delete(self) -> None:
        """Kill the sandbox; errors are logged (it may already be gone)."""
        try:
            self._sandbox.kill()
        except Exception:
            logger.warning('Failed to delete e2b sandbox %s', self.id)
