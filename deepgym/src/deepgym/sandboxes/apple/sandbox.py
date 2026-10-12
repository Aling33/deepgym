"""Apple ``container`` (https://github.com/apple/container): one lightweight Linux VM per
sandbox on macOS. Needs the CLI with its service running (``container system start``).

Apple's CLI has no ``--network none``, so the provider doesn't block egress. The VM
gets CAP_SYS_ADMIN and CAP_NET_ADMIN only so root can build an offline network
namespace (with loopback up) for untrusted code, which always runs as a non-root
user with every capability dropped.
"""

from __future__ import annotations

import shutil
import subprocess

from deepgym.sandboxes.cli import CliContainer


class AppleContainer(CliContainer):
    """A running Apple container VM."""

    cli = 'container'
    run_flags = ('--cap-add', 'CAP_SYS_ADMIN', '--cap-add', 'CAP_NET_ADMIN')
    delete_args = ('delete', '--force')
    network_blocked = False

    @classmethod
    def available(cls) -> bool:
        """Return True if the container CLI is installed and its service is running."""
        if shutil.which(cls.cli) is None:
            return False
        try:
            status = subprocess.run(
                [cls.cli, 'system', 'status'], capture_output=True, text=True, timeout=15
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return status.returncode == 0 and 'running' in status.stdout
