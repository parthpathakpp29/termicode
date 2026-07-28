# File editing, backups, and the sandbox boundary

This document covers how TermiCode reads, writes, edits, and deletes files, how it decides a path is off-limits, and how backups/`/undo` work. Relevant modules: `file_tools.py` and `path_safety.py`.

## The sandbox boundary (`path_safety.py`)

Every file-touching tool calls `validate_path(requested_path)` before touching disk. It resolves both the requested path and the current working directory with `os.path.realpath` — not `os.path.abspath` — and refuses anything whose real, resolved location falls outside the real, resolved working directory.

The `realpath` distinction matters concretely: `abspath` does not resolve symlinks or Windows junctions. A symlink or junction placed inside the workspace, pointing somewhere outside it, would pass an `abspath`-based containment check while genuinely reading and writing files outside the sandbox — this was confirmed as a real, exploitable gap (using an actual Windows junction, which needs no elevated privilege to create) before the check was switched to `realpath`. `tests/test_path_safety_escape.py` creates a real symlink or junction to verify this rather than mocking the filesystem, since a mock can't reproduce the specific disagreement between `abspath` and `realpath` that caused the original gap.

Separately, `_is_protected(path)` blocks specific files and patterns by name, regardless of location: `.env` and its variants, `secrets.*`, common credential filenames and private-key extensions, and anything with a `.termicode` path component (TermiCode's own session/cache state — see [sessions.md](sessions.md) — which is normally outside the workspace anyway and so already unreachable via `validate_path`; this check only matters if someone runs TermiCode from their home directory itself). This check runs *before* any preview is built for a write/edit/delete — approving a write to a protected file must never even get the chance to render that file's current contents into a preview.

## Reading

`read_file(file_path, start_line=None, end_line=None)` reads the whole file if no range is given, unless it's over 2,500 lines — at that size it refuses and asks for an explicit range instead, rather than dumping something that size into the model's context. A line range, when given, is returned with line numbers prefixed, so the model can reference specific lines back in an `edit_file` call.

## Writing, editing, deleting — and their backups

All three mutating operations create a timestamped `.bak` snapshot before touching the real file:

- **`write_file_approved`** — if the target already exists, its current content is copied to `<path>.<timestamp>.bak` before being overwritten. If it doesn't exist, this is a plain new-file write with no backup (nothing to back up).
- **`edit_file_approved`** — requires an exact, whitespace-and-all match of `search_string` in the file's current content; a mismatch (wrong indentation, wrong line endings, or the string genuinely absent) fails with an error explaining that, rather than silently doing nothing. On a match, the file's current content is backed up, then `search_string` is replaced with `replace_string` — only the **first** occurrence, even if the string appears more than once.
- **`delete_file_approved`** — doesn't delete at all in the filesystem sense; it renames the file to its own `.bak` snapshot. `/undo` (see below) can always recover it.

The timestamp is `time.time_ns()` — nanosecond resolution, not `time.time()`'s second resolution. This matters when auto-approve (see [approval-flow.md](approval-flow.md)) is on: without a human pause between prompts, an edit immediately followed by a delete on the same file can genuinely happen within the same wall-clock second, and a second-resolution timestamp would make the two backups collide on filename — on Windows, `os.rename` raises outright on that collision rather than silently overwriting, as POSIX `rename` would.

## `/undo` and `restore_backup`

`restore_backup(file_path)` globs for `<path>.*.bak`, sorts the matches, and restores the most recent one — deleting the current file first, then renaming the backup into its place. The lexicographic sort is only correct because the timestamp format has constant digit width for any realistic date range (true of both the old second-based and the current nanosecond-based timestamps) — a `tests/test_safety_tools.py` test verifies this explicitly with controlled timestamps rather than assuming it holds.

`/undo <file>` in the CLI is a thin wrapper over this same function.
