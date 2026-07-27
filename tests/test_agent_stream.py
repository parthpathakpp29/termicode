from types import SimpleNamespace

from termicode.cli import MAX_COMPLETION_TOKENS, _has_complete_arguments, _stream_agent_response


def _delta(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _chunk(delta=None, finish_reason=None, usage=None, choices=None):
    """Build a stream chunk. Pass choices=[] for a usage-only trailer."""
    if choices is None:
        choices = [SimpleNamespace(delta=delta or _delta(), finish_reason=finish_reason)]
    return SimpleNamespace(choices=choices, usage=usage)


def _tool_delta(call_id=None, name=None, arguments=None, index=0):
    """index defaults to 0: every real provider tags each tool-call delta
    with its parallel-call index, present on every chunk including
    continuations that omit id/name."""
    function = SimpleNamespace(name=name, arguments=arguments)
    return [SimpleNamespace(index=index, id=call_id, function=function)]


class FakeClient:
    """Minimal stand-in for the OpenAI client that replays fixed chunks."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.chunks)


def _run(chunks):
    client = FakeClient(chunks)
    result = _stream_agent_response(client, "test/model", [], [])
    return client, result


def test_content_and_usage_accumulate_across_chunks():
    _, (content, tool_calls, tokens, finish_reason) = _run([
        _chunk(_delta(content="Hello ")),
        _chunk(_delta(content="world")),
        _chunk(usage=SimpleNamespace(total_tokens=42), choices=[]),
    ])

    assert content == "Hello world"
    assert tool_calls == {}
    assert tokens == 42
    assert finish_reason is None


def test_usage_only_trailer_does_not_discard_the_response():
    """A chunk with no choices must be skipped, not raise IndexError."""
    _, (content, _, tokens, _) = _run([
        _chunk(_delta(content="kept")),
        _chunk(usage=SimpleNamespace(total_tokens=7), choices=[]),
    ])

    assert content == "kept"
    assert tokens == 7


def test_tool_call_arguments_accumulate_across_deltas():
    _, (_, tool_calls, _, _) = _run([
        _chunk(_delta(tool_calls=_tool_delta(call_id="call_1", name="read_file"))),
        _chunk(_delta(tool_calls=_tool_delta(arguments='{"file_path":'))),
        _chunk(_delta(tool_calls=_tool_delta(arguments='"cli.py"}'))),
        _chunk(finish_reason="tool_calls"),
    ])

    assert list(tool_calls) == ["call_1"]
    assert tool_calls["call_1"]["name"] == "read_file"
    assert tool_calls["call_1"]["arguments"] == '{"file_path":"cli.py"}'


def test_finish_reason_length_is_reported():
    _, (_, _, _, finish_reason) = _run([
        _chunk(_delta(content="cut off here")),
        _chunk(finish_reason="length"),
    ])

    assert finish_reason == "length"


def test_finish_reason_stop_is_reported():
    _, (_, _, _, finish_reason) = _run([_chunk(_delta(content="done"), finish_reason="stop")])

    assert finish_reason == "stop"


def test_request_uses_the_configured_completion_ceiling():
    client, _ = _run([_chunk(_delta(content="ok"))])

    assert client.calls[0]["max_tokens"] == MAX_COMPLETION_TOKENS
    assert MAX_COMPLETION_TOKENS >= 4096
    assert client.calls[0]["stream"] is True


def test_incomplete_arguments_are_detected_as_truncated():
    cut_off = {"function": {"name": "write_file", "arguments": '{"file_path": "a.py", "content": "def f('}}

    assert _has_complete_arguments(cut_off) is False


def test_complete_arguments_are_not_treated_as_truncated():
    """A turn can stop on the limit with its last call intact; don't reject it."""
    complete = {"function": {"name": "read_file", "arguments": '{"file_path": "a.py"}'}}
    no_args = {"function": {"name": "get_overview", "arguments": ""}}

    assert _has_complete_arguments(complete) is True
    assert _has_complete_arguments(no_args) is True
