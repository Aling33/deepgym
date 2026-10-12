"""Request and response models for the console API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deepgym.models import Action, RunResult, Trajectory
from deepgym.sandboxes.cli import RunningSandbox

RunMode = Literal['local', 'daytona', 'auto', 'apple', 'docker', 'modal', 'e2b']
RunStatus = Literal['queued', 'running', 'completed', 'failed']
EnvKind = Literal['single-turn', 'multi-turn', 'computer-use']
LocalProvider = Literal['apple', 'docker']


class EnvironmentSummary(BaseModel):
    """One registry entry, as listed in the environments table."""

    id: str
    """Name to pass to load_environment, e.g. 'coin_change' or 'cyber/web_path_traversal_toy'."""

    name: str
    kind: EnvKind
    type: str
    difficulty: str
    domain: str
    family: str = ''
    tags: list[str] = Field(default_factory=list)
    variants: int = 1


class EnvironmentDetail(EnvironmentSummary):
    """An environment with its task, verifier source and reference solution."""

    variant: int = 0
    task: str
    verifier: str
    reference: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class RunCreate(BaseModel):
    """Start one run per environment, all with the same solution and provider."""

    environments: list[str] = Field(min_length=1, max_length=50)
    mode: RunMode = 'local'
    solution: str | None = None
    """Solution source; None runs each environment's reference solution."""


class RunConfig(BaseModel):
    """What the console allows when starting runs."""

    local_custom_code: bool
    """Whether custom solutions may run on this machine (--allow-local-exec)."""


class RunSpec(BaseModel):
    """What one run executes: an environment and the solution to score against it."""

    model_config = ConfigDict(frozen=True)

    environment: str
    solution: str
    reference: bool


class RunSummary(BaseModel):
    """A run as listed in the runs table."""

    id: str
    group_id: str
    """Shared by runs started together (a small eval)."""

    environment: str
    mode: RunMode
    provider: str
    """Where the run executed: 'local', 'daytona' or a sandbox provider."""

    reference: bool
    status: RunStatus
    score: float | None = None
    passed: bool | None = None
    error_type: str | None = None
    duration_ms: float | None = None
    created_at: str
    finished_at: str | None = None


class RunDetail(RunSummary):
    """A run with its solution, error and full verifier result."""

    solution: str
    error: str | None = None
    result: RunResult | None = None


class EpisodeCreate(BaseModel):
    """A finished episode to store for replay."""

    environment: str = ''
    trajectory: Trajectory
    result: RunResult | None = None


class EpisodeSummary(BaseModel):
    """An episode as listed in the episodes table."""

    id: str
    environment: str
    steps: int
    total_reward: float
    score: float | None = None
    passed: bool | None = None
    created_at: str


class Frame(BaseModel):
    """One replay frame: an observation and the action taken from it (none for the last)."""

    index: int
    content: str
    done: bool = False
    metadata: dict[str, object] | None = None
    action: Action | None = None
    reward: float | None = None
    has_screenshot: bool = False


class EpisodeDetail(EpisodeSummary):
    """An episode with every frame (screenshots are served separately) and its result."""

    frames: list[Frame]
    result: RunResult | None = None


class ProviderSandboxes(BaseModel):
    """Live DeepGym sandboxes of one local container CLI."""

    provider: LocalProvider
    available: bool
    error: str | None = None
    sandboxes: list[RunningSandbox] = Field(default_factory=list)
