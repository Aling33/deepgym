"""Execute console runs on a background thread pool and persist each outcome."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from deepgym.console.run_store import RunStore
from deepgym.console.schemas import RunMode, RunSpec, RunSummary
from deepgym.core import DeepGym
from deepgym.exceptions import DeepGymError, error_type_for
from deepgym.models import Environment

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4
LOCAL_CUSTOM_CODE_DISABLED = (
    'Local runs of custom code are disabled. Pick a sandbox provider (docker, apple, daytona, '
    'modal or e2b), or restart the console with --allow-local-exec.'
)


class Runner:
    """Run solutions in the background with one cached DeepGym client per mode."""

    def __init__(self, runs: RunStore, *, allow_local_exec: bool) -> None:
        self._runs = runs
        self._allow_local_exec = allow_local_exec
        self._pool = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix='console')
        self._clients: dict[RunMode, DeepGym] = {}
        self._lock = threading.Lock()

    @property
    def allow_local_exec(self) -> bool:
        """Whether custom solutions may run on this machine."""
        return self._allow_local_exec

    def client(self, mode: RunMode) -> DeepGym:
        """Return the client for *mode*, creating it on first use.

        Raises:
            DeepGymError: If the provider can't be used on this machine.
        """
        with self._lock:
            if mode not in self._clients:
                self._clients[mode] = DeepGym(mode=mode)
            return self._clients[mode]

    def check_allowed(self, dg: DeepGym, custom_code: bool) -> None:
        """Refuse custom code on this machine unless the console allows local execution.

        Reference solutions ship with DeepGym, so they may always run locally.

        Raises:
            DeepGymError: If custom code would run locally without ``--allow-local-exec``.
        """
        if custom_code and dg.backend == 'local' and not self._allow_local_exec:
            raise DeepGymError(LOCAL_CUSTOM_CODE_DISABLED)

    def submit(
        self, dg: DeepGym, mode: RunMode, jobs: Sequence[tuple[RunSpec, Environment]]
    ) -> list[RunSummary]:
        """Queue one run per job under a shared group id and start them in the background.

        Args:
            dg: Client from :meth:`client` for *mode*.
            mode: The provider mode the caller asked for.
            jobs: Each run's spec and its loaded environment.

        Returns:
            The queued runs.
        """
        runs = self._runs.create_group([spec for spec, _ in jobs], mode, dg.backend)
        for run, (spec, env) in zip(runs, jobs):
            self._pool.submit(self._execute, run.id, dg, env, spec.solution)
        return runs

    def shutdown(self) -> None:
        """Stop the pool; runs still queued are failed as interrupted on the next start."""
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _execute(self, run_id: str, dg: DeepGym, env: Environment, solution: str) -> None:
        self._runs.start(run_id)
        start = time.perf_counter()
        try:
            result = dg.run(env, solution)
        except Exception as exc:  # Recorded on the run; the pool would otherwise drop it.
            logger.warning('Console run %s failed: %s', run_id, exc)
            self._runs.fail(run_id, error_type_for(exc), str(exc), _elapsed_ms(start))
            return
        self._runs.complete(run_id, result, _elapsed_ms(start))


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
