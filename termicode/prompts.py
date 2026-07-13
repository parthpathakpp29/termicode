import os


def build_system_prompt(current_map: str, summary: str = "") -> str:
    custom_rules = ""
    if os.path.exists("AGENT.md"):
        try:
            with open("AGENT.md", "r", encoding="utf-8") as f:
                custom_rules = f"\n\nUSER CUSTOM RULES:\n{f.read()}"
        except OSError:
            pass

    memory_block = (
        f"\n\n--- LONG-TERM MEMORY SUMMARY ---\n{summary}\n--------------------------------\n"
        if summary
        else ""
    )

    return (
        "You are TermiCode, an expert AI coding assistant.\n"
        "You have access to tools to read files, write files, and run terminal commands.\n"
        f"Project map:\n{current_map}\n{custom_rules}\n{memory_block}\n"
        "1. If you need to find where a specific function, variable, or text is located in the project, use 'search_codebase' first before trying to read files blindly.\n"
        "2. Never guess file contents. Use 'read_file'.\n"
        "3. Use 'write_file' ONLY for new files. For existing files, ALWAYS use 'edit_file' to patch lines surgically.\n"
        "4. When a user asks you to run, execute, or test code, you MUST use the 'run_command' tool to execute it in the terminal. Do NOT just print the code back to the user.\n"
        "5. CRITICAL TOKEN LIMIT: Never attempt to read more than 1 large file per turn.\n"
        "6. When using 'edit_file', your search_string MUST EXACTLY MATCH the file's existing text, including all whitespaces and line breaks.\n"
        "7. CRITICAL JSON FORMATTING: When using 'write_file' or 'edit_file', your code payload MUST be a single, properly escaped multiline string. NEVER output an array, list, or unescaped quotes. Do NOT wrap the code in markdown ``` blocks inside the JSON argument.\n"
        "8. ANTI-WANDERING PROTOCOL: Do not endlessly explore the directory. Read a maximum of 2 files for context, make a technical decision, execute the code, and return your final answer to the user immediately.\n"
        "9. REPOWISE INTEGRATION: You are connected to the Repowise intelligence engine. You MUST use tools like 'get_overview' and 'get_context' to understand project architecture and defect risks before modifying complex files. Rely on Repowise for deep context.\n"
        "10. RIPPLE ORCHESTRATION: If you modify a function signature, API endpoint, or database schema, you MUST immediately use 'search_codebase' or 'get_context' to find all dependent files that call it, and autonomously use 'edit_file' to update them. Do not stop until the system is consistent."
    )


def get_available_tools() -> list:
    return [
        {"type": "function", "function": {"name": "list_directory", "description": "Lists files in directory.", "parameters": {"type": "object", "properties": {"directory_path": {"type": "string"}}}}},
        {"type": "function", "function": {
            "name": "read_file",
            "description": "Reads file content. When inspecting a function or class, provide a broad range rather than a single line. If start_line and end_line are omitted, reads the whole file.",
            "parameters": {"type": "object", "properties": {
                "file_path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            }, "required": ["file_path"]},
        }},
        {"type": "function", "function": {"name": "write_file", "description": "Writes content to a new file.", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
        {"type": "function", "function": {"name": "run_command", "description": "Executes a terminal command and returns the output.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
        {"type": "function", "function": {
            "name": "edit_file",
            "description": "Surgically replaces a specific block of text in an existing file. ALWAYS prefer this over write_file for existing files.",
            "parameters": {"type": "object", "properties": {
                "file_path": {"type": "string"},
                "search_string": {"type": "string", "description": "The exact current text to replace."},
                "replace_string": {"type": "string", "description": "The new text to insert."},
            }, "required": ["file_path", "search_string", "replace_string"]},
        }},
        {"type": "function", "function": {
            "name": "search_codebase",
            "description": "Searches for a specific exact string across all text files.",
            "parameters": {"type": "object", "properties": {
                "directory_path": {"type": "string"},
                "query": {"type": "string"},
            }, "required": ["directory_path", "query"]},
        }},
        {"type": "function", "function": {
            "name": "restore_backup",
            "description": "Restores the most recent timestamped backup file (.bak).",
            "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
        }},
        {"type": "function", "function": {
            "name": "create_directory",
            "description": "Creates a new folder/directory.",
            "parameters": {"type": "object", "properties": {"directory_path": {"type": "string"}}, "required": ["directory_path"]},
        }},
        {"type": "function", "function": {
            "name": "delete_file",
            "description": "Deletes an existing file.",
            "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
        }},
        {"type": "function", "function": {
            "name": "search_web",
            "description": "Searches the live internet for up-to-date information.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "The search query to look up on the web."}}, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "generate_termicode_rules",
            "description": "Auto-generates an AGENT.md configuration file based on detected project type.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        {"type": "function", "function": {
            "name": "get_overview",
            "description": "Fetches the architectural overview, module map, and entry points.",
            "parameters": {"type": "object", "properties": {}},
        }},
        {"type": "function", "function": {
            "name": "get_context",
            "description": "Triage card for files/modules with graph-aware context.",
            "parameters": {"type": "object", "properties": {
                "targets": {"type": "string", "description": "The file paths or symbols to get context for."},
            }, "required": ["targets"]},
        }},
        {"type": "function", "function": {
            "name": "get_health",
            "description": "Scores files for defect risk, maintainability, and performance.",
            "parameters": {"type": "object", "properties": {
                "targets": {"type": "string", "description": "Optional specific files to score."},
            }},
        }},
    ]
