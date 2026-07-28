import httpx
import pytest
from openai import RateLimitError

from termicode.cli import _stream_with_fallback
from termicode.models import next_fallback_model, route_model


CANDIDATES = ["free-coder-a", "free-coder-b", "free-general-a"]


# --- next_fallback_model: works off a plain ranked candidate list now,
# not a tiered {id: {tier, cost_per_m}} dict. ---

def test_next_fallback_model_returns_the_first_untried_candidate():
    assert next_fallback_model(tried={"free-coder-a"}, candidates=CANDIDATES) == "free-coder-b"


def test_next_fallback_model_skips_every_tried_candidate_in_order():
    tried = {"free-coder-a", "free-coder-b"}

    assert next_fallback_model(tried=tried, candidates=CANDIDATES) == "free-general-a"


def test_next_fallback_model_returns_none_once_every_candidate_is_tried():
    tried = set(CANDIDATES)

    assert next_fallback_model(tried=tried, candidates=CANDIDATES) is None


def test_next_fallback_model_on_an_empty_candidate_list():
    assert next_fallback_model(tried=set(), candidates=[]) is None


# --- route_model: a manual override always wins; otherwise today's one
# policy returns the top-ranked candidate regardless of prompt/context_length,
# which the design explicitly accepts (see route_model's docstring) so a
# future policy can use them without every call site changing again. ---

def test_route_model_honors_a_manual_override():
    result = route_model("refactor this", "manually-picked-model", CANDIDATES, user_manually_selected=True)

    assert result == "manually-picked-model"


def test_route_model_returns_the_top_ranked_candidate_when_auto_routing():
    result = route_model("explain this function", "free-coder-a", CANDIDATES, user_manually_selected=False)

    assert result == CANDIDATES[0]


def test_route_model_treats_every_intent_the_same_today():
    """Documents the deliberate simplification: a trivial question and a real
    coding task both resolve to the same top pick, since there is no longer a
    reliable size/speed signal to route between them on."""
    coding_task = route_model("refactor the whole auth module", "x", CANDIDATES, user_manually_selected=False)
    simple_question = route_model("what does this variable do", "x", CANDIDATES, user_manually_selected=False)

    assert coding_task == simple_question == CANDIDATES[0]


def test_route_model_falls_back_to_current_model_with_no_candidates():
    result = route_model("anything", "current", [], user_manually_selected=False)

    assert result == "current"


# --- _stream_with_fallback ---

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
    stream = _ScriptedStream([_rate_limit_error(), ("answer", {}, 12, "stop")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    content, tool_calls, usage, finish_reason, model_used = _stream_with_fallback(
        client=None,
        current_model="free-coder-a",
        messages=[],
        available_tools=[],
        user_manually_selected=False,
        candidates=["free-coder-a", "free-coder-b"],
    )

    assert content == "answer"
    assert model_used == "free-coder-b"
    assert stream.models_called == ["free-coder-a", "free-coder-b"]


def test_never_retries_the_same_model_twice(monkeypatch):
    stream = _ScriptedStream([_rate_limit_error(), _rate_limit_error(), ("answer", {}, 5, "stop")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    _, _, _, _, model_used = _stream_with_fallback(
        client=None,
        current_model="free-coder-a",
        messages=[],
        available_tools=[],
        user_manually_selected=False,
        candidates=["free-coder-a", "free-coder-b", "free-general-a"],
    )

    assert model_used == "free-general-a"
    assert len(stream.models_called) == len(set(stream.models_called)) == 3


def test_raises_once_every_candidate_is_exhausted(monkeypatch):
    stream = _ScriptedStream([_rate_limit_error(), _rate_limit_error()])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(RateLimitError):
        _stream_with_fallback(
            client=None,
            current_model="free-coder-a",
            messages=[],
            available_tools=[],
            user_manually_selected=False,
            candidates=["free-coder-a", "free-coder-b"],
        )

    assert stream.models_called == ["free-coder-a", "free-coder-b"]


def test_manual_model_selection_bypasses_fallback_entirely(monkeypatch):
    """A user-picked model must fail exactly as it always did — no silent
    downgrade to a free model on their behalf."""
    stream = _ScriptedStream([_rate_limit_error()])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(RateLimitError):
        _stream_with_fallback(
            client=None,
            current_model="paid-premium",
            messages=[],
            available_tools=[],
            user_manually_selected=True,
            candidates=["free-coder-a"],  # must be ignored entirely
        )

    assert stream.models_called == ["paid-premium"]


def test_non_rate_limit_errors_are_not_retried(monkeypatch):
    stream = _ScriptedStream([ConnectionError("network is down")])
    monkeypatch.setattr("termicode.cli._stream_agent_response", stream)

    with pytest.raises(ConnectionError):
        _stream_with_fallback(
            client=None,
            current_model="free-coder-a",
            messages=[],
            available_tools=[],
            user_manually_selected=False,
            candidates=["free-coder-a"],
        )

    assert stream.models_called == ["free-coder-a"]
