"""DeepGymSessionTool against a stand-in for verl's tool API (verl is not installed here)."""

import asyncio
import importlib
import sys
import types

import pytest

from deepgym.models import MultiTurnEnvironment

ENV = MultiTurnEnvironment(
    task='Write hello to out.txt',
    allowed_actions={'bash', 'done'},
    final_verifier_code=(
        'import json, pathlib\n'
        'ok = pathlib.Path("out.txt").read_text().strip() == "hello"\n'
        'print(json.dumps({"score": float(ok), "passed": ok}))\n'
    ),
)


class _ToolResponse:
    def __init__(self, text: str | None = None, image: list | None = None) -> None:
        self.text = text
        self.image = image


class _Schema:
    def __init__(self, **kwargs: object) -> None:
        self.data = kwargs


class _BaseTool:
    def __init__(self, config: dict, tool_schema: _Schema) -> None:
        self.config = config
        self.tool_schema = tool_schema


@pytest.fixture()
def tool_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    base_tool = types.ModuleType('verl.tools.base_tool')
    base_tool.BaseTool = _BaseTool
    base_tool.OpenAIFunctionToolSchema = _Schema
    base_tool.ToolResponse = _ToolResponse
    for name in ('verl', 'verl.tools'):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, 'verl.tools.base_tool', base_tool)
    monkeypatch.delitem(sys.modules, 'deepgym.integrations.verl_tool', raising=False)
    module = importlib.import_module('deepgym.integrations.verl_tool')
    monkeypatch.setattr(module, 'load_environment', lambda name, variant=0: ENV)
    return module


def test_rollout_lifecycle(tool_module: types.ModuleType) -> None:
    async def rollout() -> tuple[list[str], float]:
        tool = tool_module.DeepGymSessionTool({'environment': 'x', 'mode': 'local'}, None)
        instance_id, first = await tool.create(create_kwargs={'environment': 'x'})
        texts = [first.text]
        for params in (
            {'action_type': 'click'},
            {'action_type': 'code', 'content': 'print(1)'},
            {'action_type': 'bash', 'content': 'echo hello > out.txt && echo wrote'},
        ):
            response, reward, _ = await tool.execute(instance_id, params)
            texts.append(response.text)
        score = await tool.calc_reward(instance_id)
        await tool.release(instance_id)
        assert not tool._sessions
        return texts, score

    texts, score = asyncio.run(rollout())

    assert texts[0] == '(no output)'
    assert texts[1].startswith('Invalid action')
    assert 'not allowed' in texts[2]
    assert texts[3].strip() == 'wrote'
    assert score == 1.0


def test_default_schema_lists_every_action(tool_module: types.ModuleType) -> None:
    tool = tool_module.DeepGymSessionTool({'environment': 'x', 'mode': 'local'}, None)
    enum = tool.tool_schema.data['function']['parameters']['properties']['action_type']['enum']
    assert {'click', 'type', 'key', 'bash', 'done'} <= set(enum)
