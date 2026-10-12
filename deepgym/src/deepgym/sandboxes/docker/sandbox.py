"""Docker: one container per sandbox, started with ``--network none`` so it has
loopback only. Needs a running Docker daemon (Docker Desktop, OrbStack, colima, ...).

Containers share the Docker host's kernel, so this is weaker isolation than the
VM-based providers (Apple container, E2B, Daytona). A process limit and
no-new-privileges keep a fork bomb or a setuid binary from reaching past the
container.
"""

from __future__ import annotations

from deepgym.sandboxes.cli import CliContainer


class DockerContainer(CliContainer):
    """A running Docker container with no network."""

    cli = 'docker'
    run_flags = ('--network', 'none', '--pids-limit', '512', '--security-opt', 'no-new-privileges')
    delete_args = ('rm', '--force')
    network_blocked = True
