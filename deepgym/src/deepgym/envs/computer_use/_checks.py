"""Shared helpers for computer-use verifiers."""

import json
from pathlib import Path


def load_state(path: str = 'state.json') -> dict:
    """Return the app state the page last saved, or {} if it never saved."""
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def report(progress: dict[str, bool], guards: dict[str, bool]) -> None:
    """Print verifier protocol JSON.

    Score is the fraction of progress checks passed, but only if every guard
    holds (work was saved, nothing else was broken). Otherwise it is 0, so
    neither doing nothing nor saving untouched state earns reward.
    """
    guards_ok = all(guards.values())
    done = sum(progress.values())
    score = done / len(progress) if guards_ok else 0.0
    failed = [name for name, ok in guards.items() if not ok]
    print(
        json.dumps(
            {
                'schema_version': '1.0',
                'score': score,
                'passed': guards_ok and done == len(progress),
                'details': f'{done}/{len(progress)} changes made'
                + (f'; guards failed: {", ".join(failed)}' if failed else ''),
                'cases': [
                    {'id': name, 'passed': ok, 'score': float(ok)}
                    for name, ok in {**guards, **progress}.items()
                ],
            }
        )
    )
