import os

from ddgs import DDGS

from termicode.ignore import (
    load_gitignore_patterns,
    prune_walk_dirs,
    should_skip_by_gitignore,
    should_skip_file,
)
from termicode.path_safety import _is_protected, validate_path


def search_codebase(directory_path: str, query: str) -> str:
    """Search for an exact string across text files in a directory."""
    try:
        validated_path = validate_path(directory_path)
        gitignore_patterns = load_gitignore_patterns(validated_path)
        results = []

        for root, dirs, files in os.walk(validated_path):
            prune_walk_dirs(root, dirs)

            rel_root = os.path.relpath(root, validated_path)
            if rel_root == ".":
                rel_root = ""

            if rel_root and should_skip_by_gitignore(rel_root.replace("\\", "/"), is_dir=True, patterns=gitignore_patterns):
                dirs.clear()
                continue

            for file in files:
                if _is_protected(file):
                    continue
                if should_skip_file(file):
                    continue

                rel_file = os.path.join(rel_root, file) if rel_root else file
                if should_skip_by_gitignore(rel_file.replace("\\", "/"), is_dir=False, patterns=gitignore_patterns):
                    continue

                file_path = os.path.join(root, file)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    for line_number, line in enumerate(lines, 1):
                        if query in line:
                            clean_line = line.strip()
                            if len(clean_line) > 100:
                                clean_line = clean_line[:97] + "..."
                            results.append(f"{file_path} (Line {line_number}): {clean_line}")
                except (UnicodeDecodeError, PermissionError):
                    continue

        if not results:
            return f"No matches found for '{query}' in directory '{directory_path}'."

        if len(results) > 50:
            return f"Found {len(results)} matches. Showing first 50:\n" + "\n".join(results[:50])

        return f"Found {len(results)} matches:\n" + "\n".join(results)

    except PermissionError as e:
        return str(e)
    except OSError as e:
        return f"Error Searching Codebase: {e}"


def search_web(query: str) -> str:
    """Searches the live internet using DuckDuckGo and returns the top results."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return f"No results found on the web for '{query}'."

        formatted_results = f"--- Web Search Results for '{query}' ---\n\n"
        for i, res in enumerate(results, 1):
            title = res.get("title", "No Title")
            href = res.get("href", "No URL")
            body = res.get("body", "No Description")
            formatted_results += f"{i}. {title}\nURL: {href}\nSnippet: {body}\n\n"

        return formatted_results

    except Exception as e:
        return f"Error searching the web: {e}"
