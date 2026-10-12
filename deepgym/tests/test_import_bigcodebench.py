"""Tests for the BigCodeBench importer and its reward-forgery defences.

Issue #26: the generated verifier used to read the score from the solution
process's stdout, so a solution sharing that process could forge it (print a
fake line, register an atexit printer, or patch unittest so no case runs).
These tests pin the fix: the result travels over a private channel the
solution cannot write to, and zero discovered tests is a failure, not a pass.
"""

import sys
from pathlib import Path

import pytest

from deepgym import DeepGym
from deepgym.models import Environment

# Ensure scripts directory is importable
scripts_dir = Path(__file__).resolve().parent.parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from import_bigcodebench import _RUNNER_SOURCE, generate_verifier  # noqa: E402

# The private report channel is an inherited pipe fd, which Windows lacks.
# On Linux/macOS these run for real (with or without bwrap).
needs_fd_passing = pytest.mark.skipif(
    sys.platform == 'win32', reason='pass_fds is not supported on Windows'
)

TEST_CODE = """
import unittest

class TestSolution(unittest.TestCase):
    def test_answer(self):
        self.assertEqual(task_fn(), 42)
"""


def _env() -> Environment:
    return Environment(
        task='bigcodebench/toy',
        verifier_code=generate_verifier('toy/1', 'task_fn', TEST_CODE, []),
    )


def _score(solution: str) -> float:
    return DeepGym(mode='local').run(_env(), solution).score


class TestGeneratedVerifierShape:
    """The generated artefacts must use the private channel, not stdout."""

    def test_runner_reports_on_private_fd(self) -> None:
        assert 'DEEPGYM_REPORT_FD' in _RUNNER_SOURCE
        # The old code captured the real stdout and wrote the result there.
        assert 'real_stdout' not in _RUNNER_SOURCE

    def test_verifier_reads_a_pipe_not_stdout(self) -> None:
        code = generate_verifier('toy/1', 'task_fn', TEST_CODE, [])
        assert 'os.pipe()' in code
        assert 'pass_fds' in code
        # Must not fall back to proc.stdout for the score.
        assert 'proc.stdout.splitlines' not in code


@needs_fd_passing
class TestRewardHacksFail:
    """The classic hacks from test_isolation.py must also fail here (#26)."""

    def test_reference_scores_full(self) -> None:
        assert _score('def task_fn():\n    return 42\n') == 1.0

    def test_fake_score_line_via_real_stdout(self) -> None:
        hack = (
            'import json, sys\n'
            'def task_fn():\n'
            '    return -1\n'
            'def _forge():\n'
            '    sys.__stdout__.write(json.dumps({"score": 1.0, "passed": True}) + "\\n")\n'
            '    sys.__stdout__.flush()\n'
            'import atexit\n'
            'atexit.register(_forge)\n'
        )
        assert _score(hack) < 1.0

    def test_fake_score_line_direct_fd(self) -> None:
        hack = (
            'import json, os\n'
            'def task_fn():\n'
            '    return -1\n'
            'line = (json.dumps({"score": 1.0, "passed": True}) + "\\n").encode()\n'
            'for fd in (1, 2):\n'
            '    try:\n'
            '        os.write(fd, line)\n'
            '    except OSError:\n'
            '        pass\n'
        )
        assert _score(hack) < 1.0

    def test_patching_unittest_hides_nothing(self) -> None:
        hack = (
            'import unittest\n'
            'def task_fn():\n'
            '    return -1\n'
            'unittest.TestLoader.loadTestsFromTestCase = lambda self, tc: unittest.TestSuite()\n'
        )
        assert _score(hack) < 1.0

    def test_wrong_answer_scores_zero(self) -> None:
        assert _score('def task_fn():\n    return 0\n') == 0.0
