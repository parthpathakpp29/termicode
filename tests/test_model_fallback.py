from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from termicode.cli import _stream_with_fallback
from termicode.models import next_fallback_model


STATS = {
    "free-coder-a": {"cost_per_m": 0.0, "tier": "free_coding"},
    "free-coder-b": {"cost_per_m": 0.0, "tier": "free_coding"},
    "free-general-a": {"cost_per_m": 0.0, "tier": "free_general"},
    "free-small-a": {"cost_per_m": 0.0, "tier": "free_small"},
    "paid-premium": {"cost_per_m": 3.0, "tier": "premium"},
}


def test_prefers_the_same_tier_as_the_failed_model():
    assert next_fallback_model(tried={"free-coder-a"}, model_stats=STATS, preferred_tier="free_coding") == "free-coder-b"


def test_falls_back_to_another_tier_once_the_preferred_one_is_exhausted():
    tried = {"free-coder-a", "free-coder-b"}
    result = next_fallback_model(tried=tried, model_stats=STATS, preferred_tier="free_coding")

    assert result in ("free-general-a", "free-small-a")


def test_never_returns_a_premium_model():
    tried = {"free-coder-a", "free-coder-b", "free-general-a", "free-small-a"}

    assert next_fallback_model(tried=tried, model_stats=STATS, preferred_tier="free_coding") is None


def test_never_returns_an_already_tried_model():
    tried = {"free-coder-a"}
    for _ in range(10):
        candidate = next_fallback_model(tried=tried, model_stats=STATS)
        if candidate is None:
            break
        assert candidate not in tried
        tried.add(candidate)

    # Every free model was eventually offered exactly once, and only those.
    assert tried == {"free-coder-a", "free-coder-b", "free-general-a", "free-small-a"}


def test_returns_none_when_no_preferred_tier_given_and_all_tried():
    tried = {"free-coder-a", "free-coder-b", "free-general-a", "free-small-a"}

    assert next_fallback_model(tried=tried, model_stats=STATS) is None


def _rate_limit_error():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "Rate limit reached"}})
    return RateLimitError("Rate limit reached", response=response, body=response.json())


class _ScriptedStream:
    """Stands in for _stream_agent_response: raises or returns per call, in order."""

    def __init__(self, script):
        self.script = list(script)
        self.models_called = []

    def __call__(self, client, model, messages, available_tools):
        self.models_called.append(model)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_falls_back_once_on_a_single_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "termicode.cli.OPENROUTER_MODEL_STATS",
        {"free-coder-a": {"tier": "free_coding"}, "free-coder-b": {"tier": "free_coding"}},
    )
    stream = _ScriptedStream([_rate_limit_error(), ("answer", {}, 12, "stop")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    content, tool_calls, usage, finish_reason, model_used = _stream_with_fallback(
        client=None, current_model="free-coder-a", messages=[], available_tools=[], user_manually_selected=False
    )

    assert content == "answer"
    assert model_used == "free-coder-b"
    assert stream.models_called == ["free-coder-a", "free-coder-b"]


def test_never_retries_the_same_model_twice(monkeypatch):
    monkeypatch.setattr(
        "termicode.cli.OPENROUTER_MODEL_STATS",
        {
            "free-coder-a": {"tier": "free_coding"},
            "free-coder-b": {"tier": "free_coding"},
            "free-general-a": {"tier": "free_general"},
        },
    )
    stream = _ScriptedStream([_rate_limit_error(), _rate_limit_error(), ("answer", {}, 5, "stop")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    _, _, _, _, model_used = _stream_with_fallback(
        client=None, current_model="free-coder-a", messages=[], available_tools=[], user_manually_selected=False
    )

    assert model_used == "free-general-a"
    assert len(stream.models_called) == len(set(stream.models_called)) == 3


def test_raises_once_every_free_model_is_exhausted(monkeypatch):
    monkeypatch.setattr(
        "termicode.cli.OPENROUTER_MODEL_STATS",
        {"free-coder-a": {"tier": "free_coding"}, "free-coder-b": {"tier": "free_coding"}},
    )
    error_a, error_b = _rate_limit_error(), _rate_limit_error()
    stream = _ScriptedStream([error_a, error_b])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(RateLimitError):
        _stream_with_fallback(
            client=None, current_model="free-coder-a", messages=[], available_tools=[], user_manually_selected=False
        )

    assert stream.models_called == ["free-coder-a", "free-coder-b"]


def test_manual_model_selection_bypasses_fallback_entirely(monkeypatch):
    """A user-picked model must fail exactly as it always did — no silent
    downgrade to a free model on their behalf."""
    monkeypatch.setattr("termicode.cli.OPENROUTER_MODEL_STATS", {"paid-premium": {"tier": "premium"}})
    stream = _ScriptedStream([_rate_limit_error()])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(RateLimitError):
        _stream_with_fallback(
            client=None, current_model="paid-premium", messages=[], available_tools=[], user_manually_selected=True
        )

    assert stream.models_called == ["paid-premium"]


def test_non_rate_limit_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr("termicode.cli.OPENROUTER_MODEL_STATS", {"free-coder-a": {"tier": "free_coding"}})
    stream = _ScriptedStream([ConnectionError("network is down")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(ConnectionError):
        _stream_with_fallback(
            client=None, current_model="free-coder-a", messages=[], available_tools=[], user_manually_selected=False
        )

    assert stream.models_called == ["free-coder-a"]
