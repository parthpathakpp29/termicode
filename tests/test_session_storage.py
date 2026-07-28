import json
import os
from pathlib import Path

import pytest

from termicode import session
from termicode.path_safety import _is_protected
from termicode.session import (
    LEGACY_HISTORY_FILE,
    LEGACY_MEMORY_FILE,
    history_path,
    load_chat_history,
    load_memory_summary,
    memory_path,
    migrate_legacy_session,
    save_session,
    session_dir,
    termicode_home,
)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point session storage at a throwaway directory, and work from another."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("TERMICODE_HOME", str(home))
    monkeypatch.chdir(project)
    monkeypatch.setattr(session, "_warned_about_fallback", False)
    return home, project


def test_session_files_live_outside_the_project(isolated_home):
    home, project = isolated_home

    assert Path(history_path()).is_relative_to(home)
    assert not Path(history_path()).is_relative_to(project)
    assert Path(memory_path()).is_relative_to(home)


def test_path_is_stable_for_the_same_project(isolated_home):
    assert history_path() == history_path()


def test_different_projects_get_different_files(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMICODE_HOME", str(tmp_path / "home"))

    paths = []
    for name in ("alpha", "beta"):
        project = tmp_path / name
        project.mkdir()
        monkeypatch.chdir(project)
        paths.append(history_path())

    assert paths[0] != paths[1]


def test_same_basename_in_different_locations_does_not_collide(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMICODE_HOME", str(tmp_path / "home"))

    paths = []
    for parent in ("one", "two"):
        project = tmp_path / parent / "api"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)
        paths.append(history_path())

    assert paths[0] != paths[1]
    assert all("api-" in Path(p).name for p in paths)


def test_save_and_load_round_trip(isolated_home):
    messages = [{"role": "system", "content": "prompt"}, {"role": "user", "content": "hello"}]

    save_session(messages, "a recap")

    assert load_chat_history() == messages
    assert load_memory_summary() == "a recap"


def test_saving_does_not_write_into_the_project(isolated_home):
    _, project = isolated_home

    save_session([{"role": "user", "content": "hello"}], "recap")

    assert list(project.iterdir()) == []


def test_migration_moves_legacy_files_out_of_the_project(isolated_home):
    _, project = isolated_home
    legacy_messages = [{"role": "user", "content": "from the old location"}]
    (project / LEGACY_HISTORY_FILE).write_text(json.dumps(legacy_messages), encoding="utf-8")
    (project / LEGACY_MEMORY_FILE).write_text(json.dumps({"summary": "old recap"}), encoding="utf-8")

    destination = migrate_legacy_session()

    assert destination is not None
    assert not (project / LEGACY_HISTORY_FILE).exists()
    assert not (project / LEGACY_MEMORY_FILE).exists()
    assert load_chat_history() == legacy_messages
    assert load_memory_summary() == "old recap"


def test_migration_never_overwrites_a_newer_session(isolated_home):
    _, project = isolated_home
    save_session([{"role": "user", "content": "current"}], "current recap")
    (project / LEGACY_HISTORY_FILE).write_text(json.dumps([{"role": "user", "content": "stale"}]), encoding="utf-8")

    migrate_legacy_session()

    assert load_chat_history() == [{"role": "user", "content": "current"}]
    # The legacy file is left alone rather than deleted; it is still user data.
    assert (project / LEGACY_HISTORY_FILE).exists()


def test_migration_is_a_no_op_without_legacy_files(isolated_home):
    assert migrate_legacy_session() is None


def test_termicode_home_is_the_parent_of_session_dir(isolated_home):
    home, _ = isolated_home

    assert termicode_home() == home
    assert session_dir() == home / "sessions"


def test_session_dir_falls_back_when_home_itself_is_unusable(isolated_home, monkeypatch):
    monkeypatch.setattr("termicode.session.termicode_home", lambda: None)

    assert session_dir() is None


def test_falls_back_to_the_project_when_home_is_unusable(isolated_home, monkeypatch):
    monkeypatch.setattr(session, "session_dir", lambda: None)

    assert history_path() == LEGACY_HISTORY_FILE
    assert memory_path() == LEGACY_MEMORY_FILE


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_session_directory_is_private_on_posix(isolated_home):
    history_path()

    assert (Path(history_path()).parent.stat().st_mode & 0o777) == 0o700


def test_dot_termicode_paths_are_protected():
    """Covers running TermiCode from the home directory itself."""
    assert _is_protected(".termicode/sessions/proj-a1b2c3d4.history.json")
    assert _is_protected(".termicode\\sessions\\proj-a1b2c3d4.history.json")
    assert _is_protected("nested/.termicode/sessions/x.json")
    assert not _is_protected("termicode/cli.py")
    assert not _is_protected("src/app.py")
