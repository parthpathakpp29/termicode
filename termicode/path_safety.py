import os


PROTECTED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".termicode_history.json",
    ".termicode_memory.json",
}

PROTECTED_BASENAMES = {
    "credentials.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

PROTECTED_EXTENSIONS = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)


def _is_protected(path: str) -> bool:
    """Returns True if the file matches the protected blocklist or secret patterns."""
    basename = os.path.basename(path)
    lower = basename.lower()

    if basename in PROTECTED_FILES or lower in PROTECTED_BASENAMES:
        return True
    if lower.startswith(".env"):
        return True
    if lower.startswith("secrets."):
        return True
    if lower.endswith(PROTECTED_EXTENSIONS):
        return True

    return False


def validate_path(requested_path: str) -> str:
    """Validate that requested_path resolves inside the current working directory."""
    cwd = os.path.abspath(os.getcwd())
    abs_path = os.path.abspath(requested_path)

    try:
        common = os.path.commonpath([cwd, abs_path])
        if common != cwd:
            raise PermissionError(f"Access denied: Path '{abs_path}' is outside the workspace '{cwd}'.")
    except ValueError:
        raise PermissionError(f"Access denied: Path '{abs_path}' has no common path with workspace '{cwd}'.")

    return abs_path
