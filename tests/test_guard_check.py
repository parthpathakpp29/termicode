import subprocess

import pytest

from termicode import guard_check


def _health_result(stdout):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def _table(*rows):
    """Build a realistic repowise "Lowest-scoring files" table.

    Mirrors the actual box-drawing output, since the parser keys off the
    pipe-delimited row format, not on any particular wording.
    """
    header = (
        "Lowest-scoring files ({})\n"
        "┌─────────┬───────┬─────┬──────┬──────┬───────┐\n"
        "│ File    │ Score │ CCN │ Nest │ NLOC │ Test? │\n"
        "├─────────┼───────┼─────┼──────┼──────┼───────┤\n"
    ).format(len(rows))
    body = "".join(f"│ {path:<7} │ {score:>5.1f} │   1 │    0 │    5 │   —   │\n" for path, score in rows)
    footer = "└─────────┴───────┴─────┴──────┴──────┴───────┘\n"
    return header + body + footer


def test_no_staged_python_files_allows_commit_without_calling_repowise(monkeypatch, capsys):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: [])

    def fail_if_called(*args, **kwargs):
        raise AssertionError("repowise.is_available should not be reached")

    monkeypatch.setattr(guard_check.repowise, "is_available", fail_if_called)

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "No Python files staged" in capsys.readouterr().out


def test_missing_repowise_allows_commit(monkeypatch, capsys):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["app.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: False)

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "not installed" in capsys.readouterr().out


def test_clean_health_report_allows_commit(monkeypatch, capsys):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["app.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: True)
    monkeypatch.setattr(guard_check, "_run", lambda command, timeout: _health_result("Average: 9.1/10\nAll healthy."))

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "Commit allowed" in capsys.readouterr().out


def test_a_staged_low_scoring_file_blocks_the_commit(monkeypatch, capsys):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["cli.py", "ui.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: True)
    output = "Average: 7.9/10 [Warning] . Worst: 2.5/10 (cli.py)\n" + _table(("cli.py", 2.5), ("ui.py", 9.1))
    monkeypatch.setattr(guard_check, "_run", lambda command, timeout: _health_result(output))

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "BLOCKED" in out
    assert "cli.py failed" in out
    # ui.py scored well above the threshold; only the real offender is named.
    assert "ui.py failed" not in out


def test_findings_that_do_not_touch_staged_files_allow_the_commit(monkeypatch, capsys):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["new_feature.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: True)
    output = "Average: 7.9/10 [Warning] . Worst: 2.5/10 (legacy.py)\n" + _table(
        ("legacy.py", 2.5), ("new_feature.py", 9.4)
    )
    monkeypatch.setattr(guard_check, "_run", lambda command, timeout: _health_result(output))

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "Commit allowed" in capsys.readouterr().out


def test_a_healthy_repo_does_not_block_the_commit_despite_a_worst_line(monkeypatch, capsys):
    """Regression test: repowise always prints a "Worst: X/10" summary line,
    even in a fully healthy repo, since it just names whichever file scored
    lowest. Treating that line's presence as a finding blocked every commit
    unconditionally — reproduced against real repowise output before this fix.
    """
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["good.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: True)
    output = "Average: 10.0/10 [Healthy] . Worst: 10.0/10 (good.py)\n" + _table(("good.py", 10.0))
    monkeypatch.setattr(guard_check, "_run", lambda command, timeout: _health_result(output))

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "Commit allowed" in capsys.readouterr().out


@pytest.mark.parametrize(
    "failure",
    [subprocess.TimeoutExpired(cmd="repowise health", timeout=60), FileNotFoundError("repowise")],
)
def test_a_broken_repowise_fails_open_rather_than_blocking_every_commit(monkeypatch, capsys, failure):
    monkeypatch.setattr(guard_check, "_staged_python_files", lambda: ["app.py"])
    monkeypatch.setattr(guard_check.repowise, "is_available", lambda: True)

    def raise_failure(command, timeout):
        raise failure

    monkeypatch.setattr(guard_check, "_run", raise_failure)

    with pytest.raises(SystemExit) as exc:
        guard_check.main()

    assert exc.value.code == 0
    assert "allowing the commit" in capsys.readouterr().out


def test_staged_python_files_filters_to_py_extension(monkeypatch):
    monkeypatch.setattr(
        guard_check,
        "_run",
        lambda command, timeout: _health_result("app.py\nREADME.md\npkg/mod.py\nnotes.txt\n"),
    )

    assert guard_check._staged_python_files() == ["app.py", "pkg/mod.py"]


def test_staged_python_files_returns_empty_list_when_git_is_unavailable(monkeypatch):
    def raise_missing(command, timeout):
        raise FileNotFoundError("git")

    monkeypatch.setattr(guard_check, "_run", raise_missing)

    assert guard_check._staged_python_files() == []


def test_parse_scores_reads_a_realistic_table():
    output = _table(("termicode/cli.py", 2.5), ("termicode/ui.py", 9.1))

    scores = guard_check._parse_scores(output)

    assert scores == {"termicode/cli.py": 2.5, "termicode/ui.py": 9.1}


def test_parse_scores_ignores_non_table_lines():
    output = (
        "Hotspot: 3.91/10 · Average: 7.94/10 [Warning] · Worst: 2.5/10 (cli.py)\n"
        "Distribution (by code volume): 67.4% healthy (28 files)\n"
    ) + _table(("cli.py", 2.5))

    scores = guard_check._parse_scores(output)

    assert scores == {"cli.py": 2.5}


def test_parse_scores_on_empty_output():
    assert guard_check._parse_scores("") == {}
