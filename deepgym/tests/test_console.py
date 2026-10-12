"""Tests for the console API: environments, runs, sandboxes, QA reports and UI serving."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deepgym.console import app as console_app
from deepgym.console.app import create_app
from deepgym.console.run_store import RunStore
from deepgym.console.schemas import RunSpec
from deepgym.sandboxes.apple import AppleContainer
from deepgym.sandboxes.docker import DockerContainer

REVERSE_OK = 'def reverse_string(s: str) -> str:\n    return s[::-1]\n'
REVERSE_WRONG = 'def reverse_string(s: str) -> str:\n    return s\n'


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Console with a temp database and QA dir, allowed to run solutions locally."""
    app = create_app(tmp_path / 'console.db', tmp_path / 'qa', allow_local_exec=True)
    with TestClient(app) as test_client:
        yield test_client


def _wait_finished(client: TestClient, run_id: str, timeout_s: float = 60) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        run = client.get(f'/api/runs/{run_id}').json()
        if run['status'] in ('completed', 'failed'):
            return run
        time.sleep(0.2)
    raise AssertionError(f'run {run_id} did not finish in {timeout_s}s')


class TestEnvironments:
    def test_list_has_every_kind(self, client: TestClient) -> None:
        envs = client.get('/api/environments').json()
        assert len(envs) >= 31
        assert {env['kind'] for env in envs} >= {'single-turn', 'computer-use'}

    @pytest.mark.parametrize(
        ('query', 'field', 'value'),
        [('kind=computer-use', 'kind', 'computer-use'), ('difficulty=easy', 'difficulty', 'easy'),
         ('domain=browser', 'domain', 'browser')],
    )  # fmt: skip
    def test_filters(self, client: TestClient, query: str, field: str, value: str) -> None:
        envs = client.get(f'/api/environments?{query}').json()
        assert envs
        assert all(env[field] == value for env in envs)

    def test_detail_has_task_verifier_and_reference(self, client: TestClient) -> None:
        env = client.get('/api/environments/coin_change').json()
        assert env['name'] == 'Coin Change'
        assert env['kind'] == 'single-turn'
        assert 'coin' in env['task'].lower()
        assert 'def ' in env['verifier']
        assert env['reference']
        assert env['metadata']['id'] == 'env-012'

    def test_detail_of_nested_env(self, client: TestClient) -> None:
        response = client.get('/api/environments/cyber/web_path_traversal_toy')
        assert response.status_code == 200
        assert response.json()['domain'] == 'cyber'

    def test_computer_use_variant(self, client: TestClient) -> None:
        env = client.get('/api/environments/signup_form?variant=3').json()
        assert env['kind'] == 'computer-use'
        assert env['variants'] == 8
        assert env['variant'] == 3
        assert env['reference'] is None

    def test_unknown_env_is_404(self, client: TestClient) -> None:
        assert client.get('/api/environments/no_such_env_xyz').status_code == 404


class TestRuns:
    def test_reference_run_passes(self, client: TestClient) -> None:
        response = client.post('/api/runs', json={'environments': ['reverse_string']})
        assert response.status_code == 202
        (queued,) = response.json()
        assert queued['reference'] is True

        run = _wait_finished(client, queued['id'])

        assert run['status'] == 'completed'
        assert run['passed'] is True
        assert run['score'] == 1.0
        assert run['provider'] == 'local'
        assert run['duration_ms'] > 0
        assert run['solution']
        assert len(run['result']['cases']) > 1

    def test_wrong_solution_scores_partially(self, client: TestClient) -> None:
        body = {'environments': ['reverse_string'], 'solution': REVERSE_WRONG, 'mode': 'local'}
        (queued,) = client.post('/api/runs', json=body).json()

        run = _wait_finished(client, queued['id'])

        assert run['status'] == 'completed'
        assert run['passed'] is False
        assert 0 < run['score'] < 1
        assert run['reference'] is False
        assert any(not case['passed'] for case in run['result']['cases'])

    def test_small_eval_shares_a_group(self, client: TestClient) -> None:
        body = {'environments': ['reverse_string', 'fizzbuzz']}
        queued = client.post('/api/runs', json=body).json()
        assert len({run['group_id'] for run in queued}) == 1

        for run in queued:
            _wait_finished(client, run['id'])
        listed = client.get(f'/api/runs?group_id={queued[0]["group_id"]}').json()

        assert sorted(run['environment'] for run in listed) == ['fizzbuzz', 'reverse_string']
        assert client.get('/api/runs?status=completed').json()

    @pytest.mark.parametrize(
        ('body', 'code'),
        [({'environments': ['signup_form']}, 400), ({'environments': ['no_such_env']}, 404),
         ({'environments': []}, 422), ({'environments': ['fizzbuzz'], 'mode': 'nope'}, 422)],
    )  # fmt: skip
    def test_rejected_requests(self, client: TestClient, body: dict, code: int) -> None:
        assert client.post('/api/runs', json=body).status_code == code
        assert client.get('/api/runs').json() == []

    def test_local_runs_need_opt_in(self, tmp_path: Path) -> None:
        client = TestClient(create_app(tmp_path / 'c.db', tmp_path / 'qa'))
        response = client.post('/api/runs', json={'environments': ['fizzbuzz'], 'mode': 'local'})
        assert response.status_code == 400
        assert '--allow-local-exec' in response.json()['detail']

    def test_unknown_run_is_404(self, client: TestClient) -> None:
        assert client.get('/api/runs/nope').status_code == 404

    def test_restart_fails_unfinished_runs(self, tmp_path: Path) -> None:
        db = tmp_path / 'console.db'
        spec = RunSpec(environment='fizzbuzz', solution='pass', reference=False)
        (run,) = RunStore(db).create_group([spec], 'local', 'local')

        client = TestClient(create_app(db, tmp_path / 'qa'))
        detail = client.get(f'/api/runs/{run.id}').json()

        assert detail['status'] == 'failed'
        assert detail['error_type'] == 'interrupted'


