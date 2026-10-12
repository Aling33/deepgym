"""Tests for recording and replaying episodes in the console."""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from deepgym.console import record_episode
from deepgym.console.app import create_app
from deepgym.models import Action, Observation, RunResult, Trajectory

PNG = b'\x89PNG\r\n\x1a\n fake image bytes'


def _trajectory() -> Trajectory:
    shot = base64.b64encode(PNG).decode()
    first = Observation(content='form loaded', step=0, screenshot=shot)
    second = Observation(content='name typed', step=1, screenshot=shot)
    final = Observation(content='saved', step=2, done=True, metadata={'exit_code': 0})
    return Trajectory(
        steps=[
            (first, Action(action_type='click', x=10, y=20)),
            (second, Action(action_type='done')),
        ],
        final_observation=final,
        total_reward=0.5,
        step_rewards=[0.25, 0.25],
    )


def _result() -> RunResult:
    return RunResult(
        score=1.0, passed=True, output='3/3', stderr='', exit_code=0,
        execution_time_ms=5.0, sandbox_id='sb-1',
    )  # fmt: skip


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    return tmp_path / 'console.db'


@pytest.fixture()
def client(db: Path, tmp_path: Path) -> TestClient:
    return TestClient(create_app(db, tmp_path / 'qa'))


def test_post_and_replay(client: TestClient) -> None:
    body = {
        'environment': 'signup_form',
        'trajectory': _trajectory().model_dump(mode='json'),
        'result': _result().model_dump(mode='json'),
    }

    response = client.post('/api/episodes', json=body)

    assert response.status_code == 201
    summary = response.json()
    assert (summary['steps'], summary['total_reward'], summary['passed']) == (2, 0.5, True)
    detail = client.get(f'/api/episodes/{summary["id"]}').json()
    frames = detail['frames']
    assert [f['content'] for f in frames] == ['form loaded', 'name typed', 'saved']
    assert frames[0]['action'] == {**frames[0]['action'], 'action_type': 'click', 'x': 10}
    assert [f['reward'] for f in frames] == [0.25, 0.25, None]
    assert [f['has_screenshot'] for f in frames] == [True, True, False]
    assert frames[2]['action'] is None
    assert detail['result']['output'] == '3/3'


def test_screenshots_are_served_as_png(client: TestClient) -> None:
    body = {'environment': 'signup_form', 'trajectory': _trajectory().model_dump(mode='json')}
    episode_id = client.post('/api/episodes', json=body).json()['id']

    shot = client.get(f'/api/episodes/{episode_id}/frames/1/screenshot')

    assert shot.status_code == 200
    assert shot.headers['content-type'] == 'image/png'
    assert shot.content == PNG
    assert client.get(f'/api/episodes/{episode_id}/frames/2/screenshot').status_code == 404


def test_bad_screenshot_is_rejected(client: TestClient) -> None:
    trajectory = _trajectory().model_dump(mode='json')
    trajectory['steps'][0][0]['screenshot'] = 'not base64!'

    response = client.post('/api/episodes', json={'trajectory': trajectory})

    assert response.status_code == 422
    assert client.get('/api/episodes').json() == []


def test_record_episode_helper(client: TestClient, db: Path) -> None:
    episode_id = record_episode(_trajectory(), _result(), environment='todo_list', db_path=db)

    listed = client.get('/api/episodes?environment=todo_list').json()

    assert [e['id'] for e in listed] == [episode_id]
    assert listed[0]['score'] == 1.0
    assert client.get('/api/episodes?environment=other').json() == []


def test_unknown_episode_is_404(client: TestClient) -> None:
    assert client.get('/api/episodes/nope').status_code == 404
