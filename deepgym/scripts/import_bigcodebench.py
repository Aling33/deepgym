#!/usr/bin/env python3
"""Import BigCodeBench benchmark into DeepGym environment format.

Downloads the 1,140 BigCodeBench problems from HuggingFace and generates
a DeepGym-compatible environment directory for each one, including:
  - task.md (the prompt)
  - reference_solution.py (prompt + canonical solution)
  - verifier.py (wraps the BigCodeBench unittest test code)
  - metadata.json

Also generates environments/bigcodebench/registry.json indexing all problems.
"""

import ast
import json
from pathlib import Path

# `datasets` is only needed to download the benchmark, not to build the
# verifier, so it is imported lazily in main(). That keeps this module (and the
# verifier generators it exposes) importable for tests without the HF stack.


# Runs inside the isolated solution process: loads the solution, runs the
# BigCodeBench unittest code against it, and reports one JSON result line on a
# private file descriptor the judge handed us (never on stdout, which the
# solution shares and can forge).
_RUNNER_SOURCE = """
import importlib.util
import json
import os
import sys
import unittest


def main():
    with open(sys.argv[1]) as handle:
        spec_data = json.load(handle)
    # The judge passes the write end of a pipe as this fd. It is a number, not a
    # path, so the solution cannot reopen it or learn it by scanning the cwd.
    report_fd = int(os.environ["DEEPGYM_REPORT_FD"])
    report = os.fdopen(report_fd, "w")

    def emit(score, passed, details):
        report.write(json.dumps({"score": score, "passed": passed, "details": details}) + "\\n")
        report.flush()
        report.close()

    # Silence both the real stdout and the rebound one: the solution must have no
    # reachable stream the judge reads. We report only through *report*.
    try:
        sys.stdout = sys.stderr = open(os.devnull, "w")
        sys.__stdout__ = sys.__stderr__ = sys.stdout
    except Exception:
        pass

    try:
        spec = importlib.util.spec_from_file_location("solution", sys.argv[2])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return emit(0.0, False, f"Import error: {type(e).__name__}: {e}")
    if not hasattr(mod, spec_data["entry_point"]):
        return emit(0.0, False, f"Missing function: {spec_data['entry_point']}")
    ns = dict(vars(mod))
    try:
        exec(spec_data["test_code"], ns)
        loader, suite = unittest.TestLoader(), unittest.TestSuite()
        for obj in list(ns.values()):
            if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
                suite.addTests(loader.loadTestsFromTestCase(obj))
        if suite.countTestCases() == 0:
            # A real BigCodeBench task always has assertions. Zero discovered
            # cases means the solution hid them, not that it passed.
            return emit(0.0, False, "No tests discovered")
        result = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
        failed = len(result.failures) + len(result.errors)
        score = (result.testsRun - failed) / result.testsRun if result.testsRun else 0.0
        emit(score, score >= 0.8, f"{result.testsRun - failed}/{result.testsRun} tests passed")
    except AssertionError as e:
        emit(0.0, False, f"Assertion failed: {e}")
    except Exception as e:
        emit(0.0, False, f"Error: {type(e).__name__}: {e}")


main()
"""


