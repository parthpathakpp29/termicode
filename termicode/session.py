import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from termicode.ui import print_token_guard, print_warning


# Session state used to live in the working directory, which meant every
# project accumulated a transcript containing the full contents of every file
# the agent read. It now lives under the user's home directory, outside the
# workspace, so validate_path keeps it out of the agent's reach as well.
LEGACY_HISTORY_FILE = ".termicode_history.json"
LEGACY_MEMORY_FILE = ".termicode_memory.json"

_warned_about_fallback = False


def _project_key() -> str:
    """A readable, collision-free identifier for the current project."""
    project_path = os.path.abspath(os.getcwd())
    digest = hashlib.sha256(os.path.normcase(project_path).encode("utf-8")).hexdigest()[:8]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(project_path)) or "project"
    return f"{name}-{digest}"


def session_dir() -> Optional[Path]:
    """Where session state is kept, or None when the home directory is unusable.

    Honours $TERMICODE_HOME. Returning None makes callers fall back to the old
    project-local filenames, so an unwritable home degrades instead of crashing.
    """
    global _warned_about_fallback

    override = os.environ.get("TERMICODE_HOME", "").strip()
    try:
        root = Path(override) if override else Path.home() / ".termicode"
        directory = root / "sessions"
        directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(directory, 0o700)
        return directory
    except (OSError, RuntimeError) as exc:
        if not _warned_about_fallback:
            _warned_about_fallback = True
            print_warning(f"Could not use the session directory ({exc}). Keeping session files in this folder.")
        return None


def history_path() -> str:
    """Absolute path to this project's chat history."""
    directory = session_dir()
    if directory is None:
        return LEGACY_HISTORY_FILE
    return str(directory / f"{_project_key()}.history.json")


def memory_path() -> str:
    """Absolute path to this project's rolling memory summary."""
    directory = session_dir()
    if directory is None:
        return LEGACY_MEMORY_FILE
    return str(directory / f"{_project_key()}.memory.json")


def migrate_legacy_session() -> Optional[str]:
    """Move project-local session files into the session directory.

    Returns the directory they were moved to, or None if nothing moved. An
    existing file at the destination always wins, and the legacy file is left
    in place rather than deleted: an ambiguity is not a reason to discard data.
    """
    if session_dir() is None:
        return None

    moved = False
    for legacy_file, destination in (
        (LEGACY_HISTORY_FILE, history_path()),
        (LEGACY_MEMORY_FILE, memory_path()),
    ):
        if not os.path.exists(legacy_file):
            continue

        if os.path.exists(destination):
            print_warning(f"Ignoring legacy '{legacy_file}'; a newer session already exists.")
            continue

        try:
            shutil.move(legacy_file, destination)
            moved = True
        except OSError as exc:
            print_warning(f"Could not move '{legacy_file}': {exc}")

    return os.path.dirname(history_path()) if moved else None


def prune_context(messages: List[Dict[str, Any]], max_turns: int = 25) -> List[Dict[str, Any]]:
    """Trim chat history while preserving system prompt and tool-message alignment."""
    if len(messages) <= max_turns:
        return messages

    before = len(messages)
    system_prompt = messages[0]
    keep_count = 12

    split_index = len(messages) - keep_count
    while split_index > 1:
        msg = messages[split_index]
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        if role == "tool":
            split_index -= 1
        else:
            break

    recent_history = messages[split_index:]
    historical_pool = messages[1:split_index]

    cleaned_pool = []
    for msg in historical_pool:
        if isinstance(msg, dict):
            role = msg.get("role")
            has_tool_calls = bool(msg.get("tool_calls"))
        else:
            role = getattr(msg, "role", None)
            has_tool_calls = bool(getattr(msg, "tool_calls", None))
        if role in ["user", "assistant"] and not has_tool_calls:
            cleaned_pool.append(msg)

    pruned = [system_prompt] + cleaned_pool + recent_history
    print_token_guard(before, len(pruned))
    return pruned


def update_memory_summary(client, old_summary: str, messages_to_drop: list) -> str:
    """Calls a fast model to summarize dropped context into rolling memory."""
    transcript = ""
    for msg in messages_to_drop:
        role = msg.get("role", "unknown") if isinstance(msg, dict) else getattr(msg, "role", "unknown")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")

        if role in ["user", "assistant"] and content:
            transcript += f"{role.upper()}: {content[:1000]}\n"

    if not transcript.strip():
        return old_summary

    prompt = (
        "You are the memory manager for an AI coding assistant.\n"
        "Read the existing memory summary, followed by a transcript of a recent conversation that is being deleted from short-term memory.\n"
        "Output a new, unified, highly concise summary (max 4 sentences) capturing the user's overarching intent, important project details, decisions made, and bugs fixed.\n\n"
        f"EXISTING SUMMARY:\n{old_summary or 'None'}\n\n"
        f"DROPPED TRANSCRIPT:\n{transcript}\n\n"
        "OUTPUT ONLY THE NEW SUMMARY TEXT."
    )

    try:
        response = client.chat.completions.create(
            model="nvidia/nemotron-nano-9b-v2:free",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return old_summary


def save_memory_summary(summary: str) -> None:
    """Persists the rolling long-term memory summary to disk."""
    try:
        with open(memory_path(), "w", encoding="utf-8") as f:
            json.dump({"summary": summary}, f, indent=2)
    except OSError as e:
        print_warning(f"Failed to persist memory summary: {e}")


def load_memory_summary() -> str:
    """Loads the rolling long-term memory summary from disk if available."""
    if os.path.exists(memory_path()):
        try:
            with open(memory_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("summary", "")
        except (OSError, json.JSONDecodeError) as e:
            print_warning(f"Corrupted memory file. Starting fresh. ({e})")
    return ""


def save_session(messages: List[Any], summary: str = "") -> None:
    """Persists chat history and long-term memory summary together."""
    save_chat_history(messages)
    save_memory_summary(summary)


def save_chat_history(messages: List[Any]) -> None:
    """Normalizes SDK objects into JSON-serializable dicts."""
    serializable_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            serializable_messages.append(msg)
        else:
            msg_dict = {"role": msg.role, "content": msg.content}
            if getattr(msg, "tool_calls", None):
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ]
            serializable_messages.append(msg_dict)

    if serializable_messages and serializable_messages[-1].get("tool_calls"):
        serializable_messages.pop()

    try:
        with open(history_path(), "w", encoding="utf-8") as f:
            json.dump(serializable_messages, f, indent=4)
    except (OSError, TypeError) as e:
        print_warning(f"Failed to persist chat history: {e}")


def load_chat_history() -> Optional[List[Dict[str, Any]]]:
    """Loads previous session messages from file if available."""
    if os.path.exists(history_path()):
        try:
            with open(history_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print_warning(f"Corrupted history file. Starting fresh. ({e})")
    return None
