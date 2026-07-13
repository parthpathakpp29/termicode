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

This project is licensed under the MIT License. If you want to use it commercially or in your own projects, you can review the terms here:

- https://opensource.org/licenses/MIT

If you want, I can also add a real LICENSE file to the repository so the license is included directly in the project.