class TestSandboxes:
    def test_lists_local_providers(self, client: TestClient) -> None:
        listing = client.get('/api/sandboxes').json()
        assert [p['provider'] for p in listing] == ['apple', 'docker']
        for provider in listing:
            assert provider['available'] or provider['error']

    @pytest.mark.parametrize('path', ['docker/not-ours', 'apple/deepgym-x;rm', 'modal/deepgym-ab'])
    def test_kill_rejects_foreign_names(self, client: TestClient, path: str) -> None:
        assert client.delete(f'/api/sandboxes/{path}').status_code == 422

    def test_parse_docker_listing(self) -> None:
        line = {'Names': 'deepgym-ab12', 'Image': 'python:3.12-slim', 'State': 'running',
                'CreatedAt': '2026-10-12 10:00:00 +0000 UTC'}  # fmt: skip
        (box,) = DockerContainer._parse_listing(json.dumps(line) + '\n')
        assert (box.id, box.image, box.state) == ('deepgym-ab12', 'python:3.12-slim', 'running')

    def test_parse_apple_listing(self) -> None:
        rows = [
            {'id': name, 'status': {'state': 'running', 'startedDate': '2026-10-12T10:00:00Z'},
             'configuration': {'image': {'reference': 'docker.io/library/python:3.12-slim'}}}
            for name in ('deepgym-ab12', 'someone-else')
        ]  # fmt: skip
        boxes = AppleContainer._parse_listing(json.dumps(rows))
        assert [box.id for box in boxes] == ['deepgym-ab12', 'someone-else']
        assert boxes[0].started == '2026-10-12T10:00:00Z'


class TestQA:
    def test_reports_newest_first_and_filtered(self, client: TestClient, tmp_path: Path) -> None:
        qa_dir = tmp_path / 'qa'
        qa_dir.mkdir()
        for name, env, created in [('a.json', 'fizzbuzz', '2026-10-01T00:00:00Z'),
                                   ('b.json', 'fizzbuzz', '2026-10-02T00:00:00'),
                                   ('c.json', 'two_sum', '2026-10-03T00:00:00+00:00')]:  # fmt: skip
            report = {'environment': env, 'passed': env == 'two_sum', 'created_at': created,
                      'checks': [{'name': 'reference passes', 'passed': True, 'details': 'ok'}]}  # fmt: skip
            (qa_dir / name).write_text(json.dumps(report))
        (qa_dir / 'broken.json').write_text('{not json')

        reports = client.get('/api/qa').json()
        fizzbuzz = client.get('/api/qa?environment=fizzbuzz').json()

        assert [r['file'] for r in reports] == ['c.json', 'b.json', 'a.json']
        assert reports[0]['checks'][0]['name'] == 'reference passes'
        assert [r['file'] for r in fizzbuzz] == ['b.json', 'a.json']

    def test_missing_dir_is_empty(self, client: TestClient) -> None:
        assert client.get('/api/qa').json() == []


class TestServing:
    def test_missing_ui_explains_how_to_build(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(console_app, 'STATIC_DIR', tmp_path / 'static')
        client = TestClient(create_app(tmp_path / 'c.db', tmp_path / 'qa'))
        response = client.get('/')
        assert response.status_code == 503
        assert 'bun run build' in response.text

    def test_serves_built_ui(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        static = tmp_path / 'static'
        (static / 'runs').mkdir(parents=True)
        (static / 'index.html').write_text('<html>console</html>')
        (static / 'runs' / 'index.html').write_text('<html>runs</html>')
        monkeypatch.setattr(console_app, 'STATIC_DIR', static)
        client = TestClient(create_app(tmp_path / 'c.db', tmp_path / 'qa'))

        assert client.get('/').text == '<html>console</html>'
        assert client.get('/runs/').text == '<html>runs</html>'
        assert client.get('/api/qa').json() == []

    def test_rejects_foreign_host_headers(self, tmp_path: Path) -> None:
        app = create_app(tmp_path / 'c.db', tmp_path / 'qa', allowed_hosts=['127.0.0.1'])
        assert TestClient(app, base_url='http://evil.example').get('/api/qa').status_code == 400
        assert TestClient(app, base_url='http://127.0.0.1').get('/api/qa').status_code == 200
