"""Detection and invocation helpers for the optional Repowise engine.

Repowise powers ``/heal``, ``/report``, ``/guard`` and the Repowise-backed
tools. It is an *optional* dependency: TermiCode must stay fully usable without
it, so availability is probed once per process and cached. Every caller that
needs to know whether those features are live should ask :func:`is_available`
rather than shelling out on its own.
"""

import subprocess
from typing import Optional


INSTALL_HINT = "pip install repowise"
FEATURES = "/heal, /report, /guard, and the Repowise-backed tools"

_available: Optional[bool] = None


def reset_cache() -> None:
    """Forget the cached probe result so the next call re-detects Repowise.

    Used by ``/doctor`` so a user who installs Repowise mid-session gets a
    truthful answer without restarting the CLI.
    """
    global _available
    _available = None


def is_available() -> bool:
    """Return True when a working ``repowise`` executable is on PATH.

    A non-zero exit counts as unavailable: a broken install is no more usable
    than a missing one. The result is cached because this sits on the startup
    path and is re-queried by every Repowise-gated command.
    """
    global _available
    if _available is not None:
        return _available

    try:
        result = subprocess.run(
            ["repowise", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        _available = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        _available = False

    return _available


def ensure_indexed(timeout: int = 120) -> None:
    """Build or refresh the local Repowise index.

    A non-zero exit is deliberately ignored: a stale index is not a reason to
    interrupt startup. The timeout is the one guard, so an unresponsive index
    build cannot hang the CLI before the user reaches a prompt.
    """
    subprocess.run(
        ["repowise", "init", "--index-only", "-y"],
        capture_output=True,
        timeout=timeout,
    )
