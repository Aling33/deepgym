"""Persist console runs: queued when submitted, then updated by the runner."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from deepgym.console.db import connect, init_db, utc_now
from deepgym.console.schemas import RunDetail, RunMode, RunSpec, RunSummary
from deepgym.models import RunResult

_SUMMARY_COLUMNS = (
    'id, group_id, environment, mode, provider, reference, status, score, passed, '
    'error_type, duration_ms, created_at, finished_at'
)
# Columns list() may filter on; keys are code-defined, values are bound parameters.
_FILTER_COLUMNS = frozenset({'status', 'environment', 'provider', 'group_id'})


class RunStore:
    """Runs table of the console database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        init_db(path)

    def create_group(
        self, specs: Sequence[RunSpec], mode: RunMode, provider: str
    ) -> list[RunSummary]:
        """Queue one run per spec under a shared group id.

        Args:
            specs: What each run executes.
            mode: The provider mode the caller asked for.
            provider: Where the runs will execute (``DeepGym.backend``).

        Returns:
            The queued runs, in spec order.
        """
        group_id = uuid4().hex[:12]
        now = utc_now()
        runs = [
            RunSummary(
                id=uuid4().hex[:12],
                group_id=group_id,
                environment=spec.environment,
                mode=mode,
                provider=provider,
                reference=spec.reference,
                status='queued',
                created_at=now,
            )
            for spec in specs
        ]
        with connect(self._path) as conn:
            conn.executemany(
                'INSERT INTO runs (id, group_id, environment, mode, provider, reference, '
                'solution, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [
                    (run.id, group_id, run.environment, mode, provider, spec.reference,
                     spec.solution, 'queued', now)
                    for run, spec in zip(runs, specs)
                ],
            )  # fmt: skip
        return runs

    def start(self, run_id: str) -> None:
        """Mark a queued run as running."""
        with connect(self._path) as conn:
            conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))

    def complete(self, run_id: str, result: RunResult, duration_ms: float) -> None:
        """Record the verifier result of a run that finished."""
        with connect(self._path) as conn:
            conn.execute(
                "UPDATE runs SET status = 'completed', score = ?, passed = ?, error_type = ?, "
                'result = ?, duration_ms = ?, finished_at = ? WHERE id = ?',
                (result.score, result.passed, result.error_type, result.model_dump_json(),
                 duration_ms, utc_now(), run_id),
            )  # fmt: skip

    def fail(self, run_id: str, error_type: str, error: str, duration_ms: float) -> None:
        """Record a run that raised instead of producing a verifier result."""
        with connect(self._path) as conn:
            conn.execute(
                "UPDATE runs SET status = 'failed', score = 0, passed = 0, error_type = ?, "
                'error = ?, duration_ms = ?, finished_at = ? WHERE id = ?',
                (error_type, error, duration_ms, utc_now(), run_id),
            )

    def fail_unfinished(self) -> int:
        """Fail runs a previous console process left queued or running; return how many.

        Returns:
            Number of runs marked failed with ``error_type='interrupted'``.
        """
        # ponytail: assumes one console process per database file.
        with connect(self._path) as conn:
            cursor = conn.execute(
                "UPDATE runs SET status = 'failed', error_type = 'interrupted', "
                "error = 'The console stopped before this run finished.', finished_at = ? "
                "WHERE status IN ('queued', 'running')",
                (utc_now(),),
            )
            return cursor.rowcount

    def list(self, filters: dict[str, str | None], limit: int = 200) -> list[RunSummary]:
        """Return the newest runs matching every non-None filter.

        Args:
            filters: Column -> value, for status, environment, provider or group_id.
            limit: Maximum number of runs to return.

        Returns:
            Runs, newest first.
        """
        active = {key: value for key, value in filters.items() if value is not None}
        unknown = active.keys() - _FILTER_COLUMNS
        if unknown:
            raise ValueError(f'Cannot filter runs by {sorted(unknown)}')
        where = ' AND '.join(f'{key} = ?' for key in active) or '1'
        with connect(self._path) as conn:
            rows = conn.execute(
                f'SELECT {_SUMMARY_COLUMNS} FROM runs WHERE {where} '
                'ORDER BY created_at DESC, rowid DESC LIMIT ?',
                (*active.values(), limit),
            ).fetchall()
        return [RunSummary.model_validate(dict(row)) for row in rows]

    def get(self, run_id: str) -> RunDetail | None:
        """Return one run with its solution and verifier result, or None if unknown."""
        with connect(self._path) as conn:
            row = conn.execute('SELECT * FROM runs WHERE id = ?', (run_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['result'] = json.loads(data['result']) if data['result'] else None
        return RunDetail.model_validate(data)
