import os
from typing import Iterable, List

# Directory names to skip anywhere in the tree (case-insensitive).
IGNORE_DIR_NAMES = {
    ".venv",
    "venv",
    "env",
    "virtualenv",
    ".virtualenv",
    "__pycache__",
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    ".vscode",
    ".idea",
    ".turbo",
    ".nuxt",
    "out",
    ".cache",
    "site-packages",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".tox",
    ".nox",
    "target",  # Rust / Java build output
    "vendor",
}

# Path segments that should never be walked (case-insensitive substring match).
IGNORE_PATH_SEGMENTS = {
    "site-packages",
    "node_modules",
    "__pycache__",
}

IGNORE_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".bak",
    ".log",
    ".exe",
    ".dll",
    ".so",
    ".pyd",
    ".whl",
    ".tar.gz",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".sqlite3",
    ".db",
    ".lock",
)

IGNORE_FILE_NAMES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
}


def _normalize_parts(path: str) -> List[str]:
    normalized = os.path.normpath(path).replace("\\", "/")
    return [part.lower() for part in normalized.split("/") if part and part != "."]


def path_contains_ignored_segment(path: str) -> bool:
    parts = _normalize_parts(path)
    return any(part in IGNORE_PATH_SEGMENTS for part in parts)


def should_skip_dir(dir_name: str, parent_root: str) -> bool:
    """Return True if a directory should be excluded from walks."""
    name_lower = dir_name.lower()

    if name_lower in IGNORE_DIR_NAMES:
        return True

    if name_lower.endswith(".dist-info") or name_lower.endswith(".egg-info"):
        return True

    candidate = os.path.join(parent_root, dir_name)
    if path_contains_ignored_segment(candidate):
        return True

    # Windows / mixed venv layout: Lib/site-packages, Scripts/python.exe
    if name_lower == "lib":
        if os.path.isdir(os.path.join(candidate, "site-packages")):
            return True

    if name_lower == "scripts":
        scripts_dir = candidate
        if os.path.isfile(os.path.join(scripts_dir, "python.exe")):
            return True
        if os.path.isfile(os.path.join(scripts_dir, "activate")):
            return True

    if name_lower == "include" and os.path.isfile(os.path.join(parent_root, "pyvenv.cfg")):
        return True

    return False


def should_skip_file(file_name: str) -> bool:
    lower = file_name.lower()
    if lower in IGNORE_FILE_NAMES:
        return True
    return lower.endswith(IGNORE_FILE_SUFFIXES)


def prune_walk_dirs(parent_root: str, dirs: Iterable[str]) -> None:
    """In-place prune of os.walk dirs list."""
    dirs[:] = [d for d in dirs if not should_skip_dir(d, parent_root)]


def load_gitignore_patterns(root: str = ".") -> List[str]:
    """Load simple .gitignore patterns (non-comment, non-empty lines)."""
    gitignore_path = os.path.join(root, ".gitignore")
    if not os.path.isfile(gitignore_path):
        return []

    patterns: List[str] = []
    try:
        with open(gitignore_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                patterns.append(stripped.rstrip("/"))
    except OSError:
        return []

    return patterns


def should_skip_by_gitignore(relative_path: str, is_dir: bool, patterns: List[str]) -> bool:
    """Best-effort .gitignore matching for common patterns."""
    if not patterns:
        return False

    normalized = relative_path.replace("\\", "/").strip("./")
    if not normalized:
        return False

    name = os.path.basename(normalized)
    for pattern in patterns:
        if pattern.startswith("/"):
            candidate = pattern.lstrip("/")
            if normalized == candidate or normalized.startswith(candidate + "/"):
                return True
            continue

        if "/" in pattern:
            if normalized == pattern or normalized.startswith(pattern + "/"):
                return True
            continue

        if name == pattern:
            return True
        if is_dir and normalized.endswith("/" + pattern):
            return True
        if f"/{pattern}/" in f"/{normalized}/":
            return True

    return False
