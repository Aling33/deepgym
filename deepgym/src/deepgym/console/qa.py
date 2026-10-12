"""QA routes: reports that ``deepgym qa`` writes to ~/.deepgym/qa/*.json."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import ValidationError

from deepgym.console.deps import QADirDep
from deepgym.console.schemas import QAReport

logger = logging.getLogger(__name__)

DEFAULT_QA_DIR = Path.home() / '.deepgym' / 'qa'

router = APIRouter(prefix='/qa', tags=['qa'])


def load_reports(qa_dir: Path) -> list[QAReport]:
    """Read every report in *qa_dir*, newest first; unreadable files are logged and skipped."""
    reports: list[QAReport] = []
    for path in sorted(qa_dir.glob('*.json')):
        try:
            report = QAReport.model_validate_json(path.read_text(encoding='utf-8'))
        except (OSError, ValidationError) as exc:
            logger.warning('Skipping QA report %s: %s', path, exc)
            continue
        reports.append(report.model_copy(update={'file': path.name}))
    return sorted(reports, key=lambda report: report.created_at, reverse=True)


@router.get('', response_model=list[QAReport])
def list_reports(qa_dir: QADirDep, environment: str | None = None) -> list[QAReport]:
    """List QA reports, newest first, optionally for one environment."""
    return [r for r in load_reports(qa_dir) if environment in (None, r.environment)]
