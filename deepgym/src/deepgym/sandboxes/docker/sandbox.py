"""Docker: one container per sandbox, started with ``--network none`` so it has
loopback only. Needs a running Docker daemon (Docker Desktop, OrbStack, colima, ...).

Containers share the Docker host's kernel, so this is weaker isolation than the
VM-based providers (Apple container, E2B, Daytona). A process limit and
no-new-privileges keep a fork bomb or a setuid binary from reaching past the
container.
"""

from __future__ import annotations

import json

from deepgym.sandboxes.cli import CliContainer, RunningSandbox


class DockerContainer(CliContainer):
    """A running Docker container with no network."""

    cli = 'docker'
    run_flags = ('--network', 'none', '--pids-limit', '512', '--security-opt', 'no-new-privileges')
    delete_args = ('rm', '--force')
    list_args = ('ps', '--filter', 'label=deepgym=1', '--format', '{{json .}}')
    network_blocked = True

    @staticmethod
    def _parse_listing(output: str) -> list[RunningSandbox]:
        """Parse ``docker ps --format '{{json .}}'``: one JSON object per line."""
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
        return [
            RunningSandbox(
                id=row['Names'], image=row['Image'], state=row['State'], started=row['CreatedAt']
            )
            for row in rows
        ]
