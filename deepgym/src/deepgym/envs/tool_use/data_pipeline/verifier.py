"""Verifier for the Data Pipeline task."""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile

from deepgym_solution import read_output, run_solution

INPUT_CSV = """name,age,city
Alice,25,New York
Bob,35,San Francisco
Charlie,40,Chicago
Diana,28,Boston
Eve,45,Seattle
Frank,22,Denver
Grace,33,Austin
Henry,50,Portland
Ivy,29,Miami
Jack,38,Dallas
"""


def verify(solution_path, test_cases_path=None):
    """Verify the solution filters CSV rows correctly."""
    # Create a temp directory with input.csv.
    work_dir = tempfile.mkdtemp(prefix='deepgym_data_pipeline_')
    input_path = os.path.join(work_dir, 'input.csv')
    output_path = os.path.join(work_dir, 'output.csv')

    with open(input_path, 'w') as f:
        f.write(INPUT_CSV.strip() + '\n')

    try:
        proc = run_solution(solution_path, cwd=work_dir, timeout=15)
    except subprocess.TimeoutExpired:
        return {
            'schema_version': '1.0',
            'score': 0.0,
            'passed': False,
            'cases': [],
            'details': 'Solution timed out after 15s',
        }

    checks = {}

    # Check script ran without error.
    checks['no_error'] = proc.returncode == 0

    # Check output.csv exists.
    try:
        output_text = read_output(output_path, work_dir)
        checks['output_exists'] = True
    except OSError:
        checks['output_exists'] = False

    if checks['output_exists']:
        rows = list(csv.DictReader(io.StringIO(output_text)))

        # Expected: Bob(35), Charlie(40), Eve(45), Grace(33), Henry(50), Jack(38)
        expected_names = {'Bob', 'Charlie', 'Eve', 'Grace', 'Henry', 'Jack'}

        actual_names = {row.get('name', '').strip() for row in rows}
        checks['correct_count'] = len(rows) == 6
        checks['correct_names'] = actual_names == expected_names

        # Check all ages are > 30.
        try:
            checks['all_ages_valid'] = all(int(row.get('age', '0').strip()) > 30 for row in rows)
        except ValueError:
            checks['all_ages_valid'] = False

        # Check headers are present.
        if rows:
            checks['has_headers'] = set(rows[0].keys()) >= {'name', 'age', 'city'}
        else:
            checks['has_headers'] = False
    else:
        checks['correct_count'] = False
        checks['correct_names'] = False
        checks['all_ages_valid'] = False
        checks['has_headers'] = False

    # Check stdout reports the count.
    checks['prints_count'] = '6' in proc.stdout.strip()

    passed_count = sum(checks.values())
    total = len(checks)
    score = passed_count / total

    details_parts = [f'{k}={v}' for k, v in checks.items()]
    if proc.stderr.strip():
        details_parts.append(f'stderr={proc.stderr.strip()[:200]}')

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
        # Threshold < 1.0: pipeline tasks use discrete output checks where minor
        # formatting differences (e.g. missing count print) should not fail an
        # otherwise correct filtering solution.
        'passed': score >= 0.8,
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
