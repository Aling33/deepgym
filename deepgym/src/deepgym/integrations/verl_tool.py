"""verl multi-turn tool backed by a live DeepGym session.

Each rollout gets its own sandbox: create() opens a session, every tool call is
one Action, calc_reward() runs the final verifier, release() deletes the sandbox.
Desktop environments return screenshots as images.

Tool config (``actor_rollout_ref.rollout.multi_turn.tool_config_path``)::

    tools:
      - class_name: deepgym.integrations.verl_tool.DeepGymSessionTool
        config:
          type: native
          environment: signup_form   # default; override per sample below
          mode: daytona             # default; 'local' runs model commands on this host

Per-sample environment, in the dataset row::

    extra_info:
      tools_kwargs:
        computer:
          create_kwargs: {environment: todo_list, variant: 3}

Sources:
    - https://github.com/verl-project/verl/blob/main/docs/sglang_multiturn/multiturn.rst
"""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from verl.tools.base_tool import BaseTool, OpenAIFunctionToolSchema, ToolResponse

from deepgym.core import DeepGym
from deepgym.exceptions import DeepGymError, SandboxError, VerifierError
from deepgym.models import Action, ActionType, Observation
from deepgym.registry import load_environment
from deepgym.session import Session

_COORD = {'type': 'integer', 'description': 'Screenshot pixel coordinate.'}

TOOL_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'computer',
        'description': (
            'Act in the environment. GUI actions use screenshot pixel coordinates. '
            'Call with action_type "done" when the task is complete.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'action_type': {
                    'type': 'string',
                    'enum': sorted(ActionType.__args__),  # type: ignore[attr-defined]
                    'description': 'What to do.',
                },
                'content': {
                    'type': 'string',
                    'description': 'Code, shell command, file contents, text to type, key '
                    'chord like "ctrl+s", or scroll direction up/down/left/right.',
                },
                'x': _COORD,
                'y': _COORD,
                'to_x': _COORD,
                'to_y': _COORD,
                'path': {'type': 'string', 'description': 'Relative path for write_file.'},
                'amount': {'type': 'integer', 'description': 'Scroll clicks or wait seconds.'},
            },
            'required': ['action_type'],
        },
    },
}


class DeepGymSessionTool(BaseTool):
    """Expose a DeepGym environment to verl as one stateful tool."""

    def __init__(self, config: dict, tool_schema: OpenAIFunctionToolSchema | None) -> None:
        super().__init__(config, tool_schema or OpenAIFunctionToolSchema(**TOOL_SCHEMA))
        self._dg = DeepGym(mode=config.get('mode', 'daytona'))
        self._sessions: dict[str, Session] = {}

    async def create(
        self, instance_id: str | None = None, **kwargs: Any
    ) -> tuple[str, ToolResponse]:
        """Open a sandbox for one rollout and return the first observation."""
        instance_id = instance_id or str(uuid4())
        create_kwargs = kwargs.get('create_kwargs', {})
        env = load_environment(
            create_kwargs.get('environment', self.config['environment']),
            variant=create_kwargs.get('variant', 0),
        )
        session = await asyncio.to_thread(self._dg.session, env)
        try:
            obs = await asyncio.to_thread(session.start)
        except BaseException:
            session.close()
            raise
        self._sessions[instance_id] = session
        return instance_id, _to_response(obs)

    async def execute(
        self, instance_id: str, parameters: dict[str, Any], **kwargs: Any
    ) -> tuple[ToolResponse, float, dict]:
        """Apply one action. Bad calls come back as text so the model can correct itself."""
        session = self._sessions[instance_id]
        if session.done:
            return ToolResponse(text='The episode is over.'), 0.0, {}
        try:
            action = Action.model_validate(parameters)
            obs, reward, done = await asyncio.to_thread(session.step, action)
        except ValidationError as exc:
            return ToolResponse(text=f'Invalid action: {exc.errors()[0]["msg"]}'), 0.0, {}
        except (SandboxError, VerifierError):
            raise
        except DeepGymError as exc:
            return ToolResponse(text=str(exc)), 0.0, {}
        return _to_response(obs), reward, {'done': done}

    async def calc_reward(self, instance_id: str, **kwargs: Any) -> float:
        """Run the final verifier and return its score."""
        result = await asyncio.to_thread(self._sessions[instance_id].score)
        return result.score

    async def release(self, instance_id: str, **kwargs: Any) -> None:
        """Delete the rollout's sandbox."""
        session = self._sessions.pop(instance_id, None)
        if session is not None:
            await asyncio.to_thread(session.close)


def _to_response(obs: Observation) -> ToolResponse:
    """Convert an observation to a verl ToolResponse, decoding any screenshot."""
    if obs.screenshot is None:
        return ToolResponse(text=obs.content or '(no output)')
    from PIL import Image
    from verl.utils.dataset.vision_utils import process_image

    image = Image.open(io.BytesIO(base64.b64decode(obs.screenshot)))
    return ToolResponse(text=obs.content or None, image=[process_image(image)])
