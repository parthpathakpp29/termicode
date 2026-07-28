# Sessions: history, memory, and where things live on disk

TermiCode remembers a conversation across restarts, per project, and keeps a rolling summary of older context once a conversation gets long. This document covers where that state lives, how it's keyed, and how context pruning/summarization works. Relevant module: `session.py`.

## Where state lives, and why it moved

Session state used to be written into the project directory as `.termicode_history.json` and `.termicode_memory.json`. That meant every project accumulated a transcript containing the full contents of every file the agent had read — a real risk if a user didn't think to `.gitignore` it, and (independent of that) something the agent's own sandbox (`path_safety.py`) had to special-case to keep the agent from reading its own history back as a "file in the workspace."

Both problems are solved by moving this state outside the project entirely, to the user's home directory:

```
~/.termicode/sessions/<project>-<id>.history.json
~/.termicode/sessions/<project>-<id>.memory.json
~/.termicode/catalog.json          (see model-routing.md — a separate subsystem, same home directory)
```

`termicode_home()` resolves this root (honoring `$TERMICODE_HOME` if set, creating the directory if needed, degrading — not crashing — if the home directory turns out to be unusable). `session_dir()` is `termicode_home() / "sessions"`. Both the session-storage subsystem and the model catalog cache share this one resolution function rather than each re-implementing it, so they can't drift apart on how `$TERMICODE_HOME` is honored.

Because this now lives outside the workspace, `path_safety.validate_path`'s ordinary containment check already keeps the agent from reading it — no special-casing needed there anymore. (`path_safety._is_protected` still additionally refuses any path containing a `.termicode` component, which only matters if someone runs TermiCode from their home directory itself, making `~/.termicode` technically part of the workspace.)

**Migration:** on startup, `migrate_legacy_session()` checks for the old in-project files and moves them to the new location if found — but only if nothing already exists at the destination. If both exist, the newer one wins and the legacy file is left in place rather than deleted; an ambiguity here is not a reason to discard data.

## Keying: how a project maps to a file

`_project_key()` builds `<sanitized-basename>-<8 hex chars>`, where the hex suffix is a truncated SHA-256 hash of the project's absolute path (case-normalized, so a drive-letter case difference on Windows doesn't fork the session). The readable prefix makes the file identifiable at a glance; the hash suffix means two different projects both named `api` don't collide.

## What gets pruned, and what gets summarized

Two separate mechanisms operate at different points, both in `session.py`:

- **`prune_context(messages, max_turns=25)`** runs on every turn before sending the request. If the message list is longer than `max_turns`, it drops *complete* user/assistant exchanges from the middle (keeping the system prompt and the most recent messages), skipping anything that would split a tool call from its result — never removes a `tool` message on its own, since an orphaned one would make the next request invalid. This trims what's sent to the model on this specific request; it does not delete anything from the persisted history.
- **`update_memory_summary(client, old_summary, messages_to_drop)`**, triggered from `cli.py` when the in-memory message list exceeds 25 entries, asks a fast model to fold the messages being permanently dropped into a running summary, which is what gets woven back into the system prompt on the next turn (and persisted separately as the "memory" file). If the summarization call fails for any reason, the old summary is kept rather than losing it — the failure is silent by design, not by accident: a summarization hiccup shouldn't interrupt the user's actual turn.

## When state is saved

`save_session` (history + memory together) is called after every completed turn, when a `Ctrl+C` interrupt is repaired and the session paused, and on `/exit`/`/reset`/an unhandled top-level exception — not only on a clean shutdown. `/reset` deletes both files for the current project and starts a fresh in-memory conversation; it does not touch other projects' session files.
