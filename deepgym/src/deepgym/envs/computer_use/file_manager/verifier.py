"""Runs with _checks.py prepended (load_state, report)."""

from pathlib import Path

docs = Path.home() / 'Documents'
archive = docs / 'Archive'


def has(path: Path, text: str) -> bool:
    return path.is_file() and path.read_text() == text


report(
    progress={
        'archive_created': archive.is_dir(),
        'report_moved': has(archive / 'report.pdf', 'Q3 revenue summary\n')
        and not (docs / 'report.pdf').exists(),
        'notes_renamed': has(docs / 'todo.txt', 'milk, eggs, bread\n')
        and not (docs / 'notes.txt').exists(),
    },
    guards={
        'no_files_lost': (
            has(docs / 'report.pdf', 'Q3 revenue summary\n')
            or has(archive / 'report.pdf', 'Q3 revenue summary\n')
        )
        and (
            has(docs / 'notes.txt', 'milk, eggs, bread\n')
            or has(docs / 'todo.txt', 'milk, eggs, bread\n')
        ),
        'photo_kept': has(docs / 'photo.jpg', 'not really a photo\n'),
        'nothing_else_archived': not archive.is_dir()
        or {p.name for p in archive.iterdir()} <= {'report.pdf'},
    },
)
