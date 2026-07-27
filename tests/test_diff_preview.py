import difflib

import pytest

from termicode import tools
from termicode.diff import (
    BINARY_NOTICE,
    MAX_PREVIEW_LINES,
    PROTECTED_NOTICE,
    build_delete_preview,
    build_edit_preview,
    build_write_preview,
)
from termicode.ui import print_security_alert


def _changed_lines(diff_text):
    """The +/- body of a unified diff, excluding its file headers."""
    return [
        line
        for line in diff_text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


def test_edit_preview_shows_removed_and_added_lines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    preview = build_edit_preview("example.py", "return 1", "return 2")

    assert "-    return 1" in preview
    assert "+    return 2" in preview


def test_edit_preview_matches_what_is_actually_written(tmp_path, monkeypatch):
    """Guards against the preview drifting from edit_file_approved."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "example.py"
    original = "alpha = 1\nbeta = 2\ngamma = 3\n"
    target.write_text(original, encoding="utf-8")

    preview = build_edit_preview("example.py", "beta = 2", "beta = 22")
    tools.edit_file_approved("example.py", "beta = 2", "beta = 22")
    written = target.read_text(encoding="utf-8")

    real_diff = "\n".join(
        difflib.unified_diff(original.splitlines(), written.splitlines(), lineterm="")
    )

    assert _changed_lines(preview) == _changed_lines(real_diff)


def test_edit_preview_warns_when_search_text_is_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("value = 1\n", encoding="utf-8")

    preview = build_edit_preview("example.py", "not_here", "x")

    assert "was not found" in preview
    assert "will fail" in preview


def test_edit_preview_flags_multiple_occurrences(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("x = 1\ny = 1\nz = 1\n", encoding="utf-8")

    preview = build_edit_preview("example.py", "= 1", "= 2")

    assert "appears 3 times" in preview
    assert "only the first is replaced" in preview


def test_edit_preview_reports_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert "does not exist" in build_edit_preview("ghost.py", "a", "b")


def test_crlf_file_does_not_produce_a_whole_file_diff(tmp_path, monkeypatch):
    """Windows line endings must not make every line look changed."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "crlf.py"
    target.write_bytes(b"alpha = 1\r\nbeta = 2\r\ngamma = 3\r\n")

    preview = build_edit_preview("crlf.py", "beta = 2", "beta = 22")

    assert _changed_lines(preview) == ["-beta = 2", "+beta = 22"]


def test_protected_paths_are_never_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=super-secret\n", encoding="utf-8")

    previews = [
        build_edit_preview(".env", "super-secret", "x"),
        build_write_preview(".env", "replacement"),
        build_delete_preview(".env"),
    ]

    for preview in previews:
        assert preview == PROTECTED_NOTICE
        assert "super-secret" not in preview


def test_write_preview_shows_new_file_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    preview = build_write_preview("fresh.py", "print('hi')\nprint('there')\n")

    assert "New file" in preview
    assert "2 lines" in preview
    assert "+print('hi')" in preview


def test_write_preview_diffs_an_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("old = 1\n", encoding="utf-8")

    preview = build_write_preview("example.py", "new = 2\n")

    assert "-old = 1" in preview
    assert "+new = 2" in preview


def test_write_preview_reports_an_unchanged_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("same = 1\n", encoding="utf-8")

    assert "No changes" in build_write_preview("example.py", "same = 1\n")


def test_delete_preview_reports_size_and_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doomed.py").write_text("a = 1\nb = 2\n", encoding="utf-8")

    preview = build_delete_preview("doomed.py")

    assert "2 lines" in preview
    assert ".bak backup" in preview
    assert "a = 1" in preview


def test_binary_files_are_not_previewed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe\x00\x01binary")

    assert build_write_preview("blob.bin", "text") == BINARY_NOTICE


def test_paths_outside_the_workspace_are_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert "Access denied" in build_write_preview("../outside.txt", "text")


def test_long_previews_are_capped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = "".join(f"line {n}\n" for n in range(500))

    preview = build_write_preview("big.py", body)

    assert "more lines not shown" in preview
    assert len(preview.splitlines()) <= MAX_PREVIEW_LINES + 3


@pytest.mark.parametrize(
    "answer,expected",
    [("y", True), ("Y", True), ("n", False), ("", False)],
)
def test_security_alert_still_works_without_a_preview(monkeypatch, answer, expected):
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: answer)

    assert print_security_alert("Write / Overwrite File", "example.py") is expected


def test_security_alert_renders_the_preview(monkeypatch, capsys):
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: "n")

    print_security_alert("Surgical File Edit", "example.py", "-old line\n+new line")
    rendered = capsys.readouterr().out

    assert "Proposed change" in rendered
    assert "old line" in rendered
    assert "new line" in rendered
