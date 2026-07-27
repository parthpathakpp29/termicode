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

Set TERMICODE_HOME to keep them somewhere else. Use /reset to erase the session for the current project.

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
- /heal <file> - Diagnose and refactor a specific file (requires Repowise)
- /undo <file> - Restore the most recent backup for a file
- /report - Generate a repository health report (requires Repowise)
- /guard on|off - Toggle the Git pre-commit interceptor (requires Repowise)
- /approve on|off - Auto-approve file writes/edits/deletes for this session (run_command always prompts)
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

## 🤝 Contributing

TermiCode is designed to be a community-driven project, and we welcome contributions from students and beginner developers.

You do not need to be an expert to help. Good ways to start include:

- fixing a small bug
- improving the CLI experience
- adding tests for an existing feature
- improving documentation and setup instructions
- adding a new slash command or small feature
- helping with onboarding examples

If you want to contribute:

1. Fork the repository
2. Create a new branch for your change
3. Make a small, focused update
4. Run the tests
5. Open a pull request with a clear explanation

Beginner-friendly ideas:

- improve error messages
- add a new example workflow
- write documentation for a feature
- suggest or implement a small quality-of-life improvement

If you are unsure where to start, open an issue and say you would like to help. We will be happy to guide you.

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
