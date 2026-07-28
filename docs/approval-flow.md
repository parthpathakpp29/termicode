# Approval flow

Every file mutation the model requests is shown to the user before it happens, and every `run_command` call is confirmed every time, with no exception. This document covers how previews are built, how the `y/N/a` prompt and session-scoped auto-approve work, and why `run_command` is deliberately excluded from auto-approve. Relevant modules: `diff.py` (preview construction), `tool_executor.py` (the approval gate), `ui.py` (rendering).

## Ordering: protected-path check before anything else

For `write_file`, `edit_file`, and `delete_file`, `tool_executor.execute_tool` checks `path_safety._is_protected(file_path)` **before** building any preview or showing any prompt. This ordering is deliberate, not incidental: if a preview were built first, approving a write to a protected file like `.env` would render that file's *current* contents into the preview panel — turning the guardrail into a disclosure path. `diff.py`'s own preview-building functions additionally refuse protected paths themselves (returning `PROTECTED_NOTICE` without reading the file), so the refusal doesn't depend on `tool_executor.py` remembering to check first — either layer alone is sufficient.

## Building the preview (`diff.py`)

`build_write_preview`, `build_edit_preview`, and `build_delete_preview` each return plain, pre-rendered text — never raising, never touching the terminal directly (rendering is `ui.py`'s job, not theirs):

- **Write** — a unified diff against the current content if the file exists, or the new file's content (capped, with a line count) if it doesn't.
- **Edit** — a unified diff of the proposed `search_string` → `replace_string` replacement. If the search text isn't present, the preview says the edit will fail rather than showing a diff at all — this surfaces a failure *before* approval instead of after. If the search text matches more than once, the preview notes that only the first occurrence will be replaced.
- **Delete** — the line count and full content, since deletion moves the file to a backup rather than reading it back afterward.

All three cap long output at 80 lines with a "N more lines not shown" footer, and degrade to a plain notice (rather than raising) for a binary/non-UTF-8 file or a path that fails `path_safety.validate_path`.

## The prompt: `y` / `N` / `a`

`ui.print_security_alert(action, file_path, preview)` renders the action and the preview, then prompts. The prompt has three outcomes, not two:

- **`y`** — approve this one action.
- **`n`** (or anything else, including just pressing enter) — decline this one action.
- **`a`** (or `all`/`always`) — approve this action *and* turn on auto-approve for the rest of the session, matching the `git add -p` convention. Every later write/edit/delete shows the same preview, badged `(auto-approved)`, without blocking for input — approving in advance is not the same as approving blind, so the preview still renders even once nothing is left to confirm.

`tool_executor.ApprovalState` holds this as a session-scoped flag — a small object rather than a bare module-level variable, so there's one named place to reset from in tests and reason about (TermiCode is a single interactive session, not a server, so this isn't a general session/config framework, just a home for one flag). It is **not persisted across restarts**: carrying "approve everything" silently into a session the user doesn't remember granting it in would be a bigger risk than being asked again next time. `/approve` (status), `/approve on`, and `/approve off` are the explicit, always-available way to check or change this outside of answering a live prompt.

## Why `run_command` is never auto-approved

`ApprovalState` deliberately does not cover `run_command`. A diff preview can show, in advance, exactly what a file write or edit will do. There is no equivalent way to show in advance what an arbitrary shell command will do — it could touch the network, delete something outside the sandbox, or have any other side effect a text preview can't capture. `run_command` uses a separate prompt function, `ui.print_command_alert`, which is a plain always-blocking `y`/`N` — there is no `a` option for it, and no flag that would let a future change accidentally introduce one without deliberately touching this file.

## The command-level gate (`/guard`)

Separately from per-call approval, `/guard on` installs a git pre-commit hook (via the standalone `termicode-guard-check` process — see [tool-system.md](tool-system.md#guard_check-a-separate-process)) that can block a commit outright if a staged file's live Repowise health score falls below a threshold. This is a different kind of gate — repo-level and commit-time, not per-tool-call — and requires Repowise; see the README's "Optional: Repowise" section for what it needs and how it degrades when Repowise isn't installed.
