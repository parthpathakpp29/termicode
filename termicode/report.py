import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from termicode.health_tools import get_health


REPORT_DIR = ".termicode_reports"


def build_report_markdown(health_output: str, generated_at: Optional[datetime] = None) -> str:
    """Build a shareable Markdown report from local health output."""
    timestamp = generated_at or datetime.now()
    cwd = os.path.abspath(os.getcwd())

    return (
        "# TermiCode Repo Health Report\n\n"
        f"- Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- Project: `{cwd}`\n"
        "- Source: local Repowise health check\n\n"
        "## Executive Summary\n\n"
        "This report captures the current maintainability and risk signals for the repository. "
        "Use it before refactors, handoffs, client updates, or pre-sale technical review.\n\n"
        "## Health Output\n\n"
        "```text\n"
        f"{health_output.strip() or 'No health output returned.'}\n"
        "```\n\n"
        "## Suggested Next Actions\n\n"
        "1. Fix the lowest-scoring files first.\n"
        "2. Add or update tests around files touched by refactors.\n"
        "3. Re-run `/report` after major changes to compare progress.\n"
    )


def generate_repo_report(
    output_dir: str = REPORT_DIR,
    health_provider: Callable[[str], str] = get_health,
    generated_at: Optional[datetime] = None,
) -> str:
    """Generate a Markdown report file and return its path."""
    timestamp = generated_at or datetime.now()
    health_output = health_provider("")
    markdown = build_report_markdown(health_output, generated_at=timestamp)

    report_dir = Path(output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"termicode-report-{timestamp.strftime('%Y%m%d-%H%M%S')}.md"
    report_path.write_text(markdown, encoding="utf-8")
    return str(report_path)
