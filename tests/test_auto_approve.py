import json

import pytest

from termicode import tool_executor
from termicode.tool_executor import MockToolCall, execute_tool


@pytest.fixture(autouse=True)
def reset_approval_state():
    """auto_approve_files persists on a module-level object across calls, so
    tests must not leak it into each other."""
    tool_executor.approval_state.disable()
    yield
    tool_executor.approval_state.disable()


def _call(name, **arguments):
    return MockToolCall({"id": "1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}})


def test_answering_always_approves_and_enables_auto_approve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: "a")

    result = execute_tool(_call("write_file", file_path="new.py", content="x = 1\n"))

    assert result.startswith("Success")
    assert tool_executor.approval_state.auto_approve_files is True


def test_once_enabled_later_writes_do_not_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool_executor.approval_state.enable()

    def fail_if_prompted(*args, **kwargs):
        raise AssertionError("should not block for input once auto-approve is on")

    monkeypatch.setattr("termicode.ui.console.input", fail_if_prompted)

    result = execute_tool(_call("write_file", file_path="new.py", content="x = 1\n"))

    assert result.startswith("Success")
    assert (tmp_path / "new.py").exists()


def test_auto_approved_writes_still_show_the_preview(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tool_executor.approval_state.enable()
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    execute_tool(_call("write_file", file_path="new.py", content="print('hi')\n"))
    rendered = capsys.readouterr().out

    assert "auto-approved" in rendered.lower()
    assert "print('hi')" in rendered


def test_plain_yes_approves_without_enabling_auto_approve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: "y")

    execute_tool(_call("write_file", file_path="a.py", content="1\n"))
    assert tool_executor.approval_state.auto_approve_files is False

    # The next write must prompt again, since "y" only approved the one action.
    prompts = []
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: prompts.append(1) or "n")
    execute_tool(_call("write_file", file_path="b.py", content="2\n"))
    assert prompts == [1]


def test_declining_does_not_enable_auto_approve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: "n")

    result = execute_tool(_call("write_file", file_path="new.py", content="x = 1\n"))

    assert "blocked" in result.lower()
    assert tool_executor.approval_state.auto_approve_files is False
    assert not (tmp_path / "new.py").exists()


def test_auto_approve_covers_edit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing.py").write_text("value = 1\n", encoding="utf-8")
    tool_executor.approval_state.enable()
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    result = execute_tool(_call("edit_file", file_path="existing.py", search_string="value = 1", replace_string="value = 2"))

    assert result.startswith("Success")


def test_auto_approve_covers_delete(tmp_path, monkeypatch):
    # A separate file from the edit test above: edit_file_approved and
    # delete_file_approved both name their backup after the current second
    # (see file_tools.py), so operating on the same path immediately after an
    # edit can collide with the backup the edit just created. That collision
    # is a pre-existing file_tools.py issue, unrelated to auto-approve itself.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "doomed.py").write_text("value = 1\n", encoding="utf-8")
    tool_executor.approval_state.enable()
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    result = execute_tool(_call("delete_file", file_path="doomed.py"))

    assert result.startswith("Success")


def test_auto_approve_does_not_cover_run_command(tmp_path, monkeypatch):
    """A diff preview can show a file change in advance; it cannot show what
    an arbitrary shell command will do, so run_command must always prompt."""
    monkeypatch.chdir(tmp_path)
    tool_executor.approval_state.enable()
    prompted = []
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: prompted.append(1) or "n")

    result = execute_tool(_call("run_command", command="echo hi"))

    assert prompted == [1]
    assert "denied" in result.lower()


def test_protected_files_are_still_refused_even_with_auto_approve_on(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool_executor.approval_state.enable()
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    result = execute_tool(_call("write_file", file_path=".env", content="HACKED=1"))

    assert "restricted" in result.lower()
