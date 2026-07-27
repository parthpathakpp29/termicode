from termicode.cli import _stream_agent_response

from test_agent_stream import FakeClient, _chunk, _delta, _tool_delta


def test_two_interleaved_parallel_tool_calls_do_not_corrupt_each_other():
    """Reproduces a confirmed real bug: tracking continuation chunks by
    "whichever id was seen most recently" instead of by index. Two parallel
    tool calls whose argument fragments genuinely interleave -- call 0's id
    arrives, a fragment, then call 1's id arrives, a fragment, then a further
    fragment for call 0 (carrying only its index, as every real provider
    sends continuations) -- used to land that last fragment on call 1 instead,
    corrupting both into invalid JSON.
    """
    chunks = [
        _chunk(_delta(tool_calls=_tool_delta(index=0, call_id="call_A", name="read_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments='{"a": '))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, call_id="call_B", name="edit_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, arguments='{"b": '))),
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments="1}"))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, arguments="2}"))),
        _chunk(finish_reason="tool_calls"),
    ]

    _, tool_calls, _, _ = _stream_agent_response(FakeClient(chunks), "m", [], [])

    assert tool_calls["call_A"]["name"] == "read_file"
    assert tool_calls["call_A"]["arguments"] == '{"a": 1}'
    assert tool_calls["call_B"]["name"] == "edit_file"
    assert tool_calls["call_B"]["arguments"] == '{"b": 2}'


def test_three_parallel_tool_calls_interleaved_out_of_order():
    chunks = [
        _chunk(_delta(tool_calls=_tool_delta(index=0, call_id="call_A", name="read_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, call_id="call_B", name="edit_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=2, call_id="call_C", name="delete_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=2, arguments='{"c":1}'))),
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments='{"a":1}'))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, arguments='{"b":1}'))),
        _chunk(finish_reason="tool_calls"),
    ]

    _, tool_calls, _, _ = _stream_agent_response(FakeClient(chunks), "m", [], [])

    assert tool_calls["call_A"]["arguments"] == '{"a":1}'
    assert tool_calls["call_B"]["arguments"] == '{"b":1}'
    assert tool_calls["call_C"]["arguments"] == '{"c":1}'


def test_a_single_tool_call_still_accumulates_correctly():
    """The common case (one tool call, no interleaving) must be unaffected."""
    chunks = [
        _chunk(_delta(tool_calls=_tool_delta(index=0, call_id="call_1", name="read_file"))),
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments='{"file_path":'))),
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments='"cli.py"}'))),
        _chunk(finish_reason="tool_calls"),
    ]

    _, tool_calls, _, _ = _stream_agent_response(FakeClient(chunks), "m", [], [])

    assert list(tool_calls) == ["call_1"]
    assert tool_calls["call_1"]["arguments"] == '{"file_path":"cli.py"}'


def test_a_tool_call_whose_id_never_arrives_is_dropped_not_crashed():
    """Defensive: if a continuation-only fragment showed up for an index that
    never got an id (should not happen per protocol, but must not corrupt
    another call's entry or raise)."""
    chunks = [
        _chunk(_delta(tool_calls=_tool_delta(index=0, arguments="orphaned"))),
        _chunk(_delta(tool_calls=_tool_delta(index=1, call_id="call_1", name="read_file", arguments="{}"))),
        _chunk(finish_reason="tool_calls"),
    ]

    _, tool_calls, _, _ = _stream_agent_response(FakeClient(chunks), "m", [], [])

    assert list(tool_calls) == ["call_1"]
    assert tool_calls["call_1"]["arguments"] == "{}"
