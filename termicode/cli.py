import os

from dotenv import load_dotenv
from rich.live import Live

from termicode import tools
from termicode.doctor import format_doctor_summary, run_doctor
from termicode.models import OPENROUTER_MODEL_STATS, get_token_usage, route_model
from termicode.project import generate_local_project_map
from termicode.prompts import build_system_prompt, get_available_tools
from termicode.report import generate_repo_report
from termicode.session import (
    HISTORY_FILE,
    MEMORY_FILE,
    load_chat_history,
    load_memory_summary,
    prune_context,
    save_memory_summary,
    save_session,
    update_memory_summary,
)
from termicode.startup import validate_startup
from termicode.tool_executor import MockToolCall, execute_tool
from termicode.ui import (
    console,
    make_response_panel,
    print_api_error,
    print_banner,
    print_help,
    print_loop_detected,
    print_project_map,
    print_startup_info,
    print_success,
    print_thinking_spinner,
    print_tool_list,
    print_warning,
    print_error,
)


def _build_heal_prompt(target_file: str) -> str:
    health_report = tools.get_health()
    max_chars = 6000
    if len(health_report) > max_chars:
        health_report = health_report[:max_chars] + "\n... [REPORT TRUNCATED TO FIT TOKEN BUDGET]"

    return (
        f"I want you to autonomously refactor and heal `{target_file}`.\n"
        f"Here is the exact Repowise codebase health report:\n\n"
        f"{health_report}\n\n"
        "CRITICAL INSTRUCTION: Do NOT read the entire file. Use `search_codebase` to find the line numbers of the 'Critical Issues'. "
        "Use `read_file` ONCE on those specific lines, and immediately execute `edit_file` to fix them. "
        "You have a strict limit of 5 tool calls before you must execute the fix. Be decisive."
    )


def _build_ripple_prompt(target_prompt: str) -> str:
    return (
        f"MULTI-FILE RIPPLE EDIT INITIATED: {target_prompt}\n\n"
        "EXECUTION PROTOCOL:\n"
        "1. Make the primary change requested using `edit_file`.\n"
        "2. Identify the exact symbol, function, or API endpoint you just changed.\n"
        "3. Use the `search_codebase` tool to find EVERY file in this workspace that imports, calls, or depends on that changed symbol.\n"
        "4. Autonomously `read_file` on those dependents, and use `edit_file` to update them to match the new signature.\n"
        "5. Repeat this process until all ripples are resolved. Do not stop and ask for permission. Execute the full chain of fixes."
    )


def _install_guard_hook() -> None:
    hook_dir = ".git/hooks"
    hook_path = os.path.join(hook_dir, "pre-commit")

    if not os.path.exists(".git"):
        print_warning("Not a Git repository. Run 'git init' first.")
        return

    os.makedirs(hook_dir, exist_ok=True)
    bash_hook_script = "#!/bin/sh\npython pre_commit_hook.py\n"

    try:
        with open(hook_path, "w", newline="\n") as f:
            f.write(bash_hook_script)

        if os.name == "posix":
            os.chmod(hook_path, 0o755)

        print_success("Pre-Commit Guardian ENABLED. TermiCode will now intercept your git commits.")
    except Exception as e:
        print_error(f"Failed to write Git hook: {e}")


def _remove_guard_hook() -> None:
    hook_path = ".git/hooks/pre-commit"
    if os.path.exists(hook_path):
        os.remove(hook_path)
        print_success("Pre-Commit Guardian DISABLED.")
    else:
        print_warning("Guardian is already disabled.")


def _stream_agent_response(client, current_model, messages, available_tools):
    accumulated_content = ""
    accumulated_tool_calls = {}
    current_tool_id = None
    usage_tokens = 0
    live_panel = None

    try:
        response_stream = client.chat.completions.create(
            model=current_model,
            messages=messages,
            tools=available_tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=1000,
            stream=True,
            stream_options={"include_usage": True},
        )

        for chunk in response_stream:
            usage = getattr(chunk, "usage", None)
            if usage and getattr(usage, "total_tokens", None):
                usage_tokens += usage.total_tokens

            delta = chunk.choices[0].delta

            if delta.content:
                if live_panel is None:
                    live_panel = Live(console=console, refresh_per_second=15, transient=False)
                    live_panel.start()
                accumulated_content += delta.content
                live_panel.update(make_response_panel(accumulated_content))

            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if tool_call.id:
                        current_tool_id = tool_call.id
                        accumulated_tool_calls[current_tool_id] = {
                            "id": current_tool_id,
                            "name": None,
                            "arguments": "",
                        }
                    if tool_call.function and current_tool_id:
                        if tool_call.function.name:
                            accumulated_tool_calls[current_tool_id]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            accumulated_tool_calls[current_tool_id]["arguments"] += tool_call.function.arguments

    finally:
        if live_panel is not None:
            live_panel.stop()

    return accumulated_content, accumulated_tool_calls, usage_tokens


