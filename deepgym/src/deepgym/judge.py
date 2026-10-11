"""Lay out a verifier run so the solution executes isolated from the judge.

Every run uses three directories:

* judge (private): verifier.py, deepgym_solution.py, test_cases.json, support files
* solution: solution.py (the model's output)
* runtime: the solution-side server, readable by the isolated solution

The verifier reaches the solution only through ``deepgym_solution``
(``load_solution`` / ``run_solution``), which starts it in a separate, isolated
process: a dedicated Linux user in Daytona, ``sandbox-exec`` on macOS, or
``bwrap`` on Linux. The solution can't read the judge directory, the deepgym
package, or the judge's memory, and can't write to the judge's stdout.
"""

from __future__ import annotations

import contextlib
import functools
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from deepgym.models import Environment
from deepgym.verifier_template import prepare_verifier

logger = logging.getLogger(__name__)

RUNTIME_FILE = 'deepgym_solution.py'
RUNTIME_SOURCE = Path(__file__).with_name('solution_runtime.py').read_text(encoding='utf-8')
# Extra seconds past the run's deadline for the verifier to finish and print.
DEADLINE_GRACE_S = 5

_DAYTONA_ROOT = '/opt/deepgym'
_SOLVER_USER = 'dgsolver'

# Run once per Daytona sandbox, as its default user (root, or a sudoer).
DAYTONA_SETUP = f"""
set -e
if [ "$(id -u)" = 0 ]; then SUDO=; else SUDO="sudo -n"; fi
id {_SOLVER_USER} >/dev/null 2>&1 || \\
  $SUDO useradd --system --no-create-home --shell /usr/sbin/nologin {_SOLVER_USER}
$SUDO mkdir -p {_DAYTONA_ROOT}/judge {_DAYTONA_ROOT}/runtime {_DAYTONA_ROOT}/solution
$SUDO chown -R "$(id -u):$(id -g)" {_DAYTONA_ROOT}
chmod 755 {_DAYTONA_ROOT} {_DAYTONA_ROOT}/runtime
chmod 700 {_DAYTONA_ROOT}/judge
chmod 777 {_DAYTONA_ROOT}/solution
echo "$(id -u) $(id -u {_SOLVER_USER}) $(id -g {_SOLVER_USER}) $(command -v python3)"
"""


class JudgeJob(BaseModel):
    """Everything one verifier run needs."""

    model_config = ConfigDict(frozen=True)

    verifier: str
    """Runnable verifier script (already prepared from the environment's source)."""

    solution: str
    """The model's output, written to solution.py."""

    test_cases: list[dict] | None = None
    support_files: dict[str, str] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1)
    case_timeout: int = Field(default=10, ge=1)
    env_vars: dict[str, str] | None = None

    @classmethod
    def for_environment(cls, env: Environment, model_output: str) -> JudgeJob:
        """Build the job for running *model_output* against *env*'s verifier."""
        return cls(
            verifier=prepare_verifier(env.verifier_source, env.verifier_mode),
            solution=model_output,
            test_cases=env.test_cases,
            support_files=env.support_files,
            timeout=env.timeout,
            case_timeout=env.case_timeout,
            env_vars=env.env_vars,
        )

    def judge_files(self) -> dict[str, str]:
        """Files for the private judge directory, keyed by relative path."""
        files = {**self.support_files, 'verifier.py': self.verifier, RUNTIME_FILE: RUNTIME_SOURCE}
        if self.test_cases is not None:
            files['test_cases.json'] = json.dumps(self.test_cases, ensure_ascii=False)
        return files

    def runtime_env(self, isolation: dict, runtime_path: str, python: str) -> dict[str, str]:
        """Variables telling deepgym_solution how to launch and bound the solution."""
        return {
            **(self.env_vars or {}),
            'DEEPGYM_ISOLATION': json.dumps(isolation),
            'DEEPGYM_RUNTIME': runtime_path,
            'DEEPGYM_PYTHON': python,
            'DEEPGYM_CASE_TIMEOUT': str(self.case_timeout),
        }

    def verifier_args(self, judge_dir: str, solution_path: str) -> list[str]:
        """Arguments after ``python``: verifier, solution, and test cases if any."""
        args = [f'{judge_dir}/verifier.py', solution_path]
        if self.test_cases is not None:
            args.append(f'{judge_dir}/test_cases.json')
        return args


# ---------------------------------------------------------------------------
# Local
# ---------------------------------------------------------------------------


