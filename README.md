<div align="center">
  <img src="https://via.placeholder.com/150x150/09090b/22d3ee?text=TERMICODE" alt="TermiCode Logo">
  
  <h1>TermiCode AI Coding Assistant</h1>
  <p>A blazing fast, private, local AI coding assistant running directly in your terminal, powered by OpenRouter and 100+ AI models.</p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
</div>

---

TermiCode is a terminal-based Micro-SaaS AI coding assistant built for speed and security. It reads your codebase, modifies files securely via surgical edits, and can even run terminal commands (with your permission). Because it leverages OpenRouter's marketplace of 100+ AI models, TermiCode gives you access to the best models from Anthropic, Google, Meta, Mistral, and more.

**Bring Your Own Key (BYOK)**: No monthly subscriptions. No bloated Electron apps.

## ✨ Features
- **⚡ Multi-Model Access**: Powered by OpenRouter with access to 100+ AI models from Anthropic, Google, Meta, Mistral, and more.
- **🛡️ Secure File Operations**: Built-in path traversal protection and a blocklist for sensitive files (like `.env`).
- **👀 Surgical Edits**: Modifies existing files precisely without rewriting the whole document, saving tokens and preventing hallucinations.
- **🖥️ Beautiful Terminal UI**: Powered by `rich` for elegant panels, Markdown rendering, and live spinners.
- **🧠 Long-Term Memory**: Automatically summarizes past context to preserve memory without exceeding token limits.
- **🚦 Command Execution**: Can run test suites, git commands, and shell scripts on your behalf (always asks for permission first).

## 🚀 Installation

### Option 1: Install globally via pipx (Recommended)
`pipx` installs Python CLI applications into isolated environments so they don't break your system Python.
```bash
pipx install termicode-ai
```

### Option 2: Install via pip
```bash
pip install termicode-ai
```

## ⚙️ Configuration

TermiCode requires an OpenRouter API key to operate.

1. Get a free API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. Create a `.env` file in the directory where you plan to run TermiCode, and add:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   ```
*(Alternatively, you can export `OPENROUTER_API_KEY` as a system environment variable in your terminal).*

## 💻 Usage

Navigate to any project directory in your terminal and simply type:
```bash
termicode
```

This starts the interactive AI shell. 
Type `/help` to see available slash commands:
- `/map` - Print the current project structure tree.
- `/clear` - Clear the terminal screen.
- `/reset` - Wipe the agent's short-term memory and start fresh.
- `/exit` - Save session and exit.

**Example Prompts:**
- *"Refactor my calculate_tax function in utils.py to handle edge cases."*
- *"Search the codebase for 'DATABASE_URL' and tell me where it's used."*
- *"Run the pytest suite and fix any failing tests."*

## 🛠️ Developer Setup (Local Building)

If you want to contribute or build TermiCode locally from the source code:

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/termicode.git
   cd termicode
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in editable mode with dev dependencies**
   ```bash
   pip install -e .[dev]
   ```

4. **Run the CLI locally**
   ```bash
   termicode
   ```

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
