"""Preview construction for file operations awaiting approval.

An approval prompt is only meaningful if the user can see what they are
approving. These helpers turn a pending write, edit or delete into display text
before anything touches disk.

They deal in plain strings and never raise: rendering belongs to termicode.ui,
and a preview failing is never a reason to fail the operation itself.
"""

import difflib
import os
from typing import Optional, Tuple

from termicode.path_safety import _is_protected, validate_path


MAX_PREVIEW_LINES = 80

PROTECTED_NOTICE = "This path is protected. TermiCode will not read or modify it."
BINARY_NOTICE = "Binary or non-UTF-8 file; no preview available."


def _resolve(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolve a path for previewing. Returns (validated_path, refusal).

    Exactly one side is populated. Protected paths are refused before any read,
    so a preview can never disclose the contents of a guarded file.
    """
    if not file_path:
        return None, "No file path was provided."

    if _is_protected(file_path):
        return None, PROTECTED_NOTICE

    try:
        return validate_path(file_path), None
    except PermissionError as exc:
        return None, str(exc)


def _read_text(validated_path: str) -> Optional[str]:
    """Return file contents, or None when they are not readable UTF-8 text."""
    try:
        with open(validated_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _cap(lines: list) -> str:
    """Trim a preview to MAX_PREVIEW_LINES, noting how much is hidden."""
    if len(lines) <= MAX_PREVIEW_LINES:
        return "\n".join(lines)

    hidden = len(lines) - MAX_PREVIEW_LINES
    return "\n".join(lines[:MAX_PREVIEW_LINES] + [f"... {_plural(hidden, 'more line')} not shown"])


def _unified(before: str, after: str, from_label: str, to_label: str) -> str:
    """Build a capped unified diff, or say so when nothing would change."""
    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )

    if not diff_lines:
        return "No changes: the file already matches the proposed content."

    return _cap(diff_lines)


def build_edit_preview(file_path: str, search_string: str, replace_string: str) -> str:
    """Show what a surgical edit would change, or why it would fail."""
    validated_path, refusal = _resolve(file_path)
    if refusal:
        return refusal

    if not os.path.exists(validated_path):
        return f"'{file_path}' does not exist, so this edit will fail."

    before = _read_text(validated_path)
    if before is None:
        return BINARY_NOTICE

    occurrences = before.count(search_string)
    if occurrences == 0:
        return (
            "The search text was not found in this file, so this edit will fail.\n"
            "It must match the existing text exactly, including indentation and line breaks."
        )

    after = before.replace(search_string, replace_string, 1)
    preview = _unified(before, after, f"{file_path} (current)", f"{file_path} (proposed)")

    if occurrences > 1:
        preview = (
            f"Note: the search text appears {occurrences} times; only the first is replaced.\n\n"
            f"{preview}"
        )

    return preview


def build_write_preview(file_path: str, content: str) -> str:
    """Show the content of a new file, or the diff of an overwrite."""
    validated_path, refusal = _resolve(file_path)
    if refusal:
        return refusal

    if not os.path.exists(validated_path):
        body = _unified("", content, "(new file)", f"{file_path} (proposed)")
        return f"New file, {_plural(len(content.splitlines()), 'line')}.\n\n{body}"

    before = _read_text(validated_path)
    if before is None:
        return BINARY_NOTICE

    return _unified(before, content, f"{file_path} (current)", f"{file_path} (proposed)")


def build_delete_preview(file_path: str) -> str:
    """Show what a delete would discard before it is moved to a backup."""
    validated_path, refusal = _resolve(file_path)
    if refusal:
        return refusal

    if not os.path.exists(validated_path):
        return f"'{file_path}' does not exist."

    text = _read_text(validated_path)
    if text is None:
        return "Binary or non-UTF-8 file. It will be moved to a timestamped .bak backup."

    lines = text.splitlines()
    header = f"{_plural(len(lines), 'line')} will be moved to a timestamped .bak backup:"
    return f"{header}\n\n{_cap(lines)}"
