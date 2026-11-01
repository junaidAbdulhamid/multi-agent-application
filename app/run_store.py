"""Completed run results kept in this server process for review."""

from __future__ import annotations

from copy import deepcopy
from threading import Lock
from uuid import uuid4

_runs: dict[str, dict] = {}
_lock = Lock()


def save_run(result: dict) -> dict:
    """Give a completed result an ID and store an independent copy."""
    run_id = str(uuid4())
    saved = deepcopy({"run_id": run_id, **result})
    with _lock:
        _runs[run_id] = saved
    return deepcopy(saved)


def get_run(run_id: str) -> dict | None:
    """Return a copy so callers cannot change the stored result."""
    with _lock:
        result = _runs.get(run_id)
        return deepcopy(result) if result is not None else None
