import subprocess

import pytest

from termicode import repowise
from termicode.doctor import DoctorCheck, format_doctor_summary, run_doctor
from termicode.health_tools import get_health
from termicode.prompts import build_system_prompt, get_available_tools


@pytest.fixture(autouse=True)
def clear_repowise_cache():
    """Availability is cached per process, so isolate every test from the rest."""
    repowise.reset_cache()
    yield
    repowise.reset_cache()


def _tool_names(tools):
    return [tool["function"]["name"] for tool in tools]


def test_is_available_false_when_binary_missing(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("repowise")

    monkeypatch.setattr("termicode.repowise.subprocess.run", fake_run)

    assert repowise.is_available() is False


def test_is_available_false_when_binary_is_broken(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "boom")

    monkeypatch.setattr("termicode.repowise.subprocess.run", fake_run)

    assert repowise.is_available() is False


def test_is_available_true_and_probe_is_cached(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "repowise, version 0.28.0", "")

    monkeypatch.setattr("termicode.repowise.subprocess.run", fake_run)

    assert repowise.is_available() is True
    assert repowise.is_available() is True
    assert len(calls) == 1


def test_ensure_indexed_is_bounded_by_timeout(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("termicode.repowise.subprocess.run", fake_run)
    repowise.ensure_indexed()

    assert captured["timeout"] == 120


def test_get_health_returns_install_hint_when_unavailable(monkeypatch):
    monkeypatch.setattr("termicode.repowise.is_available", lambda: False)

    result = get_health()

    assert repowise.INSTALL_HINT in result
    assert "not installed" in result


def test_system_prompt_omits_repowise_instruction_when_unavailable():
    prompt = build_system_prompt("map", repowise_available=False)

    assert "REPOWISE INTEGRATION" not in prompt
    assert "get_context" not in prompt
    assert "RIPPLE ORCHESTRATION" in prompt


def test_system_prompt_numbering_stays_contiguous_when_degraded():
    prompt = build_system_prompt("map", repowise_available=False)

    assert "8. ANTI-WANDERING PROTOCOL" in prompt
    assert "9. RIPPLE ORCHESTRATION" in prompt
    assert "10." not in prompt


def test_system_prompt_defaults_to_full_instructions():
    assert build_system_prompt("map", "recap") == build_system_prompt("map", "recap", True)
    assert "REPOWISE INTEGRATION" in build_system_prompt("map")


def test_tool_schema_excludes_repowise_tools_when_unavailable():
    names = _tool_names(get_available_tools(repowise_available=False))

    assert "get_overview" not in names
    assert "get_context" not in names
    assert "get_health" not in names
    assert "read_file" in names
    assert "edit_file" in names


def test_tool_schema_defaults_to_full_list():
    assert get_available_tools() == get_available_tools(True)

    names = _tool_names(get_available_tools())

    assert {"get_overview", "get_context", "get_health"} <= set(names)


def test_missing_repowise_is_reported_as_optional_not_failure():
    def fake_runner(command, timeout):
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, "true", "")
        if command[0] == "repowise":
            raise FileNotFoundError("repowise")
        raise AssertionError(f"unexpected command: {command}")

    checks = run_doctor(runner=fake_runner)
    repowise_check = next(check for check in checks if check.name == "Repowise")

    assert repowise_check.optional is True
    assert repowise_check.ok is False

    summary = format_doctor_summary(checks)

    assert "OPTIONAL: Repowise" in summary
    assert "FAIL: Repowise" not in summary


def test_optional_checks_are_excluded_from_the_required_count():
    checks = [
        DoctorCheck(name="Required", ok=True, detail="fine"),
        DoctorCheck(name="Optional", ok=False, detail="absent", optional=True),
    ]

    assert "1/1 required checks passed" in format_doctor_summary(checks)
