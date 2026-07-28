# Contributing to TermiCode

TermiCode is a small, community-driven project. You do not need to be an expert to contribute — fixing a small bug, improving an error message, or adding a test for something untested are all genuinely useful contributions.

## Setup

```bash
git clone https://github.com/parthpathakpp29/termicode.git
cd termicode
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
```

`pip install -e .[dev]` installs TermiCode itself in editable mode plus `pytest`, `black`, and `flake8`. You do not need an OpenRouter API key to run the test suite — you only need one to actually run `termicode` interactively (see the [README](README.md#configuration)).

Repowise (the optional engine behind `/heal`, `/report`, and `/guard`) is a separate install (`pip install repowise`) and is not required for development. Tests that depend on it skip or fall back gracefully when it is absent — see [docs/tool-system.md](docs/tool-system.md) for how the codebase detects and gates on it.

## Running the tests

```bash
pytest
```

A few things worth knowing about the test suite:

- `tests/conftest.py` redirects the process's temp directory to `<repo>/.tmp` for the whole run, and adds the repo root to `sys.path`. You do not need to configure anything for this — it happens automatically when pytest collects the suite.
- Most tests are pure unit tests against a single module, using `tmp_path` and `monkeypatch` — there's no shared test database or fixture server to stand up.
- A handful of tests exercise real OS-level behavior deliberately rather than mocking it — for example, `tests/test_path_safety_escape.py` creates an actual symlink or Windows junction to verify the sandbox boundary, and skips cleanly if the environment can't create one. If you're adding a test for something security- or filesystem-boundary-related, prefer this style over mocking the OS call: a mock can't catch the exact class of bug a real symlink/junction can.
- There is currently no CI running these automatically on push or PR — running `pytest` yourself before opening a PR is the only gate today. Adding CI is a welcome contribution in its own right.

## Code style

`black` and `flake8` are available as dev dependencies but neither has a project config file today, and nothing enforces them automatically. In practice: match the style of the surrounding file. A few conventions the existing code follows consistently, worth keeping:

- No comments explaining *what* code does (names should already make that clear). Comments are used for the non-obvious *why* — a workaround, a constraint discovered the hard way, a decision that would otherwise look arbitrary.
- Functions that touch the filesystem return a result string (`"Success: ..."` / `"Error: ..."`) rather than raising, since their results are read directly by the model as tool output. Exceptions are reserved for genuine programming errors, not expected failure modes (a missing file, a rate limit, a malformed argument).
- New modules get a short module-level docstring explaining their role, matching the style in `catalog.py`, `session.py`, and `tool_executor.py`.

## Making a change

- **Small, focused change** (bug fix, a new test, a doc improvement, a small quality-of-life fix): just open a pull request. No need to open an issue first.
- **Anything larger** (a new tool, a new slash command, a change to how sessions/routing/approval work): please open an issue describing what you want to do before writing the code. This isn't a formality — it saves you from writing something that gets rearchitected in review, and it's the fastest way to find out if someone's already working on the same thing.

A good PR:
1. Does one thing. If you notice something unrelated while working (dead code, a stale comment, a missing test), mention it in the PR description or a follow-up issue rather than folding it into the same diff.
2. Includes or updates tests for the behavior it changes. See [ARCHITECTURE.md](ARCHITECTURE.md#tests) for how the test suite is organized by module.
3. Explains *why*, not just *what* — the diff already shows what changed; the description should say why it was needed.

## Where to start

If you're not sure what to work on:

- **Adding a new tool** is a well-scoped first contribution with a documented pattern to follow — see [docs/tool-system.md](docs/tool-system.md).
- **Adding a new slash command** follows the existing `if cmd == "/x"` branches in `cli.py`'s main loop — look at `/approve` or `/guard` for the shape of a simple one.
- Beginner-friendly ideas: improve an error message, add a test for a function that doesn't have one yet, improve a section of the README or `docs/`, or work through an open issue tagged for newcomers.

If none of that fits what you want to do, open an issue and describe it — happy to help scope it.

## Reporting a bug

Open a [GitHub issue](https://github.com/parthpathakpp29/termicode/issues). Include:
- What you ran (the command or slash command) and what you expected.
- What actually happened — the real output, not a paraphrase.
- Your OS and Python version. TermiCode's file-safety code (`path_safety.py`) and the git hook it can install (`/guard`) both have OS-specific branches (POSIX permission bits, Windows junction/symlink resolution), so the platform often matters.

## License

By contributing, you agree your contribution is licensed under the project's [MIT License](LICENSE).
