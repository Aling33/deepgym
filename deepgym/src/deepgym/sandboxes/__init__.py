"""Sandbox providers: one folder per provider, each implementing :class:`Sandbox`.

``open_sandbox('docker')`` starts a fresh sandbox by provider name. Daytona is
opened by :class:`~deepgym.core.DeepGym` itself because it needs a client and the
environment's snapshot. Provider SDKs are optional extras, imported only when that
provider is used.
"""

from __future__ import annotations

from typing import Literal

from deepgym.exceptions import DeepGymError
from deepgym.sandboxes.protocol import ExecResult, Sandbox, SandboxTimeoutError

Provider = Literal['apple', 'docker', 'modal', 'e2b']
PROVIDERS: tuple[Provider, ...] = ('apple', 'docker', 'modal', 'e2b')

__all__ = [
    'PROVIDERS',
    'ExecResult',
    'Provider',
    'Sandbox',
    'SandboxTimeoutError',
    'check_provider',
    'open_sandbox',
]


def open_sandbox(provider: Provider) -> Sandbox:
    """Start a fresh sandbox from *provider*.

    Raises:
        SandboxError: If the sandbox can't be started.
    """
    match provider:
        case 'apple':
            from deepgym.sandboxes.apple import AppleContainer

            return AppleContainer()
        case 'docker':
            from deepgym.sandboxes.docker import DockerContainer

            return DockerContainer()
        case 'modal':
            from deepgym.sandboxes.modal import ModalSandbox

            return ModalSandbox()
        case 'e2b':
            from deepgym.sandboxes.e2b import E2BSandbox

            return E2BSandbox()
    raise DeepGymError(f'Unknown sandbox provider {provider!r}; choose from {PROVIDERS}')


def check_provider(provider: Provider) -> None:
    """Fail fast if *provider* can't be used on this machine.

    Raises:
        DeepGymError: If its CLI isn't running or its SDK isn't installed.
    """
    if provider in ('apple', 'docker'):
        from deepgym.sandboxes.apple import AppleContainer
        from deepgym.sandboxes.docker import DockerContainer

        cls = AppleContainer if provider == 'apple' else DockerContainer
        if not cls.available():
            hint = '`container system start`' if provider == 'apple' else 'start the Docker daemon'
            raise DeepGymError(f"mode='{provider}' needs the {cls.cli} CLI running ({hint})")
        return
    try:
        __import__(f'deepgym.sandboxes.{provider}')
    except ImportError as exc:
        raise DeepGymError(
            f"mode='{provider}' needs its SDK: pip install 'deepgym[{provider}]'"
        ) from exc
