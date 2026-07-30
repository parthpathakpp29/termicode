import pytest

from termicode.search_tools import search_codebase, search_web


class _FakeDDGS:
    """Stands in for ddgs.DDGS, used as a context manager by search_web."""

    def __init__(self, results):
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def text(self, query, max_results=5):
        return self._results


def test_search_web_formats_results(monkeypatch):
    results = [
        {"title": "First result", "href": "https://example.com/1", "body": "First snippet"},
        {"title": "Second result", "href": "https://example.com/2", "body": "Second snippet"},
    ]
    monkeypatch.setattr("termicode.search_tools.DDGS", lambda: _FakeDDGS(results))

    output = search_web("test query")

    assert "First result" in output
    assert "https://example.com/1" in output
    assert "First snippet" in output
    assert "Second result" in output


def test_search_web_handles_no_results(monkeypatch):
    monkeypatch.setattr("termicode.search_tools.DDGS", lambda: _FakeDDGS([]))

    assert "No results found" in search_web("obscure query")


def test_search_web_handles_missing_fields_gracefully(monkeypatch):
    """A result missing a field must not crash formatting."""
    monkeypatch.setattr("termicode.search_tools.DDGS", lambda: _FakeDDGS([{}]))

    output = search_web("query")

    assert "No Title" in output
    assert "No URL" in output


def test_search_web_reports_an_error_instead_of_raising(monkeypatch):
    class _RaisingDDGS:
        def __enter__(self):
            raise ConnectionError("network is down")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("termicode.search_tools.DDGS", lambda: _RaisingDDGS())

    result = search_web("query")

    assert "Error searching the web" in result


def test_search_codebase_finds_a_match_with_line_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("first line\nneedle here\nlast line\n", encoding="utf-8")

    result = search_codebase(".", "needle")

    assert "example.py" in result
    assert "Line 2" in result
    assert "needle here" in result


def test_search_codebase_reports_no_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "example.py").write_text("nothing relevant\n", encoding="utf-8")

    assert "No matches found" in search_codebase(".", "needle")


def test_search_codebase_skips_protected_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET_TOKEN=needle\n", encoding="utf-8")

    result = search_codebase(".", "needle")

    assert "No matches found" in result


def test_search_codebase_truncates_past_50_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lines = "\n".join(f"needle {i}" for i in range(60))
    (tmp_path / "big.py").write_text(lines, encoding="utf-8")

    result = search_codebase(".", "needle")

    assert "Found 60 matches. Showing first 50" in result
