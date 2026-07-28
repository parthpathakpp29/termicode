# The tool system

TermiCode's model interacts with the outside world entirely through OpenAI-compatible function/tool calling. This document covers how a tool call gets from the model's streamed response to a Python function and back, and exactly what's involved in adding a new tool.

## The three places a tool exists

Every tool currently has to exist in three places, kept in sync by hand:

1. **The schema**, in `prompts.py`'s `get_available_tools()` — the JSON-schema-shaped description the model sees, including its name, description, and parameters.
2. **The dispatch branch**, in `tool_executor.py`'s `execute_tool()` — an explicit `if name == "..."` / `elif` chain that calls the real Python function and returns its result as a string.
3. **The implementation**, usually in `file_tools.py`, `command_tools.py`, `search_tools.py`, or `health_tools.py`, re-exported through `tools.py`'s flat facade.

There is no tool-registration mechanism or plugin system today — adding a tool means editing (1) and (2) directly, and either adding to (3) or reusing an existing function. If you're looking for a well-scoped first contribution, adding a tool that follows this existing pattern is a reasonable one; see "Adding a tool," below.

## How a streamed tool call is reconstructed

The model streams its response in small chunks, and a tool call can arrive split across many of them — this is true even for a single tool call, and it's the only path when the model issues more than one tool call in the same turn (parallel tool calls).

The OpenAI-compatible streaming contract works like this: the **first** chunk for a given tool call carries its `id`, its function `name`, and an `index` (which parallel call this is, `0`, `1`, `2`, ...). **Every later chunk** for that same call carries only its `index` and a fragment of `arguments` — `id` and `name` come back as `None`.

`cli.py`'s `_stream_agent_response` accumulates these **keyed by `index`**, into a dict of `{index: {"id": ..., "name": ..., "arguments": ...}}`, appending each fragment's `arguments` onto the existing string. Only once streaming finishes does it convert that to the `{id: {...}}` shape the rest of the code expects.

This matters more than it might look: an earlier version of this code tracked "whichever `id` was seen most recently" instead of `index`. That works for a single tool call, but breaks the moment two tool calls genuinely interleave — a continuation fragment for the first call, arriving after the second call's `id` has been seen, would get appended to the *second* call's arguments instead of the first's, corrupting both into invalid JSON. If you're touching this accumulation logic, `tests/test_parallel_tool_calls.py` has a regression test built from the exact interleaved-chunk scenario that reproduced this.

## Executing a tool call

Once a full `{name, arguments}` pair is assembled, `tool_executor.execute_tool` does the actual work:

1. Parses `arguments` as JSON. A parse failure returns an error string to the model rather than raising — the model can see and recover from "Invalid JSON arguments," but the process shouldn't crash over it.
2. Dispatches on `name` to the matching branch.
3. For the file-mutating tools (`write_file`, `edit_file`, `delete_file`), checks `path_safety._is_protected` first and refuses outright if the path is protected — before anything else runs, including building a preview. See [approval-flow.md](approval-flow.md) for why the ordering here matters.
4. For everything else requiring confirmation (approved file mutations, `run_command`), shows a preview/prompt and only proceeds on approval.
5. Returns the result as a plain string, which becomes the `content` of a `tool` role message sent back to the model.

Tool functions themselves (in `file_tools.py` etc.) follow a consistent convention: they return a `"Success: ..."` or `"Error: ..."` string rather than raising, because their return value is read directly by the model. Exceptions are reserved for genuine bugs, not expected failure modes.

## Adding a tool

1. Add the implementation function wherever it fits best (`file_tools.py` for filesystem operations, `search_tools.py` for search/lookup, or a new module if it's a new category entirely), and re-export it from `tools.py` if it lives in a new file.
2. Add its schema to `get_available_tools()` in `prompts.py`. If it should only be offered when Repowise is installed, add it inside the `if repowise_available:` block, matching `get_overview`/`get_context`/`get_health`.
3. Add a dispatch branch in `tool_executor.execute_tool()`, following the shape of the existing branches — call the function, return its result string. If it mutates a file, follow the `_is_protected` check → preview → `_confirm()` pattern the existing file tools use (see [approval-flow.md](approval-flow.md)).
4. Add tests. `tests/test_safety_tools.py` and `tests/test_diff_preview.py` are reasonable models to follow depending on whether the new tool touches files.
5. If the tool should show up in `/tools`, it will automatically — that list is built directly from `get_available_tools()`.

## `guard_check`: a separate process

`termicode/guard_check.py` is not part of the interactive TermiCode session at all. It's installed as its own console script entry point (`termicode-guard-check`, in `pyproject.toml`) and is what `/guard on` writes into `.git/hooks/pre-commit`. Git invokes it directly as a subprocess on every commit — it shares the `termicode` package's code (it imports `termicode.repowise` to check availability) but shares no in-memory state with a running TermiCode REPL. It's designed to fail open: if Repowise is missing or errors, the commit is allowed rather than blocked, since a broken dependency should never be able to make every future commit impossible.
