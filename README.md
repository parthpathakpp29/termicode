# TermiCode

> **Open-source terminal AI coding assistant with secure file editing, repository intelligence, approval prompts, and OpenRouter-powered model routing.**

TermiCode helps developers understand, modify, and maintain codebases without leaving the terminal. It combines AI-assisted coding with built-in safety features like diff previews, approval prompts, protected file guardrails, session memory, and intelligent model routing.

Unlike traditional AI coding assistants, TermiCode prioritizes **transparent and controlled code editing**. Every change can be reviewed before it touches your files, making it suitable for real development work.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/termicode-ai)](https://pypi.org/project/termicode-ai/)

---

# ✨ Features

* 🤖 OpenRouter-powered AI coding assistant
* 🔒 Secure file editing with approval prompts
* 📝 Unified diff preview before every file modification
* 📂 Repository exploration and code search
* 🧠 Persistent project memory across sessions
* 🔄 Automatic model fallback during rate limits
* 💰 Live model pricing and token usage tracking
* 🛡️ Protected file guardrails (`.env`, secrets, session files)
* ⚡ Terminal-first workflow
* 🔌 Optional Repowise integration for repository health analysis

---

# 🚀 Installation

Install from PyPI:

```bash
pipx install termicode-ai

# or

pip install termicode-ai
```

Launch TermiCode:

```bash
termicode
```

---

# ⚡ Quick Start

Create an OpenRouter API key:

https://openrouter.ai

Then configure your environment:

```bash
export OPENROUTER_API_KEY=your_api_key
```

Windows PowerShell:

```powershell
$env:OPENROUTER_API_KEY="your_api_key"
```

Start the assistant:

```bash
termicode
```

Example prompts:

```text
Explain this repository.

Refactor authentication.py.

Find where JWT tokens are verified.

Run the test suite and fix failing tests.

Generate a repository health report.

Improve the architecture of this module.
```

---

# 💻 Example Workflow

```bash
$ termicode

> Explain this repository

✓ Generated architecture summary.

> Refactor utils.py

✓ Diff preview generated.
✓ Waiting for approval...

Approve? (y/N/a)

> y

✓ File updated successfully.

> Run the test suite and fix failures

✓ Tests executed.
✓ Proposed fixes generated.
```

---

# 🎯 Who It's For

TermiCode is designed for developers who prefer working from the command line, including:

* Students learning large codebases
* Hackathon teams shipping quickly
* Open-source contributors
* Backend engineers
* Python developers
* CLI enthusiasts
* AI-assisted development workflows

---

# 🛡️ Safety First

Unlike many coding assistants, TermiCode is designed around explicit user control.

It includes:

* File protection for sensitive paths
* Approval prompts before file modifications
* Diff previews before writes
* Protected session storage
* Sandboxed file access
* Safe undo support
* Command approval controls

---

# 🧠 Intelligent Model Routing

TermiCode dynamically fetches the latest available models from OpenRouter instead of relying on a hardcoded model list.

Features include:

* Automatic best free model selection
* Budget mode for inexpensive paid models
* Manual model selection
* Live pricing information
* Automatic fallback when a model becomes rate-limited

Useful commands:

```text
/model auto
/model budget
/model <model-name>
/stats
```

---

# 📂 Session Memory

Every project gets its own persistent conversation history.

Sessions are stored outside your repository:

```text
~/.termicode/sessions/<project>-<id>.history.json
~/.termicode/sessions/<project>-<id>.memory.json
```

You can relocate them using:

```bash
TERMICODE_HOME
```

Useful command:

```text
/reset
```

---

# 🔌 Optional Repowise Integration

Repowise adds repository intelligence capabilities including:

* Repository health reports
* AI-assisted refactoring
* Commit protection
* Code health analysis

Install:

```bash
pip install repowise
```

Then verify:

```text
/doctor
```

Core TermiCode functionality works without Repowise.

---

# 📖 Commands

| Command            | Description                           |
| ------------------ | ------------------------------------- |
| `/help`            | Show available commands               |
| `/map`             | Display project structure             |
| `/doctor`          | Check local environment               |
| `/model`           | Manage AI model selection             |
| `/stats`           | Show token usage and cost             |
| `/heal <file>`     | AI-assisted file repair *(Repowise)*  |
| `/report`          | Repository health report *(Repowise)* |
| `/guard on/off`    | Git commit protection *(Repowise)*    |
| `/approve on/off`  | Toggle file auto-approval             |
| `/undo <file>`     | Restore latest backup                 |
| `/ripple <prompt>` | Multi-file architectural changes      |
| `/reset`           | Reset current session                 |
| `/clear`           | Clear terminal                        |
| `/exit`            | Exit TermiCode                        |

---

# 🧪 Development

Clone the repository:

```bash
git clone https://github.com/parthpathakpp29/termicode.git

cd termicode

python -m venv .venv

source .venv/bin/activate

pip install -e .[dev]
```

Run tests:

```bash
pytest
```

---

# 📚 Documentation

| Document                | Description                              |
| ----------------------- | ---------------------------------------- |
| `ARCHITECTURE.md`       | Codebase architecture and execution flow |
| `CONTRIBUTING.md`       | Contribution guide                       |
| `CHANGELOG.md`          | Release history                          |
| `SECURITY.md`           | Security reporting policy                |
| `CODE_OF_CONDUCT.md`    | Community guidelines                     |
| `docs/model-routing.md` | Model routing system                     |
| `docs/tool-system.md`   | Tool execution architecture              |
| `docs/sessions.md`      | Session persistence                      |
| `docs/file-editing.md`  | File editing workflow                    |
| `docs/approval-flow.md` | Approval and safety model                |

---

# 🤝 Contributing

Contributions are welcome.

Whether you're fixing a bug, improving documentation, adding tests, or implementing a new feature, we'd love your help.

Before opening large feature PRs, please open an issue to discuss the proposal.

See **CONTRIBUTING.md** for setup instructions and contribution guidelines.

---

# 📄 License

Licensed under the **MIT License**.

See **LICENSE** for details.
