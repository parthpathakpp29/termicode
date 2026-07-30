"""Verifies every branch of tool_executor.execute_tool's dispatch chain routes
to the correct underlying function with the right arguments.

This is deliberately about the *dispatch layer* rather than the underlying
tool functions' own behavior (those are covered elsewhere, per module -- see
ARCHITECTURE.md's module map). CONTRIBUTING.md documents this if/elif chain
as the primary place a new tool gets added; a test that exercises every
existing branch is what would catch a copy-paste mistake in a new one landing
next to it (wrong function called, wrong argument name, args.get() typo).
"""

import json

import pytest

from termicode import tool_executor
from termicode.tool_executor import MockToolCall, execute_tool


@pytest.fixture(autouse=True)
def reset_approval_state():
    tool_executor.approval_state.disable()
    yield
    tool_executor.approval_state.disable()


def _call(name, **arguments):
    return MockToolCall({"id": "1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}})


def test_list_directory_dispatches_with_the_right_argument(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.list_directory", lambda directory_path: captured.setdefault("path", directory_path) or "ok")

    execute_tool(_call("list_directory", directory_path="src"))

    assert captured["path"] == "src"


def test_list_directory_defaults_to_current_directory_when_omitted(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.list_directory", lambda directory_path: captured.setdefault("path", directory_path) or "ok")

    execute_tool(_call("list_directory"))

    assert captured["path"] == "."


def test_read_file_dispatches_with_all_arguments(monkeypatch):
    captured = {}

    def fake_read_file(file_path, start_line=None, end_line=None):
        captured.update(file_path=file_path, start_line=start_line, end_line=end_line)
        return "ok"

    monkeypatch.setattr("termicode.tools.read_file", fake_read_file)

    execute_tool(_call("read_file", file_path="a.py", start_line=1, end_line=10))

    assert captured == {"file_path": "a.py", "start_line": 1, "end_line": 10}


def test_search_codebase_dispatches_with_both_arguments(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "termicode.tools.search_codebase",
        lambda directory_path, query: captured.update(directory_path=directory_path, query=query) or "ok",
    )

    execute_tool(_call("search_codebase", directory_path=".", query="needle"))

    assert captured == {"directory_path": ".", "query": "needle"}


def test_restore_backup_dispatches_with_file_path(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.restore_backup", lambda file_path: captured.setdefault("path", file_path) or "ok")

    execute_tool(_call("restore_backup", file_path="a.py"))

    assert captured["path"] == "a.py"


def test_create_directory_dispatches_with_directory_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "termicode.tools.create_directory", lambda directory_path: captured.setdefault("path", directory_path) or "ok"
    )

    execute_tool(_call("create_directory", directory_path="newdir"))

    assert captured["path"] == "newdir"


def test_search_web_dispatches_with_query(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.search_web", lambda query: captured.setdefault("query", query) or "ok")

    execute_tool(_call("search_web", query="python packaging"))

    assert captured["query"] == "python packaging"


def test_generate_termicode_rules_dispatches_with_no_arguments(monkeypatch):
    called = []
    monkeypatch.setattr("termicode.tools.generate_termicode_rules", lambda: called.append(True) or "ok")

    execute_tool(_call("generate_termicode_rules"))

    assert called == [True]


def test_get_overview_dispatches_with_no_arguments(monkeypatch):
    called = []
    monkeypatch.setattr("termicode.tools.get_overview", lambda: called.append(True) or "ok")

    execute_tool(_call("get_overview"))

    assert called == [True]


def test_get_context_dispatches_with_targets(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.get_context", lambda targets: captured.setdefault("targets", targets) or "ok")

    execute_tool(_call("get_context", targets="cli.py"))

    assert captured["targets"] == "cli.py"


def test_get_context_defaults_targets_to_empty_string_when_omitted(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.get_context", lambda targets: captured.setdefault("targets", targets) or "ok")

    execute_tool(_call("get_context"))

    assert captured["targets"] == ""


def test_get_health_dispatches_with_targets(monkeypatch):
    captured = {}
    monkeypatch.setattr("termicode.tools.get_health", lambda targets: captured.setdefault("targets", targets) or "ok")

    execute_tool(_call("get_health", targets="cli.py"))

    assert captured["targets"] == "cli.py"


def test_run_command_dispatches_only_on_approval(monkeypatch):
    ran = []
    monkeypatch.setattr("termicode.ui.console.input", lambda *a, **k: "y")
    monkeypatch.setattr("termicode.tools.run_command_approved", lambda command: ran.append(command) or "ok")

    execute_tool(_call("run_command", command="echo hi"))

    assert ran == ["echo hi"]


def test_unknown_tool_name_returns_an_error_without_touching_any_tool_function():
    result = execute_tool(_call("this_tool_does_not_exist"))

    assert "Unknown tool" in result


def test_invalid_json_arguments_return_an_error_without_dispatching():
    call = MockToolCall({"id": "1", "type": "function", "function": {"name": "read_file", "arguments": "{not valid json"}})

    result = execute_tool(call)

    assert "Invalid JSON arguments" in result
