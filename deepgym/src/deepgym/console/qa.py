"""QA routes: the per-environment reports ``deepgym qa`` writes (see deepgym.qa.report)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import ValidationError

from deepgym.console.deps import QADirDep
from deepgym.qa.report import QAReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/qa', tags=['qa'])


def load_reports(qa_dir: Path) -> list[QAReport]:
    """Read every report in *qa_dir*, newest first; unreadable files are logged and skipped."""
    reports: list[QAReport] = []
    for path in sorted(qa_dir.glob('*.json')):
        try:
            reports.append(QAReport.model_validate_json(path.read_text(encoding='utf-8')))
        except (OSError, ValidationError) as exc:
            logger.warning('Skipping QA report %s: %s', path, exc)
    # timestamp() also orders hand-written reports whose time has no zone.
    return sorted(reports, key=lambda report: report.created_at.timestamp(), reverse=True)


@router.get('', response_model=list[QAReport])
def list_reports(qa_dir: QADirDep, environment: str | None = None) -> list[QAReport]:
    """List QA reports, newest first, optionally for one environment."""
    return [r for r in load_reports(qa_dir) if environment in (None, r.environment)]
