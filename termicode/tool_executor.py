import json
import os

from termicode import tools
from termicode.diff import build_delete_preview, build_edit_preview, build_write_preview
from termicode.ui import (
    print_auto_approved,
    print_backup_notice,
    print_command_alert,
    print_security_alert,
    print_tool_result,
    print_tool_triggered,
)


class ApprovalState:
    """Session-scoped approval state for file write/edit/delete tools.

    A small object rather than a bare module variable, so the state has one
    named home to reset from in tests and to reason about, instead of a global
    that could be reassigned from anywhere. There is exactly one instance for
    the process — TermiCode is a single, interactive session, not a server —
    so this is not a general session/config framework, just a home for one flag.

    Deliberately does not cover run_command: a diff preview can show what a
    file write will do in advance; it cannot show what an arbitrary shell
    command will do, so that prompt always blocks regardless of this flag.

    Not persisted across restarts — carrying "approve everything" silently
    into a session the user does not remember granting it in would be a
    bigger risk than asking again next time.
    """

    def __init__(self):
        self.auto_approve_files = False

    def enable(self) -> None:
        self.auto_approve_files = True

    def disable(self) -> None:
        self.auto_approve_files = False


approval_state = ApprovalState()


def _confirm(action: str, file_path: str, preview: str) -> bool:
    """Shows the pending change and returns whether it is approved.

    Answering "always" at the prompt turns on auto-approve for the rest of
    the session; later calls then show the same preview without blocking.
    """
    if approval_state.auto_approve_files:
        print_auto_approved(action, file_path, preview)
        return True

    response = print_security_alert(action, file_path, preview)
    if response == "always":
        approval_state.enable()
    return response in ("yes", "always")


class MockToolCall:
    def __init__(self, data):
        self.id = data["id"]
        self.type = data["type"]
        self.function = MockFunction(data["function"])


class MockFunction:
    def __init__(self, func_data):
        self.name = func_data["name"]
        self.arguments = func_data["arguments"]


def execute_tool(tool_call) -> str:
    """Manually routes LLM tool requests to Python functions."""
    name = tool_call.function.name
    try:
        args_str = tool_call.function.arguments
        if args_str is None or args_str == "":
            args = {}
        else:
            args = json.loads(args_str) or {}
    except (json.JSONDecodeError, TypeError):
        return "Error: Invalid JSON arguments provided for tool call."

    print_tool_triggered(name, args)

    if name == "list_directory":
        result = tools.list_directory(args.get("directory_path", "."))

    elif name == "read_file":
        result = tools.read_file(
            args.get("file_path"),
            start_line=args.get("start_line"),
            end_line=args.get("end_line"),
        )

    elif name == "write_file":
        file_path = args.get("file_path")
        content = args.get("content", "")
        if isinstance(content, list):
            content = "\n".join(content)

        # Refused before prompting: approving would render the current contents
        # of a protected file into the preview below.
        if tools._is_protected(file_path):
            result = f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."
        elif _confirm(
            "Write / Overwrite File", file_path, build_write_preview(file_path, content)
        ):
            result = tools.write_file_approved(file_path, content)
            if "Snapshot:" in result:
                backup_path = result.split("Snapshot:", 1)[1].strip()
                print_backup_notice(backup_path)
        else:
            result = f"Action blocked: User denied permission to write '{file_path}'."

    elif name == "edit_file":
        file_path = args.get("file_path")
        search_string = args.get("search_string", "")
        if isinstance(search_string, list):
            search_string = search_string[0] if search_string else ""

        replace_string = args.get("replace_string", "")
        if isinstance(replace_string, list):
            replace_string = replace_string[0] if replace_string else ""

        if not search_string:
            result = "Error: search_string cannot be empty."
        elif tools._is_protected(file_path):
            result = f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."
        elif _confirm(
            "Surgical File Edit", file_path, build_edit_preview(file_path, search_string, replace_string)
        ):
            result = tools.edit_file_approved(file_path, search_string, replace_string)
        else:
            result = "Action blocked: User denied permission to edit the file."

    elif name == "run_command":
        command = args.get("command")
        if print_command_alert(command):
            result = tools.run_command_approved(command)
        else:
            result = "Action blocked: User denied permission to execute this command."

    elif name == "search_codebase":
        result = tools.search_codebase(args.get("directory_path"), args.get("query"))
    elif name == "restore_backup":
        result = tools.restore_backup(args.get("file_path"))
    elif name == "create_directory":
        result = tools.create_directory(args.get("directory_path"))
    elif name == "delete_file":
        file_path = args.get("file_path")
        if tools._is_protected(file_path):
            result = f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted."
        elif _confirm("Delete File", file_path, build_delete_preview(file_path)):
            try:
                result = tools.delete_file_approved(file_path)
            except Exception as e:
                result = str(e)
        else:
            result = f"Action blocked: User denied permission to delete '{file_path}'."
    elif name == "search_web":
        result = tools.search_web(args.get("query"))
    elif name == "generate_termicode_rules":
        result = tools.generate_termicode_rules()
    elif name == "get_overview":
        result = tools.get_overview()
    elif name == "get_context":
        result = tools.get_context(args.get("targets", ""))
    elif name == "get_health":
        result = tools.get_health(args.get("targets", ""))
    else:
        result = f"Error: Unknown tool '{name}'"

    print_tool_result(result)
    return result
