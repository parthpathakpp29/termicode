# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-07-29

### Added

- Diff previews shown before approving any file write, edit, or delete, instead of approving by file path alone.
- Session-scoped auto-approve (`y`/`N`/`a` at the prompt, plus `/approve on|off`) for file writes/edits/deletes. `run_command` is never covered by this — it always prompts.
- Automatic fallback to a different free-tier model when the current one hits a rate limit (429), instead of ending the turn.
- A live, fetched, and locally cached OpenRouter model catalog (`~/.termicode/catalog.json`, refreshed every 6 hours by default), replacing a hardcoded model table. `/model auto`, `/model budget`, and `/model <name>` now select from real, current models and real, current pricing.
- `LICENSE` (MIT).
- CI: the test suite now runs automatically on every push and pull request, across Python 3.9-3.12 and Ubuntu/Windows/macOS.
- `ARCHITECTURE.md`, `CONTRIBUTING.md`, and a `docs/` folder covering model routing, the tool system, sessions, file editing, and the approval flow.
- `.gitattributes` normalizing line endings across contributors' platforms.

### Changed

- Repowise (the engine behind `/heal`, `/report`, and `/guard`) is now an optional dependency. TermiCode runs fully without it installed.
- Session history and the rolling memory summary now live under `~/.termicode/` instead of inside the project directory.
- `run_command`'s timeout raised from a fixed 30 seconds to a named, configurable 180 seconds.
- The per-turn output token ceiling was raised, and a truncated response is now detected and surfaced to the model and the user instead of failing silently with a misleading error.
- `Ctrl+C` now cancels the in-progress turn and returns to the prompt, instead of always ending the whole session; a second consecutive press at an idle prompt is what actually exits.
- Model routing and `/stats` cost reporting now read pricing from the live catalog above, instead of a hardcoded table.

### Fixed

- `/guard`'s pre-commit hook was broken in four independent ways: it invoked a file that was never packaged, a subprocess call crashed on non-UTF-8 console encodings, its own status output crashed on non-UTF-8 consoles, and its detection logic blocked every commit unconditionally regardless of actual code health. All four are fixed; the hook now fails open (allows the commit) if Repowise is unavailable or errors.
- A sandbox-escape vulnerability: the file-access boundary used `abspath`, which does not resolve symlinks or Windows junctions, allowing a link inside the workspace to point outside it. Switched to `realpath` on both sides of the containment check.
- A backup-filename collision: two backup-creating file operations on the same file within the same wall-clock second could collide on filename (and raise outright on Windows, rather than silently overwriting as on POSIX). Backup names now use nanosecond-resolution timestamps.
- Streamed parallel tool calls could be corrupted: continuation chunks were tracked by "whichever id was seen most recently" instead of by index, which silently misattributed argument fragments once two tool calls genuinely interleaved in one response.
- A paid model could be silently used while its cost was reported as `$0`, because the previous hardcoded model table mislabeled it as free. Now impossible by construction: cost is always read from the live catalog above, and an unrecognized model never reports `$0`.

## [0.1.3] and earlier

Predates this changelog. See `git log` for history.
