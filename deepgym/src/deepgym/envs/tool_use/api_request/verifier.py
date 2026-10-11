"""Verifier for the API Request task.

Verify that the solution script contains correct logic for fetching JSON from
an HTTP endpoint and extracting a nested field, without requiring live internet.
The verifier checks code structure and runs the script with a mocked HTTP
response.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from deepgym_solution import run_solution


def verify(solution_path, test_cases_path=None):
    """Verify the solution fetches JSON and extracts the slideshow title."""
    source = Path(solution_path).read_text(encoding='utf-8')

    checks = {}

    # Check that the solution uses an HTTP library.
    checks['uses_http'] = (
        'urllib.request' in source
        or 'requests' in source
        or 'httpx' in source
        or 'urlopen' in source
        or 'http.client' in source
    )

    # Check that the solution parses JSON.
    checks['parses_json'] = 'json' in source or '.json()' in source

    # Check that the solution extracts the slideshow title field.
    checks['extracts_title'] = 'slideshow' in source and 'title' in source

    # Run the solution with a mocked HTTP response to verify end-to-end.
    # We create a wrapper that patches urllib/requests to return the expected JSON.
    expected_json = json.dumps(
        {
            'slideshow': {
                'author': 'Yours Truly',
                'date': 'date of publication',
                'slides': [
                    {'title': 'Wake up to WonderWidgets!', 'type': 'all'},
                    {
                        'title': 'Overview',
                        'type': 'all',
                        'items': [
                            'Why <em>WonderWidgets</em> are great',
                            'Who <em>buys</em> WonderWidgets',
                        ],
                    },
                ],
                'title': 'Sample Slide Show',
            }
        }
    )

    wrapper = textwrap.dedent(f"""\
        import sys
        import types
        import json

        # Mock urllib.request.urlopen
        _mock_data = {expected_json!r}.encode("utf-8")

        class _MockResponse:
            def read(self):
                return _mock_data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        _has = hasattr(__builtins__, "__import__")
        _orig_import = __builtins__.__import__ if _has else __import__

        import urllib.request
        urllib.request._original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **kw: _MockResponse()

        # Also mock requests.get if requests is used
        _fake_requests = types.ModuleType("requests")
        class _FakeResp:
            status_code = 200
            text = {expected_json!r}
            def json(self):
                return json.loads(self.text)
        _fake_requests.get = lambda *a, **kw: _FakeResp()
        sys.modules["requests"] = _fake_requests

        # Now exec the solution
        exec(open({solution_path!r}).read())
    """)

    work_dir = tempfile.mkdtemp(prefix='deepgym_api_request_')
    wrapper_path = Path(work_dir, 'run_with_mocks.py')
    wrapper_path.write_text(wrapper, encoding='utf-8')
    try:
        proc = run_solution(str(wrapper_path), cwd=work_dir, timeout=15)
        checks['correct_output'] = 'Sample Slide Show' in proc.stdout
    except subprocess.TimeoutExpired:
        checks['correct_output'] = False
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    passed_count = sum(checks.values())
    total = len(checks)
    score = passed_count / total

    details_parts = [f'{k}={v}' for k, v in checks.items()]

    cases = []
    for idx, (check_name, check_passed) in enumerate(checks.items()):
        cases.append(
            {
                'id': f'check_{idx}',
                'input_summary': check_name,
                'passed': bool(check_passed),
                'schema_version': '1.0',
                'score': 1.0 if check_passed else 0.0,
                'cases': [],
                'expected_summary': 'True',
                'actual_summary': str(check_passed),
            }
        )

    return {
        'schema_version': '1.0',
        'score': score,
        # Threshold < 1.0: API tasks check structural code patterns (uses_http,
        # parses_json, extracts_title) that may not all match for solutions using
        # alternative but valid libraries.
        'passed': score >= 0.75,
        'details': f'{passed_count}/{total} checks passed. ' + ', '.join(details_parts),
        'cases': cases,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    'schema_version': '1.0',
                    'score': 0.0,
                    'passed': False,
                    'cases': [],
                    'details': 'Usage: verifier.py <solution_path>',
                }
            )
        )
        sys.exit(1)

    try:
        result = verify(sys.argv[1])
    except Exception as e:
        result = {
            'schema_version': '1.0',
            'score': 0.0,
            'passed': False,
            'cases': [],
            'details': f'Verifier error: {type(e).__name__}: {e}',
        }

    print(json.dumps(result))
