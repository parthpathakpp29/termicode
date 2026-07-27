import os
import subprocess

import pytest

from termicode.path_safety import validate_path
from termicode.file_tools import read_file


def _make_dir_link(link_path: str, target_path: str) -> bool:
    """Create link_path -> target_path as a symlink (POSIX) or a directory
    junction (Windows, via mklink /J, which unlike os.symlink needs no
    elevated privilege). Returns False if neither is possible here, so the
    test can skip rather than fail on a restricted environment.
    """
    try:
        os.symlink(target_path, link_path, target_is_directory=True)
        return True
    except OSError:
        pass

    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link_path, target_path],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    return False


@pytest.fixture
def escaping_workspace(tmp_path):
    """workspace/escape -> ../outside, with a secret only reachable through
    the link. Skips if this environment cannot create the link at all."""
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret data", encoding="utf-8")

    if not _make_dir_link(str(workspace / "escape"), str(outside)):
        pytest.skip("could not create a symlink or junction in this environment")

    return workspace


def test_validate_path_blocks_a_symlinked_escape(escaping_workspace, monkeypatch):
    """Reproduces a confirmed real escape: a Windows directory junction (no
    admin privilege required to create one) let validate_path's old
    abspath-based check treat a path physically outside the workspace as
    though it were inside it, and read_file returned the linked-to file's
    real contents."""
    monkeypatch.chdir(escaping_workspace)

    with pytest.raises(PermissionError):
        validate_path("escape/secret.txt")


def test_read_file_refuses_a_symlinked_escape(escaping_workspace, monkeypatch):
    monkeypatch.chdir(escaping_workspace)

    result = read_file("escape/secret.txt")

    assert "top secret data" not in result
    assert "Access denied" in result or "outside the workspace" in result


def test_validate_path_still_allows_an_ordinary_file(escaping_workspace, monkeypatch):
    """The fix must not make every real, non-linked file suspect too."""
    monkeypatch.chdir(escaping_workspace)
    (escaping_workspace / "normal.py").write_text("x = 1\n", encoding="utf-8")

    validated = validate_path("normal.py")

    assert os.path.exists(validated)
