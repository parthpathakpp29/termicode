# TermiCode

TermiCode is an interactive terminal-based AI coding assistant built for local development workflows. It helps you inspect a repository, make safe code changes, and run lightweight automation tasks without leaving the terminal.

It uses OpenRouter-backed models, includes guardrails for sensitive files, supports surgical file edits, and offers a set of slash commands for repository exploration, refactoring, and session management.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## ✨ What it does

- Works directly in your terminal with an interactive chat-style interface.
- Reads the current project structure and helps you understand the codebase.
- Performs targeted file edits instead of rewriting whole files.
- Protects sensitive paths such as .env and other guarded files.
- Supports slash commands for mapping the repo, resetting context, generating reports, and triggering refactor workflows.

## 🚀 Installation

### With pipx (recommended)

```bash
pipx install termicode
```

### With pip

```bash
pip install termicode
```

### From source

```bash
git clone https://github.com/parthpathakpp29/termicode.git
cd termicode
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
```

## ⚙️ Configuration

TermiCode requires an OpenRouter API key to start.

1. Create a .env file in the directory where you run the CLI.
2. Add your key:

```env
OPENROUTER_API_KEY=your_api_key_here
```

You can also export the variable in your shell instead of using a .env file.

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
- /heal <file> - Diagnose and refactor a specific file
- /undo <file> - Restore the most recent backup for a file
- /report - Generate a repository health report
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

## 📄 License

This project is licensed under the MIT License. If you want to use it commercially or in your own projects, you can review the terms here:

- https://opensource.org/licenses/MIT

If you want, I can also add a real LICENSE file to the repository so the license is included directly in the project.
