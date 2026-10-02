"""Server-owned role configuration and model construction boundary."""

from .factory import current_snapshot, get_role_model, initialize, shutdown, use_snapshot

__all__ = ["current_snapshot", "get_role_model", "initialize", "shutdown", "use_snapshot"]
