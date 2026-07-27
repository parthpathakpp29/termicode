from types import SimpleNamespace

from termicode.cli import (
    CANCELLED_TOOL_RESULT,
    _close_unanswered_tool_calls,
    _stream_agent_response,
)


def _assistant_with_calls(*call_ids):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
            for call_id in call_ids
        ],
    }


def _tool_result(call_id, content="done"):
    return {"role": "tool", "tool_call_id": call_id, "name": "read_file", "content": content}


def _unanswered(messages):
    """Tool call ids with no matching tool message — must always be empty."""
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    return [
        call["id"]
        for m in messages
        if m.get("role") == "assistant" and m.get("tool_calls")
        for call in m["tool_calls"]
        if call["id"] not in answered
    ]


def test_dangling_tool_calls_are_answered():
    messages = [{"role": "user", "content": "go"}, _assistant_with_calls("call_1", "call_2")]

    synthesised = _close_unanswered_tool_calls(messages)

    assert synthesised == 2
    assert _unanswered(messages) == []
    assert messages[-1]["content"] == CANCELLED_TOOL_RESULT


def test_already_answered_calls_are_left_alone():
    messages = [
        {"role": "user", "content": "go"},
        _assistant_with_calls("call_1", "call_2"),
        _tool_result("call_1", "real result"),
    ]

    synthesised = _close_unanswered_tool_calls(messages)

    assert synthesised == 1
    assert _unanswered(messages) == []
    # The real result survives; only the interrupted call is marked cancelled.
    assert messages[2]["content"] == "real result"
    assert messages[3]["tool_call_id"] == "call_2"


def test_a_fully_answered_turn_is_untouched():
    messages = [
        {"role": "user", "content": "go"},
        _assistant_with_calls("call_1"),
        _tool_result("call_1"),
    ]
    before = list(messages)

    assert _close_unanswered_tool_calls(messages) == 0
    assert messages == before


def test_cancelling_before_any_tool_call_is_a_no_op():
    messages = [{"role": "user", "content": "go"}]

    assert _close_unanswered_tool_calls(messages) == 0
    assert messages == [{"role": "user", "content": "go"}]


def test_repair_is_idempotent():
    """A second Ctrl+C during cleanup must not double up results."""
    messages = [{"role": "user", "content": "go"}, _assistant_with_calls("call_1")]

    _close_unanswered_tool_calls(messages)
    second_pass = _close_unanswered_tool_calls(messages)

    assert second_pass == 0
    assert len(messages) == 3


def test_only_the_most_recent_turn_is_repaired():
    """Earlier turns are already complete; repair must not walk the whole history."""
    messages = [
        {"role": "user", "content": "first"},
        _assistant_with_calls("old_1"),
        _tool_result("old_1"),
        {"role": "assistant", "content": "answered"},
        {"role": "user", "content": "second"},
        _assistant_with_calls("new_1"),
    ]

    assert _close_unanswered_tool_calls(messages) == 1
    assert messages[-1]["tool_call_id"] == "new_1"


def test_non_dict_messages_do_not_break_repair():
    messages = [SimpleNamespace(role="assistant", content="sdk object"), _assistant_with_calls("call_1")]

    assert _close_unanswered_tool_calls(messages) == 1


class _SpyLive:
    """Records start/stop ordering so nested Live usage is detectable."""

    events = []

    def __init__(self, *args, **kwargs):
        self.name = "response"

    def start(self, *args, **kwargs):
        _SpyLive.events.append(f"{self.name}:start")

    def stop(self, *args, **kwargs):
        _SpyLive.events.append(f"{self.name}:stop")

    def update(self, *args, **kwargs):
        pass


class _SpySpinner(_SpyLive):
    def __init__(self, *args, **kwargs):
        self.name = "spinner"


def _fake_client(chunks):
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: iter(chunks))
        )
    )


def _chunk(content=None):
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)], usage=None)


def test_spinner_runs_and_stops_before_the_response_panel(monkeypatch):
    _SpyLive.events = []
    monkeypatch.setattr("termicode.cli.print_thinking_spinner", lambda: _SpySpinner())
    monkeypatch.setattr("termicode.cli.Live", _SpyLive)

    _stream_agent_response(_fake_client([_chunk("hello")]), "m", [], [])

    assert _SpyLive.events[0] == "spinner:start"
    # Rich permits one Live at a time: the spinner must stop before the panel.
    assert _SpyLive.events.index("spinner:stop") < _SpyLive.events.index("response:start")


def test_spinner_stops_even_when_the_stream_fails(monkeypatch):
    _SpyLive.events = []
    monkeypatch.setattr("termicode.cli.print_thinking_spinner", lambda: _SpySpinner())

    def exploding_create(**kwargs):
        raise RuntimeError("connection lost")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=exploding_create))
    )

    try:
        _stream_agent_response(client, "m", [], [])
    except RuntimeError:
        pass

    assert _SpyLive.events == ["spinner:start", "spinner:stop"]
