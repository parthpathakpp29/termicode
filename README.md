# TermiCode

TermiCode is a terminal-based AI coding assistant built for students, hackathon teams, and open-source contributors who want to work faster without leaving the command line.

It helps you inspect a repository, make safe code changes, and run lightweight automation tasks directly from your terminal. It uses OpenRouter-backed models, includes guardrails for sensitive files, supports surgical file edits, and offers slash commands for repository exploration, refactoring, and session management.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## ✨ Why students and contributors use it

- Works directly in the terminal, which is ideal for developers already living in the command line.
- Helps you understand unfamiliar codebases quickly during assignments, internships, or hackathons.
- Makes small, focused code changes without rewriting entire files.
- Protects sensitive paths such as .env and other guarded files.
- Supports slash commands for mapping the repo, resetting context, generating reports, and triggering refactor workflows.

## 🎯 Who it is for

- College students working on coding assignments and personal projects
- Hackathon teams who want a fast CLI-based assistant
- Open-source contributors who want a lightweight tool for repository exploration
- Developers who prefer terminal-first workflows over heavy IDE integrations

## 📚 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - module map, the lifecycle of a single turn, and known constraints
- [CONTRIBUTING.md](CONTRIBUTING.md) - setup, development workflow, testing, and how to propose a change
- [docs/model-routing.md](docs/model-routing.md) - the live model catalog, free/budget/premium tiers, and rate-limit fallback
- [docs/tool-system.md](docs/tool-system.md) - how a tool call goes from the model to a Python function and back, and how to add a tool
- [docs/sessions.md](docs/sessions.md) - where conversation history and memory live on disk, and how context pruning works
- [docs/file-editing.md](docs/file-editing.md) - the sandbox boundary, backups, and `/undo`
- [docs/approval-flow.md](docs/approval-flow.md) - the diff-preview and `y/N/a` approval prompt, and why `run_command` never auto-approves

## 🚀 Installation

TermiCode is not yet published on PyPI, so install it from source:

```bash
git clone https://github.com/parthpathakpp29/termicode.git
cd termicode
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
```

Once a release is published, it will also be installable with:

```bash
pipx install termicode
# or
pip install termicode
```

## ⚙️ Configuration

TermiCode requires an OpenRouter API key to start.

1. Create a .env file in the directory where you run the CLI.
2. Add your key:

```env
OPENROUTER_API_KEY=your_api_key_here
```

You can also export the variable in your shell instead of using a .env file.

### Where your session is stored

TermiCode remembers your conversation between runs, per project. That history includes the contents of every file it read, so it is kept outside your repository:

```
~/.termicode/sessions/<project>-<id>.history.json
~/.termicode/sessions/<project>-<id>.memory.json
```

Earlier versions wrote these into the project folder as .termicode_history.json and .termicode_memory.json. If you have those, TermiCode moves them to the new location on first run and tells you where they went.

Set TERMICODE_HOME to keep them somewhere else. Use /reset to erase the session for the current project. See [docs/sessions.md](docs/sessions.md) for how this is keyed and how context pruning/summarization works.

### Model selection

TermiCode fetches the live OpenRouter model list rather than picking from a hardcoded set, so it stays correct as models are added, repriced, or retired. The catalog is cached under ~/.termicode/catalog.json and refreshed automatically after 6 hours (set TERMICODE_CATALOG_TTL_SECONDS to change that). See [docs/model-routing.md](docs/model-routing.md) for how models are scored and how the fallback chain works.

- By default, TermiCode auto-routes to the best-ranked free model that supports tool calling. Run /model auto to return to this after picking a specific model.
- /model budget switches to the cheapest available paid model that still supports tool calling - useful when the free tier is rate-limited and a few cents is an acceptable tradeoff.
- /model <name> pins to any specific model on OpenRouter by id, free or paid, and disables auto-routing until you run /model auto again.
- /model with no arguments shows what is currently selected.
- /stats shows real token usage and cost, priced from the live catalog, for whichever model you are using.

If OpenRouter's free tier is rate-limiting you often, a one-time $10 credit purchase (it never expires) raises the free-tier daily request limit from 50 to 1,000 - see openrouter.ai for details.

### Optional: Repowise

[Repowise](https://github.com/repowise-dev/repowise) is a codebase intelligence engine that scores files for defect risk and maintainability. TermiCode uses it to power three commands:

- /heal - diagnose and refactor a file using its health report
- /report - generate a repository health report
- /guard - block commits that touch low-scoring files

**TermiCode works fully without it.** When Repowise is missing, those three commands explain how to enable themselves and everything else runs normally.

To enable them:

```bash
pip install repowise
```

Then run /doctor to re-check - you do not need to restart TermiCode.

Note that Repowise is licensed under AGPL-3.0, separately from TermiCode's MIT license, and brings a substantial dependency tree of its own. That is why it is an opt-in extra rather than a required dependency.

## 💻 Usage

Run the CLI from any project directory:

```bash
termicode
```

Once it starts, you can use commands such as:

- /help - Show available commands
- /map - Print the current project structure
- /clear - Clear the terminal screen
- /reset - Reset the current session context
- /doctor - Check your local setup and dependencies
- /model - Show the current model, or /model auto|budget|<name> to pick one (see "Model selection" below)
- /heal <file> - Diagnose and refactor a specific file (requires Repowise)
- /undo <file> - Restore the most recent backup for a file
- /report - Generate a repository health report (requires Repowise)
- /guard on|off - Toggle the Git pre-commit interceptor (requires Repowise)
- /approve on|off - Auto-approve file writes/edits/deletes for this session (run_command always prompts, see [docs/approval-flow.md](docs/approval-flow.md))
- /ripple <prompt> - Apply a multi-file architecture change
- /exit - Save the session and quit

Example prompts:

- Refactor a slow or brittle function in a Python module.
- Search the repository for a symbol or configuration value.
- Run the test suite and fix any failing tests.

## 🧪 Development

To run the test suite locally:

```bash
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions, what the test suite expects, and code style notes.

## 🤝 Contributing

TermiCode is designed to be a community-driven project, and we welcome contributions from students and beginner developers - you do not need to be an expert to help. Fixing a small bug, adding a test, or improving documentation are all genuinely useful.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup, the development workflow, PR guidelines, and where to start if you're not sure what to work on. If you want to understand how the pieces fit together before making a change, start with **[ARCHITECTURE.md](ARCHITECTURE.md)**.

If you are unsure where to start, open an issue and say you would like to help. We will be happy to guide you.

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
