import glob
import os
import time
from typing import Optional

from termicode.ignore import should_skip_dir
from termicode.path_safety import _is_protected, validate_path


def list_directory(directory_path: str = ".") -> str:
    """List all files and folders in the specified directory."""
    try:
        validated_path = validate_path(directory_path)
        items = os.listdir(validated_path)
        if not items:
            return f"The directory '{directory_path}' is empty."

        filtered_items = [
            item for item in items
            if not _is_protected(item) and not should_skip_dir(item, validated_path)
        ]

        if not filtered_items:
            return f"The directory '{directory_path}' contains only protected files."

        formatted_list = "\n".join([f"- {item}" for item in filtered_items])
        return f"Contents of '{directory_path}':\n{formatted_list}"

    except FileNotFoundError:
        return f"Error: Directory '{directory_path}' not found."
    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error listing directory: {e}"


def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Read file content, optionally within a line range."""
    try:
        validated_path = validate_path(file_path)
        if _is_protected(file_path):
            return f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."
        if not os.path.exists(validated_path):
            return f"Error: '{file_path}' does not exist. Try listing the directory first."

        with open(validated_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)

        if start_line is None and end_line is None:
            if total_lines > 2500:
                return f"Error: File is massively large ({total_lines} lines). You must specify 'start_line' and 'end_line' to read specific chunks. DO NOT attempt to read this entire file chunk-by-chunk."
            content = "".join(lines)
            return f"--- Contents of {file_path} ---\n{content}\n--- End of file ---"

        s_idx = max(0, (start_line - 1)) if start_line is not None else 0
        e_idx = min(total_lines, end_line) if end_line is not None else total_lines

        sliced_lines = lines[s_idx:e_idx]
        content_list = []
        for idx, line in enumerate(sliced_lines, start=s_idx + 1):
            content_list.append(f"{idx}: {line}")
        content = "".join(content_list)

        return f"--- Contents of {file_path} (Lines {s_idx + 1} to {e_idx}) ---\n{content}\n--- End of file ---"

    except FileNotFoundError:
        return f"Error: The file '{file_path}' does not exist. Try listing the directory first."
    except UnicodeDecodeError:
        return f"Error: '{file_path}' appears to be a binary file or image, which cannot be read as text."
    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error reading file: {e}"


def write_file_approved(file_path: str, content: str) -> str:
    """Writes or overwrites a file. Caller must obtain user approval first."""
    try:
        validated_path = validate_path(file_path)
        if _is_protected(file_path):
            return f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."

        backup_path = None
        if os.path.exists(validated_path):
            timestamp = int(time.time())
            backup_path = f"{validated_path}.{timestamp}.bak"
            with open(backup_path, "w", encoding="utf-8") as f:
                with open(validated_path, "r", encoding="utf-8") as original:
                    f.write(original.read())

        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content)

        result = f"Success: Wrote new content to '{file_path}'."
        if backup_path:
            result += f" Snapshot: {backup_path}"
        return result
    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error writing file: {e}"


def edit_file_approved(file_path: str, search_string: str, replace_string: str) -> str:
    """Surgically replaces text in a file. Caller must obtain user approval first."""
    if not search_string:
        return "Error: search_string cannot be empty. Please specify the exact code block you want to replace."

    try:
        validated_path = validate_path(file_path)
        if _is_protected(file_path):
            return f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."

        if not os.path.exists(validated_path):
            return f"Error: '{file_path}' does not exist. Use write_file to create new files."

        with open(validated_path, "r", encoding="utf-8") as f:
            content = f.read()

        if search_string not in content:
            return "Error: The exact 'search_string' was not found in the file. Ensure you are matching indentation and line breaks perfectly."

        timestamp = int(time.time())
        backup_path = f"{validated_path}.{timestamp}.bak"
        with open(backup_path, "w", encoding="utf-8") as backup:
            backup.write(content)

        new_content = content.replace(search_string, replace_string, 1)

        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Success: Surgically edited '{file_path}'."

    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error editing file: {e}"


def restore_backup(file_path: str) -> str:
    """Restores the most recent timestamped backup file (.bak)."""
    try:
        validated_path = validate_path(file_path)
        backups = glob.glob(f"{validated_path}.*.bak")
        if not backups:
            return f"Error: No backup snapshots found for '{file_path}'."

        backups.sort(reverse=True)
        latest_backup = backups[0]

        if os.path.exists(validated_path):
            os.remove(validated_path)

        os.rename(latest_backup, validated_path)
        return f"Success: Restored '{file_path}' from snapshot {os.path.basename(latest_backup)}."

    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error restoring backup: {e}"


def create_directory(directory_path: str) -> str:
    """Creates a new folder/directory."""
    try:
        validated_path = validate_path(directory_path)
        os.makedirs(validated_path, exist_ok=True)
        return f"Success: Created Directory '{directory_path}'."
    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error creating directory: {e}"


def delete_file_approved(file_path: str) -> str:
    """Deletes a file by moving it to a timestamped backup."""
    try:
        if _is_protected(file_path):
            return f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted."

        validated_path = validate_path(file_path)

        if not os.path.exists(validated_path):
            return f"Error: '{file_path}' does not exist."

        timestamp = int(time.time())
        backup_path = f"{validated_path}.{timestamp}.bak"
        os.rename(validated_path, backup_path)

        return f"Success: Deleted '{file_path}' (Safely moved to backup)."

    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error deleting file: {e}"
