import json
import os

from termicode import tools
from termicode.ui import (
    print_backup_notice,
    print_command_alert,
    print_security_alert,
    print_tool_result,
    print_tool_triggered,
)


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

        if print_security_alert("Write / Overwrite File", file_path):
            if tools._is_protected(file_path):
                result = f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted for security reasons."
            else:
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
        elif print_security_alert("Surgical File Edit", file_path):
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
        if print_security_alert("Delete File", file_path):
            try:
                if tools._is_protected(file_path):
                    result = f"Error: Access to '{os.path.basename(file_path)}' is permanently restricted."
                else:
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
