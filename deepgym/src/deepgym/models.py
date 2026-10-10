"""Pydantic data models for DeepGym."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, model_validator


class Environment(BaseModel):
    """Define a task environment for RL evaluation.

    The environment specifies the task prompt, verifier logic, execution
    constraints, and optional pre-built sandbox snapshot.
    """

    name: str | None = None
    """Optional stable environment identifier used for routing and reporting."""

    task: str
    """The task description / prompt presented to the model."""

    type: Literal['coding', 'computer-use', 'tool-use'] = 'coding'
    """Environment type: coding, computer-use, or tool-use."""

    verifier_code: str = ''
    """Python source code of the verifier script."""

    verifier_path: Path | None = None
    """Optional filesystem path to a verifier script (alternative to inline code)."""

    @model_validator(mode='after')
    def check_verifier_source(self) -> Environment:
        """Ensure at least one of verifier_code or verifier_path is provided."""
        if not self.verifier_code and self.verifier_path is None:
            raise ValueError('Either verifier_code or verifier_path must be provided')
        return self

    language: str = 'python'
    """Programming language for the solution."""

    timeout: int = Field(default=30, ge=1)
    """Maximum execution time in seconds."""

    difficulty: Literal['easy', 'medium', 'hard'] = 'medium'
    """Task difficulty level."""

    domain: str = 'coding'
    """Task domain (e.g. coding, math, reasoning)."""

    tags: list[str] = Field(default_factory=list)
    """Freeform tags for filtering and categorization."""

    test_cases: list[dict] | None = None
    """Optional list of test-case dicts passed to the verifier."""

    snapshot: str | None = None
    """Pre-built Daytona snapshot name with dependencies pre-installed."""

    env_vars: dict[str, str] | None = None
    """Environment variables to inject into the sandbox."""


class CaseResult(BaseModel):
    """Result of a single test case within a verifier.

    Enable fine-grained reward shaping for GRPO training by reporting
    which specific tests passed or failed, along with diagnostic summaries.
    """

    id: str = ''
    """Identifier for this test case (e.g. 'test_0', 'edge_case_empty')."""

    passed: bool
    """Whether this specific test case passed."""

    score: float = Field(default=1.0, ge=0.0, le=1.0)
    """Score for this test case (0.0-1.0). Defaults to 1.0 if passed."""

    input_summary: str = ''
    """Brief summary of the test input (truncated for large inputs)."""

    expected_summary: str = ''
    """Brief summary of the expected output."""

    actual_summary: str = ''
    """Brief summary of the actual output produced."""

    error: str | None = None
    """Error message if the test case raised an exception."""

    execution_time_ms: float = 0.0
    """Execution time for this specific test case in milliseconds."""


class VerifierResult(BaseModel):
    """Represent structured output from a verifier script.

    Verifiers must print a JSON object to stdout conforming to this schema.
    """

    schema_version: str = '1.0'
    """Protocol version for forward compatibility."""

    score: float = Field(ge=0.0, le=1.0)
    """Numeric score between 0 and 1."""

    passed: bool
    """Whether the solution passed the verifier's acceptance criteria."""

    details: str | None = None
    """Optional human-readable explanation."""

    reward_components: dict[str, float] | None = None
    """Breakdown of shaped rewards (e.g. correctness, style, efficiency)."""

    metrics: dict[str, Any] | None = None
    """Execution metrics (e.g. execution_time, memory_used)."""

    seed: int | None = None
    """Random seed used, for reproducibility."""

    truncated: bool = False
    """Whether execution was cut short (e.g. timeout)."""

    error_type: str | None = None
    """Category of error if one occurred (timeout, runtime_error, import_error, etc.)."""

    cases: list[CaseResult] | None = None
    """Per-test-case breakdown. Enable fine-grained reward shaping for GRPO training."""


