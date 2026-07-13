import os

from termicode.ignore import (
    load_gitignore_patterns,
    prune_walk_dirs,
    should_skip_by_gitignore,
    should_skip_file,
)


def generate_local_project_map(max_depth: int = 3, max_chars: int = 3000) -> str:
    """Generates a compact text-based tree of the local project directory."""
    project_map = []
    gitignore_patterns = load_gitignore_patterns(".")

    try:
        for root, dirs, files in os.walk("."):
            prune_walk_dirs(root, dirs)

            rel_root = os.path.relpath(root, ".")
            if rel_root == ".":
                rel_root = ""

            if rel_root and should_skip_by_gitignore(rel_root, is_dir=True, patterns=gitignore_patterns):
                dirs.clear()
                continue

            level = 0 if rel_root == "" else rel_root.count(os.sep) + 1
            if level > max_depth:
                dirs.clear()
                continue

            indent = " " * 4 * level
            sub_folder = os.path.basename(root)
            if sub_folder and sub_folder != ".":
                project_map.append(f"{indent}[DIR] {sub_folder}/")

            sub_indent = " " * 4 * (level + 1)
            for file in sorted(files):
                if should_skip_file(file):
                    continue

                rel_file = os.path.join(rel_root, file) if rel_root else file
                if should_skip_by_gitignore(rel_file.replace("\\", "/"), is_dir=False, patterns=gitignore_patterns):
                    continue

                project_map.append(f"{sub_indent}[FILE] {file}")

                if len("\n".join(project_map)) > max_chars:
                    project_map.append(f"{sub_indent}... [MAP TRUNCATED - use list_directory to explore further]")
                    return "\n".join(project_map)

    except OSError as e:
        return f"Error generating project map: {e}"

    return "\n".join(project_map)
