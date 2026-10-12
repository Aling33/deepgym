"""The console app: a JSON API under /api plus the built UI from ./static."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from fastapi import APIRouter, FastAPI
    from fastapi.responses import PlainTextResponse
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.trustedhost import TrustedHostMiddleware
except ImportError as _exc:
    raise ImportError(
        'FastAPI is required for the console. Install with: pip install "deepgym[server]"'
    ) from _exc

from deepgym.console import environments, episodes, qa, runs, sandboxes
from deepgym.console.db import DEFAULT_DB_PATH
from deepgym.console.episode_store import EpisodeStore
from deepgym.console.qa import DEFAULT_QA_DIR
from deepgym.console.run_store import RunStore
from deepgym.console.runner import Runner

STATIC_DIR = Path(__file__).parent / 'static'
MISSING_UI_MESSAGE = (
    'The console UI is not built, so only the API under /api is served.\n'
    'Build it from a clone of the repo (needs bun):\n'
    '  cd deepgym/console-ui && bun install && bun run build\n'
    'Wheels from PyPI ship it prebuilt.'
)


def ui_built() -> bool:
    """Return True if the UI's static export is in place."""
    return (STATIC_DIR / 'index.html').is_file()


def create_app(
    db_path: Path = DEFAULT_DB_PATH,
    qa_dir: Path = DEFAULT_QA_DIR,
    *,
    allow_local_exec: bool = False,
    allowed_hosts: Sequence[str] | None = None,
) -> FastAPI:
    """Create the console application.

    Args:
        db_path: SQLite file for runs and episodes.
        qa_dir: Directory of QA report JSON files.
        allow_local_exec: Allow runs that execute solutions on this machine
            (mode 'local', or 'auto' without Daytona).
        allowed_hosts: Host headers to accept; None accepts any. Pass the loopback
            names when bound to loopback so other sites can't reach it by DNS rebinding.

    Returns:
        The FastAPI app. Runs left unfinished by a previous process are marked failed.
    """
    run_store = RunStore(db_path)
    run_store.fail_unfinished()
    runner = Runner(run_store, allow_local_exec=allow_local_exec)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        runner.shutdown()

    app = FastAPI(title='DeepGym Console', lifespan=lifespan)
    app.state.runs = run_store
    app.state.episodes = EpisodeStore(db_path)
    app.state.runner = runner
    app.state.qa_dir = qa_dir
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    api = APIRouter(prefix='/api')
    for module in (environments, runs, episodes, sandboxes, qa):
        api.include_router(module.router)
    app.include_router(api)

    if ui_built():
        app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='ui')
    else:
        app.add_api_route('/', _missing_ui, include_in_schema=False)
    return app


def _missing_ui() -> PlainTextResponse:
    return PlainTextResponse(MISSING_UI_MESSAGE, status_code=503)
