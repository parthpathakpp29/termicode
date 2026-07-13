import json
import os
from typing import Any, Dict, List, Optional

from termicode.ui import print_token_guard, print_warning


HISTORY_FILE = ".termicode_history.json"
MEMORY_FILE = ".termicode_memory.json"


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
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"summary": summary}, f, indent=2)
    except OSError as e:
        print_warning(f"Failed to persist memory summary: {e}")


def load_memory_summary() -> str:
    """Loads the rolling long-term memory summary from disk if available."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
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
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable_messages, f, indent=4)
    except (OSError, TypeError) as e:
        print_warning(f"Failed to persist chat history: {e}")


def load_chat_history() -> Optional[List[Dict[str, Any]]]:
    """Loads previous session messages from file if available."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print_warning(f"Corrupted history file. Starting fresh. ({e})")
    return None
