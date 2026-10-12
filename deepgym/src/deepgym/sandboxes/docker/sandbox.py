"""Docker: one container per sandbox, started with ``--network none`` so it has
loopback only. Needs a running Docker daemon (Docker Desktop, OrbStack, colima, ...).
"""

from __future__ import annotations

from deepgym.sandboxes.cli import CliContainer


class DockerContainer(CliContainer):
    """A running Docker container with no network."""

    cli = 'docker'
    run_flags = ('--network', 'none')
    delete_args = ('rm', '--force')
    network_blocked = True
