import importlib
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _run_command(command: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _check_python_version() -> DoctorCheck:
    version = sys.version_info
    ok = version >= (3, 8)
    detail = f"Python {platform.python_version()}"
    return DoctorCheck(
        name="Python version",
        ok=ok,
        detail=detail,
        fix="Install Python 3.8 or newer." if not ok else "",
    )


def _check_api_key() -> DoctorCheck:
    has_key = bool(os.getenv("OPENROUTER_API_KEY", "").strip())
    return DoctorCheck(
        name="OpenRouter API key",
        ok=has_key,
        detail="OPENROUTER_API_KEY is set." if has_key else "OPENROUTER_API_KEY is missing.",
        fix="Add OPENROUTER_API_KEY=your_key_here to .env or your shell environment." if not has_key else "",
    )


def _check_git_repo(runner: Callable[[List[str], int], subprocess.CompletedProcess]) -> DoctorCheck:
    if not os.path.isdir(".git"):
        return DoctorCheck(
            name="Git repository",
            ok=False,
            detail="This folder is not a Git repository.",
            fix="Run git init before using /guard.",
        )

    try:
        result = runner(["git", "rev-parse", "--is-inside-work-tree"], 10)
        ok = result.returncode == 0 and result.stdout.strip() == "true"
        return DoctorCheck(
            name="Git repository",
            ok=ok,
            detail="Git worktree detected." if ok else "Git exists but this folder is not a valid worktree.",
            fix="Run git status to inspect the repository." if not ok else "",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(
            name="Git repository",
            ok=False,
            detail=f"Could not run git: {exc}",
            fix="Install Git and make sure it is available in PATH.",
        )


def _check_repowise(runner: Callable[[List[str], int], subprocess.CompletedProcess]) -> DoctorCheck:
    try:
        result = runner(["repowise", "--version"], 10)
        output = (result.stdout or result.stderr).strip()
        ok = result.returncode == 0
        return DoctorCheck(
            name="Repowise",
            ok=ok,
            detail=output or ("Repowise is available." if ok else "Repowise command failed."),
            fix="Install or repair Repowise before using /heal, /guard, and /report." if not ok else "",
        )
    except FileNotFoundError:
        return DoctorCheck(
            name="Repowise",
            ok=False,
            detail="Repowise is not installed or not in PATH.",
            fix="Install Repowise before using /heal, /guard, and /report.",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck(
            name="Repowise",
            ok=False,
            detail=f"Could not run Repowise: {exc}",
            fix="Check your Repowise installation.",
        )


def _check_import(module_name: str) -> DoctorCheck:
    try:
        importlib.import_module(module_name)
        return DoctorCheck(name=f"Python package: {module_name}", ok=True, detail="Installed.")
    except ImportError:
        return DoctorCheck(
            name=f"Python package: {module_name}",
            ok=False,
            detail="Missing.",
            fix=f"Install project dependencies; missing package: {module_name}.",
        )


def _check_workspace_write() -> DoctorCheck:
    probe_path = ".termicode_doctor_write_test"
    try:
        with open(probe_path, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe_path)
        return DoctorCheck(name="Workspace write access", ok=True, detail="Can write to the current folder.")
    except OSError as exc:
        return DoctorCheck(
            name="Workspace write access",
            ok=False,
            detail=f"Cannot write to the current folder: {exc}",
            fix="Run TermiCode from a writable project folder.",
        )


def run_doctor(
    runner: Optional[Callable[[List[str], int], subprocess.CompletedProcess]] = None,
) -> List[DoctorCheck]:
    """Run local setup checks for TermiCode."""
    command_runner = runner or _run_command
    return [
        _check_python_version(),
        _check_api_key(),
        _check_git_repo(command_runner),
        _check_repowise(command_runner),
        _check_import("openai"),
        _check_import("dotenv"),
        _check_import("rich"),
        _check_import("ddgs"),
        _check_workspace_write(),
    ]


def format_doctor_summary(checks: List[DoctorCheck]) -> str:
    passed = sum(1 for check in checks if check.ok)
    total = len(checks)
    lines = [f"TermiCode Doctor: {passed}/{total} checks passed.", ""]

    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        lines.append(f"- {status}: {check.name} - {check.detail}")
        if check.fix:
            lines.append(f"  Fix: {check.fix}")

    return "\n".join(lines)
