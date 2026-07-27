import subprocess

from termicode import repowise


def get_overview() -> str:
    """Fetches the architectural overview."""
    return "System Notice: Semantic 'query' is disabled in local-only mode. Use 'list_directory' to view the architecture, and 'get_health' to view the codebase health metrics."


def get_context(targets: str) -> str:
    """Fetches graph-aware context."""
    return f"System Notice: Semantic 'query' is disabled. Use 'read_file' to inspect {targets}, and 'get_health' to check its defect risk."


def get_health(targets: str = "") -> str:
    """Fetches code health metrics. Works 100% locally."""
    if not repowise.is_available():
        return (
            "Code health metrics are unavailable because Repowise is not installed. "
            f"Install it with `{repowise.INSTALL_HINT}` to enable this tool."
        )

    try:
        cmd = ["repowise", "health"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return result.stdout if result.stdout else result.stderr
    except subprocess.TimeoutExpired:
        return "Error: Repowise health timed out."
    except Exception as e:
        return f"Error running Repowise health: {e}"
