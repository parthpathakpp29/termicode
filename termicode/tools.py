"""Compatibility facade for TermiCode tool functions.

The implementation now lives in focused modules, but this file keeps the old
``termicode.tools`` import surface stable for the CLI and external users.
"""

from termicode.command_tools import run_command_approved
from termicode.doctor import format_doctor_summary, run_doctor
from termicode.file_tools import (
    create_directory,
    delete_file_approved,
    edit_file_approved,
    list_directory,
    read_file,
    restore_backup,
    write_file_approved,
)
from termicode.health_tools import get_context, get_health, get_overview
from termicode.path_safety import (
    PROTECTED_BASENAMES,
    PROTECTED_EXTENSIONS,
    PROTECTED_FILES,
    _is_protected,
    validate_path,
)
from termicode.rules import generate_termicode_rules
from termicode.report import build_report_markdown, generate_repo_report
from termicode.search_tools import search_codebase, search_web


__all__ = [
    "PROTECTED_BASENAMES",
    "PROTECTED_EXTENSIONS",
    "PROTECTED_FILES",
    "_is_protected",
    "validate_path",
    "list_directory",
    "read_file",
    "write_file_approved",
    "edit_file_approved",
    "restore_backup",
    "run_command_approved",
    "search_codebase",
    "create_directory",
    "delete_file_approved",
    "search_web",
    "generate_termicode_rules",
    "run_doctor",
    "format_doctor_summary",
    "build_report_markdown",
    "generate_repo_report",
    "get_overview",
    "get_context",
    "get_health",
]
