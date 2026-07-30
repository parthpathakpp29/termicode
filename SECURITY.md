# Security Policy

TermiCode reads, writes, and deletes files, and can run arbitrary shell commands, on the user's behalf. Taking security issues seriously here means more than the usual web-app checklist.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security vulnerability. Instead, open a private [GitHub Security Advisory](https://github.com/parthpathakpp29/termicode/security/advisories/new) for this repository, or contact the maintainer directly through GitHub.

Include, if you can:
- What you found and why it's exploitable (a path-traversal, a way to bypass an approval prompt, a way to read a protected file, etc.).
- Steps to reproduce, or a minimal example.
- The potential impact as you see it.

You should get an acknowledgement within a few days. This is a volunteer-maintained project without a dedicated security team, so please be patient — but security reports are treated as a priority over other work.

## What's in scope

- The sandbox boundary (`path_safety.py`) — anything that lets a tool call read, write, or execute outside the intended workspace.
- The protected-file blocklist — anything that lets `.env`, private keys, or TermiCode's own session state be read or written despite being marked protected.
- The approval flow — anything that lets a file mutation or a shell command execute without the user's actual consent (bypassing the prompt, or a preview that misrepresents what will actually happen).
- The model catalog and routing (`catalog.py`, `models.py`) — anything that could cause a paid model to be silently used, or cost to be misreported.
- Secret handling — anything that could cause an API key or session content to be written somewhere unintended (logs, a committed file, a third-party request).

## What's out of scope

- The model's own behavior. TermiCode does not control what a given LLM decides to do with the tools it's given — that's a property of the model and provider, not this codebase. (If a *specific tool's design* makes a bad model decision unusually consequential, that's in scope — e.g., a tool that doesn't need an approval prompt but arguably should.)
- Vulnerabilities that require the user to have already disabled a safety feature intentionally (e.g., `/approve on`, then complaining that a file was overwritten without a fresh prompt — that's the documented behavior of that setting, not a bug).
- Issues in third-party dependencies with no TermiCode-specific exploitation path — please report those upstream instead.

## Supported versions

There is no long-term-support branch yet — security fixes land on the latest release. Once TermiCode has multiple published minor versions, this section will specify which ones still receive fixes.
