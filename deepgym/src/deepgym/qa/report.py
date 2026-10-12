"""QA report model, per-environment JSON files, and the CLI table."""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

SKIPPED = 'skipped'
"""Name of the single check a report carries when the environment isn't checkable."""

_COLUMNS = {
    'reference_passes': 'ref',
    'deterministic': 'det',
    'empty_fails': 'empty',
    'stub_fails': 'stub',
    'hack_resistant': 'hack',
    'difficulty': 'diff',
}


class QACheck(BaseModel):
    """Outcome of one quality check on one environment."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    details: str


class QAReport(BaseModel):
    """Quality-gate verdict for one environment, saved as ``<env>.json``."""

    model_config = ConfigDict(frozen=True)

    environment: str
    checks: list[QACheck]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def passed(self) -> bool:
        """True when every check passed."""
        return all(check.passed for check in self.checks)

    @property
    def status(self) -> Literal['PASS', 'FAIL', 'SKIP']:
        """PASS, FAIL or SKIP, as shown in the table."""
        if any(check.name == SKIPPED for check in self.checks):
            return 'SKIP'
        return 'PASS' if self.passed else 'FAIL'


def write_report(report: QAReport) -> Path:
    """Write *report* to ``$DEEPGYM_QA_DIR/<env>.json`` (default ``~/.deepgym/qa``).

    Slashes in the environment name become underscores in the file name.

    Returns:
        Path of the written file.
    """
    directory = Path(os.environ.get('DEEPGYM_QA_DIR') or Path.home() / '.deepgym' / 'qa')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{report.environment.replace("/", "_")}.json'
    path.write_text(report.model_dump_json(indent=2) + '\n', encoding='utf-8')
    return path


def _cell(check: QACheck | None) -> str:
    if check is None:
        return '-'
    return 'ok' if check.passed else 'FAIL'


def format_table(reports: Sequence[QAReport]) -> str:
    """Render one row per environment, then the details of failed and difficulty checks."""
    width = max(len('environment'), *(len(report.environment) for report in reports))
    rows = [['environment'.ljust(width), *_COLUMNS.values(), 'result']]
    notes: list[str] = []
    for report in reports:
        by_name = {check.name: check for check in report.checks}
        rows.append(
            [
                report.environment.ljust(width),
                *(_cell(by_name.get(name)) for name in _COLUMNS),
                report.status,
            ]
        )
        notes.extend(
            f'{report.environment}: {check.name}: {check.details}'
            for check in report.checks
            if not check.passed or check.name == 'difficulty'
        )
    table = '\n'.join('  '.join(f'{cell:<5}' for cell in row).rstrip() for row in rows)
    statuses = [report.status for report in reports]
    summary = (
        f'{statuses.count("PASS")} passed, {statuses.count("FAIL")} failed, '
        f'{statuses.count("SKIP")} skipped'
    )
    return '\n\n'.join(section for section in (table, '\n'.join(notes), summary) if section)
