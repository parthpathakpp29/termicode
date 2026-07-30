import pytest

from termicode import startup


class _FakeCompletions:
    def __init__(self, should_fail):
        self.should_fail = should_fail
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.should_fail:
            raise ConnectionError("network is down")
        return object()


class _FakeChat:
    def __init__(self, should_fail):
        self.completions = _FakeCompletions(should_fail)


class _FakeClient:
    def __init__(self, should_fail=False):
        self.chat = _FakeChat(should_fail)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Every test controls its own key and cwd rather than inheriting the
    real environment or a real Repowise install."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)


def test_missing_api_key_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        startup.validate_startup()

    assert exc.value.code == 1


def test_blank_api_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "   ")

    with pytest.raises(SystemExit):
        startup.validate_startup()


def test_client_construction_failure_exits(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")

    def raise_on_construct(*args, **kwargs):
        raise ValueError("bad client config")

    monkeypatch.setattr("termicode.startup.OpenAI", raise_on_construct)

    with pytest.raises(SystemExit) as exc:
        startup.validate_startup()

    assert exc.value.code == 1


def test_connectivity_ping_failure_exits(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    monkeypatch.setattr("termicode.startup.OpenAI", lambda **kwargs: _FakeClient(should_fail=True))
    monkeypatch.setattr("termicode.repowise.is_available", lambda: False)

    with pytest.raises(SystemExit) as exc:
        startup.validate_startup()

    assert exc.value.code == 1


def test_successful_startup_returns_the_client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    fake_client = _FakeClient(should_fail=False)
    monkeypatch.setattr("termicode.startup.OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr("termicode.repowise.is_available", lambda: False)

    result = startup.validate_startup()

    assert result is fake_client
    assert fake_client.chat.completions.calls == 1


def test_repowise_available_triggers_indexing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    monkeypatch.setattr("termicode.startup.OpenAI", lambda **kwargs: _FakeClient())
    monkeypatch.setattr("termicode.repowise.is_available", lambda: True)

    indexed = []
    monkeypatch.setattr("termicode.repowise.ensure_indexed", lambda: indexed.append(True))

    startup.validate_startup()

    assert indexed == [True]


def test_repowise_indexing_failure_does_not_abort_startup(monkeypatch):
    """Indexing is a nice-to-have; a failure there must not be fatal the way
    a missing key or a failed connectivity ping is."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    monkeypatch.setattr("termicode.startup.OpenAI", lambda **kwargs: _FakeClient())
    monkeypatch.setattr("termicode.repowise.is_available", lambda: True)

    def raise_indexing_error():
        raise RuntimeError("index build failed")

    monkeypatch.setattr("termicode.repowise.ensure_indexed", raise_indexing_error)

    result = startup.validate_startup()

    assert result is not None


def test_repowise_unavailable_still_returns_a_working_client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake")
    fake_client = _FakeClient()
    monkeypatch.setattr("termicode.startup.OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr("termicode.repowise.is_available", lambda: False)

    result = startup.validate_startup()

    assert result is fake_client
