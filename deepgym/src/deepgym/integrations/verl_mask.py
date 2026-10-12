"""verl single-turn agent loop that keeps unscored samples out of the policy loss.

When a sandbox or verifier fails, :func:`deepgym.integrations.verl.compute_score`
returns 0.0 with ``error: 1.0``, and verl trains on that 0.0. A reward function or
reward manager can't drop the sample: ``run_single`` returns only ``reward_score`` and
``reward_extra_info`` (verl/experimental/reward_loop/reward_manager/naive.py:99), and
only those two reach the trajectory (verl/experimental/agent_loop/agent_loop.py:1044).

The agent loop owns the trajectory's ``response_mask``, so this loop scores the
response itself and zeroes the mask when ``error`` is 1.0:

- verl skips its own reward step because ``reward_score`` is set (agent_loop.py:989);
- the mask is also the ``loss_mask`` (verl/trainer/ppo/v1/agent_loop_tq.py:202), so
  the sample adds nothing to the policy, entropy or KL loss (verl/workers/utils/losses.py:98)
  and is left out of their normalizers (verl/workers/engine/fsdp/transformer_impl.py:734,
  verl/trainer/ppo/core_algos.py:1183);
- its GRPO advantage is zero (core_algos.py:329). verl's rejection sampling drops
  samples the same way (verl/trainer/ppo/rollout_corr_helper.py:231).

Its 0.0 still counts toward its group's GRPO mean and std (core_algos.py:313-321),
and a policy that learns to trigger failures escapes their penalty, so keep watching
the ``error`` metric. Line numbers are from verl main at 2035f58.

Agent loop config (``actor_rollout_ref.rollout.agent.agent_loop_config_path``)::

    - name: deepgym_single_turn
      _target_: deepgym.integrations.verl_mask.DeepGymSingleTurnAgentLoop
      mode: daytona   # DeepGym backend, as in compute_score's reward_kwargs

then set ``actor_rollout_ref.rollout.agent.default_agent_loop=deepgym_single_turn``.
Dataset rows are the ones :func:`~deepgym.integrations.verl.verl_rows` builds.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from verl.experimental.agent_loop.agent_loop import AgentLoopOutput, register
from verl.experimental.agent_loop.single_turn_agent_loop import SingleTurnAgentLoop

from deepgym.integrations.verl import compute_score
from deepgym.sandboxes import Provider


@register('deepgym_single_turn')
class DeepGymSingleTurnAgentLoop(SingleTurnAgentLoop):
    """Single-turn loop scored by DeepGym; samples that got no verdict are masked out."""

    def __init__(
        self,
        *args: Any,
        mode: Literal['auto', 'daytona', 'local'] | Provider = 'auto',
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.mode = mode

    async def run(self, sampling_params: dict[str, Any], **kwargs: Any) -> AgentLoopOutput:
        """Generate one response, score it, and zero its mask if scoring failed."""
        output = await super().run(sampling_params, **kwargs)
        result = await asyncio.to_thread(self._score, output.response_ids, kwargs)
        output.reward_score = result['score']
        output.extra_fields['reward_extra_info'] = result
        if result['error'] == 1.0:
            output.response_mask = [0] * len(output.response_mask)
        return output

    def _score(self, response_ids: list[int], row: dict[str, Any]) -> dict[str, float]:
        """Decode the response and score it with the environment its dataset row names."""
        response = self.tokenizer.decode(response_ids, skip_special_tokens=True)
        return compute_score(
            row['data_source'], response, extra_info=row.get('extra_info'), mode=self.mode
        )
