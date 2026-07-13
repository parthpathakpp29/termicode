import subprocess
from datetime import datetime

from termicode.doctor import format_doctor_summary, run_doctor
from termicode.report import build_report_markdown, generate_repo_report


def test_format_doctor_summary_lists_passes_and_fixes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def fake_runner(command, timeout):
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 1, "", "not git")
        if command[0] == "repowise":
            return subprocess.CompletedProcess(command, 0, "repowise 1.0", "")
        raise AssertionError(f"unexpected command: {command}")

    checks = run_doctor(runner=fake_runner)
    summary = format_doctor_summary(checks)

    assert "TermiCode Doctor:" in summary
    assert "OpenRouter API key" in summary
    assert "OPENROUTER_API_KEY is missing" in summary
    assert "Repowise" in summary


def test_build_report_markdown_includes_health_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generated_at = datetime(2026, 7, 9, 12, 30, 0)

    markdown = build_report_markdown("Worst: termicode/cli.py", generated_at=generated_at)

    assert "# TermiCode Repo Health Report" in markdown
    assert "2026-07-09 12:30:00" in markdown
    assert "Worst: termicode/cli.py" in markdown
    assert "Suggested Next Actions" in markdown


def test_generate_repo_report_writes_markdown_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    generated_at = datetime(2026, 7, 9, 12, 30, 0)

    report_path = generate_repo_report(
        output_dir="reports",
        health_provider=lambda targets: "Average: 7.33/10",
        generated_at=generated_at,
    )

    report_file = tmp_path / report_path
    assert report_file.exists()
    assert report_file.name == "termicode-report-20260709-123000.md"
    assert "Average: 7.33/10" in report_file.read_text(encoding="utf-8")
