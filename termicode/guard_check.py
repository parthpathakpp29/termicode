"""Pre-commit health check installed by /guard on.

Runs as a separate process, invoked by Git as .git/hooks/pre-commit, so it
cannot rely on anything already loaded in a running TermiCode session — only
on termicode being installed and this module being importable from it.

A broken or missing Repowise must never block a commit: only an actual
finding against a staged file does. Anything else fails open with a warning,
so a dependency going missing after /guard was enabled cannot brick a user's
git workflow.
"""

import re
import subprocess
import sys

from termicode import repowise


# Below this, Repowise's own report has already moved a file out of its
# "healthy" band (see the Distribution line: healthy / warning / alert).
# A named constant here is a one-line tuning knob rather than a buried number.
BLOCK_BELOW_SCORE = 6.0

# Matches a row of the "Lowest-scoring files" table, e.g.:
#   │ termicode/cli.py                 │   2.5 │  62 │    9 │  506 │   —   │
_TABLE_ROW_RE = re.compile(r"^\s*[|│]\s*(\S+)\s*[|│]\s*([\d.]+)\s*[|│]")


def _run(command, timeout):
    """subprocess.run with the encoding pinned.

    Without this, decoding repowise's output with the platform's default
    codec raises UnicodeDecodeError on consoles that are not UTF-8 — this
    crashed the previous version of this check on an ordinary Windows setup.
    """
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _parse_scores(output: str) -> dict:
    """Maps file path to score, read from the "Lowest-scoring files" table.

    The report's summary line ("Worst: X/10 (file.py)") always names some file
    as the lowest scorer, healthy repo or not, so it cannot be used to decide
    whether a file is actually a problem. A real per-file score can.
    """
    scores = {}
    for line in output.splitlines():
        match = _TABLE_ROW_RE.match(line)
        if not match:
            continue
        file_path, score_text = match.group(1), match.group(2)
        try:
            scores[file_path] = float(score_text)
        except ValueError:
            continue  # the header row's "Score" column lands here; skip it
    return scores


def _staged_python_files() -> list:
    try:
        result = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in result.stdout.splitlines() if line.endswith(".py")]


def main() -> None:
    staged_files = _staged_python_files()
    if not staged_files:
        print("  -> No Python files staged. Proceeding.")
        sys.exit(0)

    if not repowise.is_available():
        print(f"  -> Repowise is not installed; skipping the health check ({repowise.INSTALL_HINT}).")
        sys.exit(0)

    print(f"  -> Running health check on {len(staged_files)} file(s)...")

    try:
        result = _run(["repowise", "health"], timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  -> Repowise health check could not run ({exc}); allowing the commit.")
        sys.exit(0)

    scores = _parse_scores(result.stdout or "")
    bad_files = [f for f in staged_files if f in scores and scores[f] < BLOCK_BELOW_SCORE]

    if not bad_files:
        print("Code health verified. Commit allowed.")
        sys.exit(0)

    print("\nHIGH RISK COMMIT BLOCKED")
    print("TermiCode detected architectural flaws or 'God Classes' in the files you are committing.")
    print("-" * 60)
    for file_path in bad_files:
        print(f"  {file_path} failed the health check.")
    print("-" * 60)
    print("To fix this automatically, open TermiCode and type:")
    for file_path in bad_files:
        print(f"  /heal {file_path}")
    print("\nCommit aborted. Refactor first, or run '/guard off' to disable this check.")
    sys.exit(1)


if __name__ == "__main__":
    main()
