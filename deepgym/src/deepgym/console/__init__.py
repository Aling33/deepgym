"""Management console: browse environments, start runs, replay episodes, watch sandboxes.

``deepgym console`` serves the API (``deepgym.console.app``) and the built UI.
``record_episode`` needs no server, so training loops can store episodes for replay.
"""

from deepgym.console.episode_store import record_episode

__all__ = ['record_episode']