@functools.cache
def local_isolation_kind() -> Literal['macos', 'bwrap', 'none']:
    """Pick the strongest sandbox this machine offers for local runs."""
    probes = {
        'macos': ['sandbox-exec', '-p', '(version 1)(allow default)', 'true'],
        'bwrap': ['bwrap', '--ro-bind', '/', '/', '--unshare-all', 'true'],
    }
    for kind, probe in probes.items():
        if shutil.which(probe[0]) is None:
            continue
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            if subprocess.run(probe, capture_output=True, timeout=10).returncode == 0:
                return kind  # type: ignore[return-value]
    logger.warning(
        'No sandbox-exec or bwrap available: local solutions run in a separate process but '
        'can read judge files. Use Daytona for untrusted code.'
    )
    return 'none'


def local_isolation(judge_dir: str) -> dict:
    """Isolation spec hiding the judge, the deepgym package, and cached benchmarks."""
    kind = local_isolation_kind()
    if kind == 'none':
        return {'kind': 'none'}
    hide = [judge_dir, str(Path(__file__).resolve().parent), str(Path.home() / '.deepgym')]
    return {'kind': kind, 'hide': [os.path.realpath(p) for p in hide if os.path.exists(p)]}


@contextlib.contextmanager
def local_judge(job: JudgeJob) -> Iterator[tuple[list[str], dict[str, str], str]]:
    """Materialize *job* in temp dirs; yield (argv, env, cwd) for the judge process."""
    dirs = [tempfile.mkdtemp(prefix=f'deepgym_{part}_') for part in ('judge', 'run', 'sol')]
    judge_dir, runtime_dir, solution_dir = (os.path.realpath(d) for d in dirs)
    try:
        for rel, content in job.judge_files().items():
            target = Path(judge_dir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        runtime_path = f'{runtime_dir}/{RUNTIME_FILE}'
        Path(runtime_path).write_text(RUNTIME_SOURCE, encoding='utf-8')
        solution_path = f'{solution_dir}/solution.py'
        Path(solution_path).write_text(job.solution, encoding='utf-8')
        env = {
            **os.environ,
            **job.runtime_env(local_isolation(judge_dir), runtime_path, sys.executable),
            'DEEPGYM_DEADLINE': str(time.time() + job.timeout),
        }
        yield [sys.executable, *job.verifier_args(judge_dir, solution_path)], env, judge_dir
    finally:
        for path in dirs:
            shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Daytona
# ---------------------------------------------------------------------------


def daytona_isolation(setup_output: str) -> tuple[dict, str]:
    """Turn DAYTONA_SETUP's output into (isolation spec, python path)."""
    judge_uid, uid, gid, python = setup_output.split()[-4:]
    if judge_uid == '0':
        prefix = ['setpriv', f'--reuid={uid}', f'--regid={gid}', '--clear-groups', '--']
    else:
        prefix = ['sudo', '-n', '-u', _SOLVER_USER, '--']
    kill = [*prefix, 'bash', '-c', 'kill -9 -1']
    return {'kind': 'user', 'prefix': prefix, 'kill': kill}, python


def daytona_uploads(job: JudgeJob) -> list[tuple[bytes, str]]:
    """(content, sandbox path) pairs for the judge, runtime, and solution files."""
    uploads = [
        (content.encode('utf-8'), f'{_DAYTONA_ROOT}/judge/{rel}')
        for rel, content in job.judge_files().items()
    ]
    uploads.append((RUNTIME_SOURCE.encode('utf-8'), f'{_DAYTONA_ROOT}/runtime/{RUNTIME_FILE}'))
    uploads.append((job.solution.encode('utf-8'), f'{_DAYTONA_ROOT}/solution/solution.py'))
    return uploads


def daytona_judge(job: JudgeJob, setup_output: str) -> tuple[str, dict[str, str]]:
    """Return (bash command, env) that run the verifier inside the sandbox."""
    isolation, python = daytona_isolation(setup_output)
    judge_dir = f'{_DAYTONA_ROOT}/judge'
    args = job.verifier_args(judge_dir, f'{_DAYTONA_ROOT}/solution/solution.py')
    command = (
        f'cd {judge_dir} && DEEPGYM_DEADLINE=$(( $(date +%s) + {job.timeout} )) '
        f'exec {shlex.quote(python)} {shlex.join(args)}'
    )
    env = job.runtime_env(isolation, f'{_DAYTONA_ROOT}/runtime/{RUNTIME_FILE}', python)
    return f'bash -c {shlex.quote(command)}', env