def generate_verifier(task_id: str, entry_point: str, test_code: str, libs: list) -> str:
    """Generate a DeepGym-compatible verifier from BigCodeBench test code.

    BigCodeBench tests inspect rich objects (DataFrames, plots), so the tests
    and the solution must share a process. The verifier hands that process the
    write end of a pipe and reads the one JSON result line back from it; the
    score never comes from the solution's stdout, which it could forge.
    """
    return f'''#!/usr/bin/env python3
"""DeepGym verifier for BigCodeBench {task_id}.

The solution and the tests share one isolated process, but the result travels
over a private pipe fd the solution cannot reach, so it can't be forged by
printing a fake score line or patching unittest.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from deepgym_solution import run_solution

_TEST_CODE = {test_code!r}
_ENTRY_POINT = {entry_point!r}
_RUNNER = {_RUNNER_SOURCE!r}


def verify(solution_path):
    """Run the BigCodeBench tests with the solution, reading the result over a pipe."""
    work = tempfile.mkdtemp(prefix="deepgym_bcb_")
    read_fd = write_fd = None
    try:
        Path(work, "runner.py").write_text(_RUNNER, encoding="utf-8")
        spec = {{"test_code": _TEST_CODE, "entry_point": _ENTRY_POINT}}
        Path(work, "tests.json").write_text(json.dumps(spec), encoding="utf-8")
        read_fd, write_fd = os.pipe()
        os.set_inheritable(write_fd, True)
        try:
            proc = run_solution(
                str(Path(work, "runner.py")),
                [str(Path(work, "tests.json")), solution_path],
                cwd=work,
                timeout=120,
                allow_subprocess=True,
                env={{"DEEPGYM_REPORT_FD": str(write_fd)}},
                pass_fds=(write_fd,),
            )
        except subprocess.TimeoutExpired:
            return {{"score": 0.0, "passed": False, "details": "Tests timed out"}}
        finally:
            # Close our copy of the writer so the read below sees EOF.
            if write_fd is not None:
                os.close(write_fd)
                write_fd = None
        with os.fdopen(read_fd, "r") as channel:
            read_fd = None
            lines = [line for line in channel.read().splitlines() if line.startswith("{{")]
        if not lines:
            return {{"score": 0.0, "passed": False, "details": "No report on the private channel"}}
        # Take the FIRST line: a trailing line could only come from a writer we
        # did not expect, so it must not be trusted either.
        return json.loads(lines[0])
    finally:
        for fd in (read_fd, write_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({{"score": 0.0, "passed": False, "details": "Usage: verifier.py <solution_path>"}}))
        sys.exit(1)
    try:
        result = verify(sys.argv[1])
    except Exception as e:
        result = {{"score": 0.0, "passed": False, "details": f"Verifier error: {{type(e).__name__}}: {{e}}"}}
    print(json.dumps(result))
'''


def main():
    from datasets import load_dataset

    output_dir = Path.home() / ".deepgym" / "environments" / "bigcodebench"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading BigCodeBench dataset from HuggingFace...")
    ds = load_dataset("bigcode/bigcodebench", split="v0.1.4")
    print(f"Loaded {len(ds)} problems.")

    registry = []
    skipped = []

    for row in ds:
        task_id = row["task_id"].replace("/", "_")
        entry_point = row["entry_point"]
        complete_prompt = row["complete_prompt"]
        canonical_solution = row["canonical_solution"]
        test_code = row["test"]
        libs_raw = row.get("libs", "[]")
        # libs field is a string repr of a list, e.g. "['random', 'itertools']"
        if isinstance(libs_raw, str):
            try:
                libs = ast.literal_eval(libs_raw)
            except (ValueError, SyntaxError):
                libs = []
        else:
            libs = libs_raw if libs_raw else []

        env_dir = output_dir / task_id
        env_dir.mkdir(exist_ok=True)

        try:
            # task.md -- the problem prompt
            (env_dir / "task.md").write_text(complete_prompt, encoding="utf-8")

            # reference_solution.py -- prompt + canonical solution (complete runnable file)
            (env_dir / "reference_solution.py").write_text(
                complete_prompt + canonical_solution, encoding="utf-8"
            )

            # verifier.py
            verifier_src = generate_verifier(task_id, entry_point, test_code, libs)
            (env_dir / "verifier.py").write_text(verifier_src, encoding="utf-8")

            # metadata.json
            metadata = {
                "id": task_id,
                "name": entry_point,
                "difficulty": "hard",
                "domain": "coding",
                "benchmark": "bigcodebench",
                "libs": libs,
                "tags": ["bigcodebench", "function-completion"] + libs[:3],
            }
            (env_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
            )

            registry.append({**metadata, "path": f"environments/bigcodebench/{task_id}"})
        except Exception as e:
            skipped.append({"id": task_id, "reason": str(e)})
            print(f"  SKIP {task_id}: {e}")

    # registry.json
    (output_dir / "registry.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nGenerated {len(registry)} BigCodeBench environments in {output_dir}")
    if skipped:
        print(f"Skipped {len(skipped)} problems:")
        for s in skipped:
            print(f"  {s['id']}: {s['reason']}")


if __name__ == "__main__":
    main()