class RunResult(BaseModel):
    """Represent the result of a single environment run."""

    score: float = Field(ge=0, le=1)
    """Normalized score from the verifier."""

    passed: bool
    """Whether the solution passed."""

    output: str
    """Verifier details/summary string."""

    stderr: str
    """Captured stderr from verifier execution."""

    exit_code: int
    """Process exit code."""

    execution_time_ms: float
    """Wall-clock execution time in milliseconds."""

    sandbox_id: str
    """Identifier of the sandbox used for this run."""

    reward_components: dict[str, float] | None = None
    """Shaped reward breakdown passed through from the verifier."""

    metrics: dict[str, Any] | None = None
    """Execution metrics passed through from the verifier."""

    seed: int | None = None
    """Random seed used by the verifier, for reproducibility."""

    truncated: bool = False
    """Whether execution was cut short."""

    error_type: str | None = None
    """Category of error if one occurred."""

    cases: list[CaseResult] | None = None
    """Per-test-case breakdown passed through from the verifier."""


class Observation(BaseModel):
    """Represent what the agent sees at each step."""

    content: str
    """Text content (stdout, page content, file listing, etc.)."""

    step: int
    """Current step number."""

    done: bool = False
    """Whether the episode is finished."""

    screenshot: str | None = None
    """Base64-encoded PNG of the desktop, at display resolution (desktop sessions only)."""

    metadata: dict[str, Any] | None = None
    """Optional structured metadata for the observation."""


ShellActionType = Literal['code', 'bash', 'write_file']
GuiActionType = Literal[
    'click',
    'double_click',
    'right_click',
    'move',
    'drag',
    'type',
    'key',
    'scroll',
    'screenshot',
    'wait',
]
ActionType = Literal[ShellActionType, GuiActionType, 'done']

GUI_ACTIONS: frozenset[GuiActionType] = frozenset(get_args(GuiActionType))

_POINTER_ACTIONS = frozenset({'click', 'double_click', 'right_click', 'move', 'scroll', 'drag'})
_TEXT_ACTIONS = frozenset({'type', 'key'})
_SCROLL_DIRECTIONS = frozenset({'up', 'down', 'left', 'right'})


class Action(BaseModel):
    """Represent an agent action.

    Shell actions (code, bash, write_file) run in the session work directory.
    GUI actions drive the desktop; coordinates are screenshot pixels.
    """

    action_type: ActionType = 'code'
    """What to do. ``done`` ends the episode."""

    content: str = ''
    """Code, shell command, file contents, text to type, key chord ('ctrl+s'),
    or scroll direction (up/down/left/right)."""

    x: int | None = Field(default=None, ge=0)
    """Pointer x for click/move/scroll, or drag start."""

    y: int | None = Field(default=None, ge=0)
    """Pointer y for click/move/scroll, or drag start."""

    to_x: int | None = Field(default=None, ge=0)
    """Drag end x."""

    to_y: int | None = Field(default=None, ge=0)
    """Drag end y."""

    path: str | None = None
    """Target path for write_file, relative to the work directory."""

    amount: int = Field(default=1, ge=1, le=60)
    """Scroll clicks, or seconds for wait."""

    @model_validator(mode='after')
    def check_arguments(self) -> Action:
        """Reject actions missing the arguments their type needs."""
        kind = self.action_type
        if kind in _POINTER_ACTIONS and (self.x is None or self.y is None):
            raise ValueError(f'{kind} needs x and y')
        if kind == 'drag' and (self.to_x is None or self.to_y is None):
            raise ValueError('drag needs to_x and to_y')
        if kind == 'scroll' and self.content not in _SCROLL_DIRECTIONS:
            raise ValueError(f'scroll content must be one of {sorted(_SCROLL_DIRECTIONS)}')
        if kind in _TEXT_ACTIONS and not self.content:
            raise ValueError(f'{kind} needs content')
        if kind == 'write_file':
            rel = PurePosixPath(self.path or '')
            if not rel.parts or rel.is_absolute() or '..' in rel.parts:
                raise ValueError('write_file needs a relative path without ".."')
        return self


