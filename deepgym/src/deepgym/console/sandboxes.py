"""Sandbox routes: live DeepGym containers of the local CLIs, and killing one.

Cloud providers (Daytona, Modal, E2B) are not listed; use their own dashboards.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi import Path as PathParam

from deepgym.console.schemas import LocalProvider, ProviderSandboxes
from deepgym.exceptions import SandboxError
from deepgym.sandboxes.apple import AppleContainer
from deepgym.sandboxes.cli import CliContainer
from deepgym.sandboxes.docker import DockerContainer

router = APIRouter(prefix='/sandboxes', tags=['sandboxes'])

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
def kill_sandbox(
    provider: LocalProvider,
    sandbox_id: str = PathParam(pattern=r'^deepgym-[0-9a-z]+$'),
) -> None:
    """Force-remove one DeepGym sandbox; only ``deepgym-*`` names are accepted."""
    try:
        _PROVIDERS[provider].remove(sandbox_id)
    except SandboxError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
