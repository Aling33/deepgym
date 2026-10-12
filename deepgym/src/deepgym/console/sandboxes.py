"""Sandbox routes: live DeepGym containers of the local CLIs, and killing one.

Cloud providers (Daytona, Modal, E2B) are not listed; use their own dashboards.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status

from deepgym.console.schemas import LocalProvider, ProviderSandboxes
from deepgym.exceptions import SandboxError
from deepgym.sandboxes.apple import AppleContainer
from deepgym.sandboxes.cli import CliContainer
from deepgym.sandboxes.docker import DockerContainer

router = APIRouter(prefix='/sandboxes', tags=['sandboxes'])

# The names CliContainer gives the sandboxes it starts.
_SANDBOX_NAME = re.compile(r'deepgym-[0-9a-f]+')

_PROVIDERS: dict[LocalProvider, type[CliContainer]] = {
    'apple': AppleContainer,
    'docker': DockerContainer,
}


@router.get('', response_model=list[ProviderSandboxes])
def list_sandboxes() -> list[ProviderSandboxes]:
    """List live DeepGym sandboxes per local provider; an unreachable CLI is reported."""
    return [_listing(provider, cls) for provider, cls in _PROVIDERS.items()]


def _listing(provider: LocalProvider, cls: type[CliContainer]) -> ProviderSandboxes:
    try:
        return ProviderSandboxes(provider=provider, available=True, sandboxes=cls.running())
    except SandboxError as exc:
        return ProviderSandboxes(provider=provider, available=False, error=str(exc))


@router.delete('/{provider}/{sandbox_id}', status_code=status.HTTP_204_NO_CONTENT)
def kill_sandbox(provider: LocalProvider, sandbox_id: str) -> None:
    """Force-remove one DeepGym sandbox; only ``deepgym-*`` names are accepted.

    Raises:
        HTTPException: 400 for any other name, 502 if the CLI fails.
    """
    if not _SANDBOX_NAME.fullmatch(sandbox_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'{sandbox_id!r} is not a DeepGym sandbox (deepgym-<id>)',
        )
    try:
        _PROVIDERS[provider].remove(sandbox_id)
    except SandboxError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
