import os

from termicode.cli import _install_guard_hook, _remove_guard_hook


def test_hook_is_not_installed_outside_a_git_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _install_guard_hook()

    assert not (tmp_path / ".git").exists()
    assert "Not a Git repository" in capsys.readouterr().out


def test_hook_is_not_installed_when_the_console_script_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    monkeypatch.setattr("termicode.cli.shutil.which", lambda name: None)

    _install_guard_hook()

    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert "termicode-guard-check" in capsys.readouterr().out


def test_hook_calls_the_console_script_not_a_bundled_file(tmp_path, monkeypatch, capsys):
    """The hook must not depend on pre_commit_hook.py existing in the project."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    monkeypatch.setattr("termicode.cli.shutil.which", lambda name: f"/usr/bin/{name}")

    _install_guard_hook()

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    content = hook_path.read_text(encoding="utf-8")

    assert "termicode-guard-check" in content
    assert "pre_commit_hook.py" not in content
    assert "Pre-Commit Guardian ENABLED" in capsys.readouterr().out


def test_remove_hook_deletes_an_existing_hook(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit").write_text("#!/bin/sh\ntermicode-guard-check\n", encoding="utf-8")

    _remove_guard_hook()

    assert not (hooks_dir / "pre-commit").exists()
    assert "DISABLED" in capsys.readouterr().out


def test_remove_hook_is_a_no_op_when_nothing_is_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _remove_guard_hook()

    assert "already disabled" in capsys.readouterr().out
