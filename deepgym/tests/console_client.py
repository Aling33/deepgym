"""Shared setup for the console tests: an app on temp paths and a client that sends its token."""

from pathlib import Path

from fastapi.testclient import TestClient

from deepgym.console.app import create_app
from deepgym.console.security import TOKEN_HEADER

TOKEN = 'test-token'


def make_client(tmp_path: Path, **kwargs: object) -> TestClient:
    """Console on a temp database and QA dir; requests carry the launch token."""
    app = create_app(tmp_path / 'console.db', tmp_path / 'qa', token=TOKEN, **kwargs)
    return TestClient(app, headers={TOKEN_HEADER: TOKEN})
