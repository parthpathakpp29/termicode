import subprocess

import pytest

from termicode import tools
from termicode.command_tools import run_command_approved
from termicode.path_safety import _is_protected, validate_path


def test_validate_path_blocks_parent_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(PermissionError):
        validate_path("../outside.txt")


def test_protected_secret_files_are_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    secret = tmp_path / ".env"
    secret.write_text("OPENROUTER_API_KEY=secret", encoding="utf-8")

    assert _is_protected(".env")
    assert "permanently restricted" in tools.read_file(".env")
    assert "permanently restricted" in tools.edit_file_approved(".env", "secret", "safe")


def test_edit_file_creates_backup_and_restore_recovers_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "example.py"
    target.write_text("value = 1\n", encoding="utf-8")

    result = tools.edit_file_approved("example.py", "value = 1", "value = 2")

    assert result.startswith("Success")
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    assert list(tmp_path.glob("example.py.*.bak"))

    restore_result = tools.restore_backup("example.py")

    assert restore_result.startswith("Success")
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_search_codebase_respects_gitignore(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "visible.py").write_text("needle = True\n", encoding="utf-8")
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    (ignored_dir / "hidden.py").write_text("needle = False\n", encoding="utf-8")

    result = tools.search_codebase(".", "needle")

    assert "visible.py" in result
    assert "hidden.py" not in result


def test_run_command_timeout_message(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="slow", timeout=30)

    monkeypatch.setattr("termicode.command_tools.subprocess.run", fake_run)

    assert "timed out" in run_command_approved("slow command")


def test_edit_then_delete_the_same_file_does_not_collide_on_backup_name(tmp_path, monkeypatch):
    """Reproduces the original bug: edit and delete on the same file, back to
    back, used to create two .bak files named after the same wall-clock
    second, and os.rename raised on Windows when the second collided with
    the first."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "hot.py"
    target.write_text("value = 1\n", encoding="utf-8")

    edit_result = tools.edit_file_approved("hot.py", "value = 1", "value = 2")
    delete_result = tools.delete_file_approved("hot.py")

    assert edit_result.startswith("Success")
    assert delete_result.startswith("Success")

    backups = sorted(tmp_path.glob("hot.py.*.bak"))
    assert len(backups) == 2
    assert backups[0].name != backups[1].name


def test_restore_backup_picks_the_chronologically_latest_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "example.py"
    target.write_text("version = 3\n", encoding="utf-8")

    # Same digit width as real time.time_ns() values for the next ~260 years,
    # which is what makes the lexicographic glob-sort in restore_backup
    # equivalent to a numeric/chronological sort.
    timestamps = iter([1700000000000000001, 1700000000000000002, 1700000000000000003])
    monkeypatch.setattr("termicode.file_tools.time.time_ns", lambda: next(timestamps))

    tools.write_file_approved("example.py", "version = 1\n")  # backup of "version = 3"
    tools.write_file_approved("example.py", "version = 2\n")  # backup of "version = 1"
    tools.write_file_approved("example.py", "version = 4\n")  # backup of "version = 2"

    restore_result = tools.restore_backup("example.py")

    assert restore_result.startswith("Success")
    # The most recent backup held "version = 2", not the oldest ("version = 3").
    assert target.read_text(encoding="utf-8") == "version = 2\n"