class Trajectory(BaseModel):
    """Record of a complete multi-turn episode."""

    steps: list[tuple[Observation, Action]] = Field(default_factory=list)
    """Sequence of (observation, action) pairs."""

    final_observation: Observation | None = None
    """The last observation after the final action or termination."""

    total_reward: float = 0.0
    """Cumulative reward for the episode."""

    step_rewards: list[float] = Field(default_factory=list)
    """Per-step reward values."""


class MultiTurnEnvironment(BaseModel):
    """Define a multi-turn environment where agents take multiple steps.

    One episode runs in one live sandbox: files are written, setup runs,
    the agent acts step by step, then the final verifier inspects the state.
    """

    name: str | None = None
    """Optional stable environment identifier used for routing and reporting."""

    task: str
    """The task description / prompt presented to the agent."""

    files: dict[str, str] = Field(default_factory=dict)
    """Text files written into the work directory before setup (relative path -> content)."""

    setup_script: str = ''
    """Bash run in the work directory after files are written (start servers, open apps)."""

    setup_code: str = ''
    """Python run after setup_script. Its output is the first observation."""

    step_verifier_code: str = ''
    """Optional verifier run after each step (for intermediate rewards)."""

    final_verifier_code: str = ''
    """Verifier run at the end to compute final score."""

    max_steps: int = Field(default=10, ge=1)
    """Maximum number of steps before forced termination."""

    timeout_per_step: int = Field(default=30, ge=1)
    """Timeout per individual step in seconds."""

    allowed_actions: frozenset[ActionType] = frozenset({'code', 'bash', 'write_file', 'done'})
    """Action types the agent may use. Anything else is rejected."""

    desktop: bool = False
    """Start a desktop (Xvfb + xfce) and return screenshots. Needs the Daytona backend."""

    snapshot: str | None = None
    """Daytona snapshot to boot. None uses Daytona's default image (has xfce + Chromium)."""

    difficulty: Literal['easy', 'medium', 'hard'] = 'medium'
    """Task difficulty level."""

    domain: str = 'agentic'
    """Task domain (e.g. browser, desktop, terminal)."""

    tags: list[str] = Field(default_factory=list)
    """Freeform tags for filtering and categorization."""

    type: Literal['multi-turn'] = 'multi-turn'
    """Environment type discriminator."""

    @model_validator(mode='after')
    def check_desktop_actions(self) -> MultiTurnEnvironment:
        """Reject GUI actions on environments without a desktop."""
        if not self.desktop and self.allowed_actions & GUI_ACTIONS:
            raise ValueError('GUI actions need desktop=True')
        return self


class BatchResult(BaseModel):
    """Aggregate results from running multiple solutions against one environment."""

    results: list[RunResult]
    total: int
    passed: int
    failed: int
    avg_score: float
    execution_time_ms: float
    """Total wall-clock time for the entire batch."""


class EvalResult(BaseModel):
    """Results from evaluating a model against an entire suite."""

    suite: str
    """Name of the evaluation suite."""

    model_name: str
    """Identifier for the model being evaluated."""

    pass_rate: float
    """Fraction of tasks passed (0.0 - 1.0)."""

    results: list[RunResult]
    total: int
    passed: int
    avg_score: float


# ---------------------------------------------------------------------------
# Job models (async job execution)
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    """Status of an async job."""

    queued = 'queued'
    starting = 'starting'
    running = 'running'
    scoring = 'scoring'
    completed = 'completed'
    failed = 'failed'
    cancelled = 'cancelled'


class Job(BaseModel):
    """Represent an async single-run job."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: RunResult | None = None
    error: str | None = None


class BatchJob(BaseModel):
    """Represent an async batch-run job."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total: int = 0
    completed_count: int = 0
    result: BatchResult | None = None
    error: str | None = None