def main():
    load_dotenv()
    print_banner()

    client = validate_startup()
    available_tools = get_available_tools()
    current_model = "qwen/qwen3-coder"
    user_manually_selected_model = False
    session_tokens = 0
    conversation_summary = load_memory_summary()
    project_structure = generate_local_project_map()

    history = load_chat_history()
    if history:
        messages = history
        messages[0]["content"] = build_system_prompt(project_structure, conversation_summary)
        print_startup_info(rehydrated=True, history_file=HISTORY_FILE)
    else:
        messages = [{"role": "system", "content": build_system_prompt(project_structure, conversation_summary)}]
        print_startup_info(rehydrated=False, history_file=HISTORY_FILE)

    while True:
        try:
            user_input = console.input("[bold white]You[/] [dim cyan]>[/] ").strip()

            if not user_input:
                continue

            if user_input.startswith("/heal"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print_warning("Usage: /heal <filename> (e.g., /heal termicode/cli.py)")
                    continue
                target_file = parts[1].strip()
                console.print(f"  [bold magenta]*[/] [dim]Diagnosing[/] [cyan]{target_file}[/] [dim]with Repowise...[/]")
                user_input = _build_heal_prompt(target_file)
                print_success("Diagnosis complete. Handing over to AI Surgeon...")

            elif user_input.startswith("/ripple"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print_warning("Usage: /ripple <your architecture change> (e.g., /ripple change user_id to string)")
                    continue
                user_input = _build_ripple_prompt(parts[1].strip())
                print_success("Orchestration locked. Handing over to AI...")

            elif user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/exit", "/quit"):
                    save_session(messages, conversation_summary)
                    console.print("\n[dim cyan]Session saved. Goodbye.[/]\n")
                    break
                elif cmd == "/clear":
                    console.clear()
                    print_banner()
                elif cmd == "/map":
                    project_structure = generate_local_project_map()
                    messages[0]["content"] = build_system_prompt(project_structure, conversation_summary)
                    print_project_map(project_structure)
                elif cmd.startswith("/undo"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        print_warning("Usage: /undo <filename>")
                    else:
                        result = tools.restore_backup(parts[1].strip())
                        if result.startswith("Success"):
                            print_success(result)
                        else:
                            print_error(result)
                elif cmd == "/tools":
                    print_tool_list(available_tools)
                elif cmd == "/reset":
                    if os.path.exists(HISTORY_FILE):
                        os.remove(HISTORY_FILE)
                    if os.path.exists(MEMORY_FILE):
                        os.remove(MEMORY_FILE)
                    conversation_summary = ""
                    project_structure = generate_local_project_map()
                    messages = [{"role": "system", "content": build_system_prompt(project_structure)}]
                    print_success("History cleared. Fresh session started.")
                elif cmd == "/help":
                    print_help()
                elif cmd.startswith("/model"):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) < 2:
                        status = "OFF (Manual Override)" if user_manually_selected_model else "ON (Dynamic)"
                        console.print(f"  [bold blue]i[/]  Current model is: [cyan]{current_model}[/]")
                        console.print(f"  [dim]Auto-Routing Engine is: {status}[/]")
                    else:
                        new_model = parts[1].strip()
                        if new_model.lower() == "auto":
                            user_manually_selected_model = False
                            current_model = "qwen/qwen-2.5-coder-32b-instruct"
                            print_success("Auto-Routing Engine RE-ENABLED.")
                        elif new_model not in OPENROUTER_MODEL_STATS:
                            console.print(f"  [bold orange3]![/]  Unknown model. Valid options: {', '.join(OPENROUTER_MODEL_STATS.keys())}")
                        else:
                            current_model = new_model
                            user_manually_selected_model = True
                            print_success(f"Brain swapped. Now using: {current_model}")
                elif cmd == "/stats":
                    tokens_used, estimated_cost = get_token_usage(session_tokens, current_model)
                    console.print(f"  [bold magenta]Stats[/]  [dim]Session Tokens:[/] [magenta]{tokens_used:,}[/]")
                    console.print(f"  [bold green]Cost[/]  [dim]Estimated Cost:[/] [green]${estimated_cost:.6f}[/]")
                    console.print(f"  [dim]Model: {current_model}[/]")
                elif cmd == "/doctor":
                    checks = run_doctor()
                    summary = format_doctor_summary(checks)
                    console.print(make_response_panel(summary))
                elif cmd == "/report":
                    try:
                        report_path = generate_repo_report()
                        print_success(f"Repo health report generated: {report_path}")
                    except Exception as e:
                        print_error(f"Failed to generate report: {e}")
                elif cmd == "/guard on":
                    _install_guard_hook()
                elif cmd == "/guard off":
                    _remove_guard_hook()
                else:
                    print_warning(f"Unknown command: [bold]{user_input}[/]. Type [cyan]/help[/] for available commands.")
                continue

            if user_input.lower() in ["exit", "quit"]:
                tokens_used, estimated_cost = get_token_usage(session_tokens, current_model)
                console.print(f"\n[bold green]Session Tokens:[/] {tokens_used:,}")
                console.print(f"[bold green]Estimated Cost:[/] ${estimated_cost:.6f}")
                save_session(messages, conversation_summary)
                console.print("\n[dim cyan]Session saved. Goodbye.[/]\n")
                break

            messages.append({"role": "user", "content": user_input})

            selected_model = route_model(
                user_input,
                current_model,
                OPENROUTER_MODEL_STATS,
                user_manually_selected_model,
                len(messages),
            )
            if selected_model != current_model:
                console.print(f"  [dim cyan]Auto-routed to:[/] [cyan]{selected_model}[/]")
                current_model = selected_model

            max_iterations = 30
            iteration = 0
            recent_tool_calls = []

            with print_thinking_spinner():
                pass

            while iteration < max_iterations:
                iteration += 1
                if len(messages) > 25:
                    console.print("  [bold magenta]*[/] [dim]Compressing older memories...[/]")
                    split_idx = len(messages) - 12

                    while split_idx > 1:
                        msg = messages[split_idx]
                        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
                        if role == "tool":
                            split_idx -= 1
                        else:
                            break

                    dropped_history = messages[1:split_idx]
                    conversation_summary = update_memory_summary(client, conversation_summary, dropped_history)
                    save_memory_summary(conversation_summary)
                    messages = [messages[0]] + messages[split_idx:]

                pruned_messages = prune_context(messages)

                try:
                    accumulated_content, accumulated_tool_calls, usage_tokens = _stream_agent_response(
                        client,
                        current_model,
                        pruned_messages,
                        available_tools,
                    )
                    session_tokens += usage_tokens
                except Exception as api_err:
                    print_api_error(api_err)
                    break

                if accumulated_tool_calls:
                    message_dict = {
                        "role": "assistant",
                        "content": accumulated_content,
                        "tool_calls": [],
                    }
                    for tool_id, tool_data in accumulated_tool_calls.items():
                        message_dict["tool_calls"].append({
                            "id": tool_data["id"],
                            "type": "function",
                            "function": {
                                "name": tool_data["name"],
                                "arguments": tool_data["arguments"],
                            },
                        })
                    messages.append(message_dict)

                    console.print()
                    for tool_call_data in message_dict["tool_calls"]:
                        mock_tool_call = MockToolCall(tool_call_data)
                        call_signature = f"{tool_call_data['function']['name']}:{tool_call_data['function']['arguments']}"

                        if call_signature in recent_tool_calls:
                            print_loop_detected(tool_call_data["function"]["name"])
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_data["id"],
                                "name": tool_call_data["function"]["name"],
                                "content": "SYSTEM GUARD ERROR: Duplicate tool call detected. Stop repeating. Provide your final answer to the user now.",
                            })
                            continue

                        recent_tool_calls.append(call_signature)
                        if len(recent_tool_calls) > 5:
                            recent_tool_calls.pop(0)

                        result = execute_tool(mock_tool_call)
                        result_str = str(result)
                        max_llm_length = 8000
                        if len(result_str) > max_llm_length:
                            result_str = result_str[:max_llm_length] + "\n\n... [SYSTEM WARNING: CONTENT TRUNCATED DUE TO CONTEXT LIMITS]"
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_data["id"],
                            "name": tool_call_data["function"]["name"],
                            "content": result_str,
                        })
                    continue

                console.print()
                messages.append({"role": "assistant", "content": accumulated_content})
                save_session(messages, conversation_summary)
                break

            if iteration >= max_iterations:
                print_warning(f"Max iterations ({max_iterations}) reached. Pausing to prevent infinite loops and token drain.")

        except KeyboardInterrupt:
            save_session(messages, conversation_summary)
            console.print("\n\n[dim cyan]Session saved. Goodbye.[/]\n")
            break
        except Exception as e:
            print_error(f"System Error: {e}")
            save_session(messages, conversation_summary)
            break


if __name__ == "__main__":
    main()
