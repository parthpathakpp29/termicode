import json
import os
import shutil

from dotenv import load_dotenv
from openai import RateLimitError
from rich.live import Live

from termicode import catalog, repowise, tools
from termicode.doctor import format_doctor_summary, run_doctor
from termicode.models import get_token_usage, next_fallback_model, route_model
from termicode.project import generate_local_project_map
from termicode.prompts import build_system_prompt, get_available_tools
from termicode.report import generate_repo_report
from termicode.session import (
    history_path,
    load_chat_history,
    load_memory_summary,
    memory_path,
    migrate_legacy_session,
    prune_context,
    save_memory_summary,
    save_session,
    update_memory_summary,
)
from termicode.startup import validate_startup
from termicode.tool_executor import MockToolCall, approval_state, execute_tool
from termicode.ui import (
    console,
    make_response_panel,
    print_api_error,
    print_banner,
    print_cancelled,
    print_exit_hint,
    print_help,
    print_loop_detected,
    print_project_map,
    print_startup_info,
    print_success,
    print_rate_limit_exhausted,
    print_rate_limit_fallback,
    print_thinking_spinner,
    print_tool_list,
    print_truncation_warning,
    print_warning,
    print_error,
)


# Ceiling on a single model response. Large enough to write a real file in one
# turn; low enough that even small free-tier models accept it. Per-model
# ceilings would belong in models.py.
MAX_COMPLETION_TOKENS = 4096

TRUNCATED_TOOL_CALL_NOTICE = (
    "SYSTEM ERROR: Your tool call was cut off because it exceeded the output limit "
    f"of {MAX_COMPLETION_TOKENS} tokens, so its arguments were incomplete and it was not executed. "
    "Do not retry the same call. Split the work into smaller pieces: write or edit "
    "one section at a time, using several 'edit_file' calls instead of one large one."
)


CANCELLED_TOOL_RESULT = "Action cancelled by the user before it finished."


def _close_unanswered_tool_calls(messages: list) -> int:
    """Answer any tool calls left dangling by an interrupted turn.

    Every tool_call the model makes must be matched by a tool message, or the
    next request is rejected. Cancelling mid-turn leaves that contract broken,
    so the missing results are filled in as cancellations.

    Results are appended rather than the turn being truncated: tools that ran
    before the interrupt may already have changed files on disk, and dropping
    that record would leave the model reasoning against a history that no
    longer matches reality. Returns how many results were synthesised.
    """
    last_call_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, dict):
            continue
        if message.get("role") == "assistant" and message.get("tool_calls"):
            last_call_index = index
            break

    if last_call_index is None:
        return 0

    answered = {
        message.get("tool_call_id")
        for message in messages[last_call_index + 1:]
        if isinstance(message, dict) and message.get("role") == "tool"
    }

    synthesised = 0
    for tool_call in messages[last_call_index]["tool_calls"]:
        if tool_call["id"] in answered:
            continue
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_call["function"]["name"],
            "content": CANCELLED_TOOL_RESULT,
        })
        synthesised += 1

    return synthesised


def _has_complete_arguments(tool_call_data: dict) -> bool:
    """True when a streamed tool call's arguments survived as parseable JSON.

    A response cut off at the token limit leaves the final call's JSON unclosed,
    which is what distinguishes a genuinely truncated call from one that merely
    happened to finish on the limit.
    """
    arguments = tool_call_data["function"]["arguments"]
    if not arguments:
        return True

    try:
        json.loads(arguments)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def _require_repowise(feature: str, repowise_available: bool) -> bool:
    """Return True when `feature` can run, warning with install steps if not."""
    if repowise_available:
        return True

    print_warning(f"{feature} requires Repowise, which is not installed.")
    console.print(f"  [dim]Enable it with:[/] [cyan]{repowise.INSTALL_HINT}[/]")
    console.print("  [dim]Then run[/] [cyan]/doctor[/] [dim]to re-check without restarting.[/]")
    return False


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

    # The hook shells out to an installed console script rather than a bundled
    # file, so it works from any project regardless of the current directory
    # or which "python" (if any) is on PATH. If it is not resolvable, the hook
    # would fail on every commit exactly like the version this replaced did.
    if shutil.which("termicode-guard-check") is None:
        print_error(
            "Could not find 'termicode-guard-check' on PATH. "
            "Reinstall TermiCode (pip install -e . or pip install termicode-ai) and try again."
        )
        return

    os.makedirs(hook_dir, exist_ok=True)
    bash_hook_script = "#!/bin/sh\ntermicode-guard-check\n"

    try:
        with open(hook_path, "w", newline="\n") as f:
            f.write(bash_hook_script)

        if os.name == "posix":
            os.chmod(hook_path, 0o755)

        print_success("Pre-Commit Guardian ENABLED. TermiCode will now intercept your git commits.")
        print_success("(Re-running this also repairs a hook installed by an older TermiCode version.)")
    except OSError as e:
        print_error(f"Failed to write Git hook: {e}")


def _remove_guard_hook() -> None:
    hook_path = ".git/hooks/pre-commit"
    if os.path.exists(hook_path):
        os.remove(hook_path)
        print_success("Pre-Commit Guardian DISABLED.")
    else:
        print_warning("Guardian is already disabled.")


def _stream_agent_response(client, current_model, messages, available_tools):
    """Stream one model turn.

    Returns (content, tool_calls, usage_tokens, finish_reason). The finish
    reason is what tells the caller the response was cut off at the output
    limit rather than completed.
    """
    accumulated_content = ""
    tool_calls_by_index = {}
    usage_tokens = 0
    finish_reason = None
    live_panel = None
    spinner = print_thinking_spinner()
    spinner_running = False

    def stop_spinner():
        """Rich allows only one Live at a time, so this must run before any
        response panel starts."""
        nonlocal spinner_running
        if spinner_running:
            spinner.stop()
            spinner_running = False

    try:
        spinner.start()
        spinner_running = True

        response_stream = client.chat.completions.create(
            model=current_model,
            messages=messages,
            tools=available_tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=MAX_COMPLETION_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )

        for chunk in response_stream:
            usage = getattr(chunk, "usage", None)
            if usage and getattr(usage, "total_tokens", None):
                usage_tokens += usage.total_tokens

            # The final usage chunk carries no choices; skip it rather than
            # letting the index below raise and discard the whole response.
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

            delta = choice.delta

            if delta.content:
                if live_panel is None:
                    stop_spinner()
                    live_panel = Live(console=console, refresh_per_second=15, transient=False)
                    live_panel.start()
                accumulated_content += delta.content
                live_panel.update(make_response_panel(accumulated_content))

            if delta.tool_calls:
                stop_spinner()
                for tool_call in delta.tool_calls:
                    # Tracked by index, not id: once a parallel tool call's
                    # first chunk introduces its id, every later continuation
                    # chunk for it omits id/name entirely and carries only
                    # index plus an argument fragment. Keying on "whichever
                    # id was seen most recently" corrupted interleaved
                    # parallel tool calls -- a later fragment for call 0
                    # would land on call 1's entry once call 1's id had been
                    # seen more recently than call 0's.
                    slot = tool_calls_by_index.setdefault(
                        tool_call.index, {"id": None, "name": None, "arguments": ""}
                    )
                    if tool_call.id:
                        slot["id"] = tool_call.id
                    if tool_call.function:
                        if tool_call.function.name:
                            slot["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            slot["arguments"] += tool_call.function.arguments

    finally:
        stop_spinner()
        if live_panel is not None:
            live_panel.stop()

    accumulated_tool_calls = {slot["id"]: slot for slot in tool_calls_by_index.values() if slot["id"]}

    return accumulated_content, accumulated_tool_calls, usage_tokens, finish_reason


def _stream_with_fallback(client, current_model, messages, available_tools, user_manually_selected, candidates):
    """Calls _stream_agent_response, retrying with a different free model on a 429.

    Only openai.RateLimitError triggers a retry; every other failure surfaces
    exactly as _stream_agent_response raised it. The chain length is not fixed
    — it continues until next_fallback_model has no untried candidate left to
    offer, which is what naturally bounds it, since a model is never tried twice.
    `candidates` is the same live, ranked free-tier list used for routing this
    turn (see catalog.free_coding_candidate_ids), not a separate lookup.

    Bypassed entirely when the user picked the model manually: silently
    downgrading an explicit choice is not this feature's job.

    Returns the same 4-tuple as _stream_agent_response, plus the model that
    actually produced it — current_model in the caller should be updated to
    it, so the session does not immediately re-hit the same limited model.
    """
    if user_manually_selected:
        content, tool_calls, usage_tokens, finish_reason = _stream_agent_response(
            client, current_model, messages, available_tools
        )
        return content, tool_calls, usage_tokens, finish_reason, current_model

    tried = set()
    model_to_try = current_model

    while True:
        tried.add(model_to_try)
        try:
            content, tool_calls, usage_tokens, finish_reason = _stream_agent_response(
                client, model_to_try, messages, available_tools
            )
            return content, tool_calls, usage_tokens, finish_reason, model_to_try
        except RateLimitError:
            fallback = next_fallback_model(tried, candidates)
            if fallback is None:
                raise
            print_rate_limit_fallback(model_to_try, fallback)
            model_to_try = fallback


def main():
    load_dotenv()
    print_banner()

    client = validate_startup()
    repowise_available = repowise.is_available()
    available_tools = get_available_tools(repowise_available)
    # Top-ranked live, free, tool-calling-capable model -- never a hardcoded
    # id. free_coding_candidate_ids() always returns at least the built-in
    # last-resort pair, so this list is never empty.
    current_model = catalog.free_coding_candidate_ids()[0]
    user_manually_selected_model = False
    session_tokens = 0

    migrated_to = migrate_legacy_session()
    if migrated_to:
        print_success(f"Moved this project's session files out of the repo, into {migrated_to}")

    conversation_summary = load_memory_summary()
    project_structure = generate_local_project_map()

    history = load_chat_history()
    if history:
        messages = history
        messages[0]["content"] = build_system_prompt(project_structure, conversation_summary, repowise_available)
        print_startup_info(rehydrated=True, history_file=history_path())
    else:
        messages = [{"role": "system", "content": build_system_prompt(project_structure, conversation_summary, repowise_available)}]
        print_startup_info(rehydrated=False, history_file=history_path())

    exit_armed = False

    while True:
        try:
            try:
                user_input = console.input("[bold white]You[/] [dim cyan]>[/] ").strip()
            except KeyboardInterrupt:
                # Ctrl+C at an idle prompt is ambiguous, so make leaving
                # deliberate: it only exits when pressed twice in a row.
                if exit_armed:
                    raise
                exit_armed = True
                print_exit_hint()
                continue
            except EOFError:
                console.print()
                raise KeyboardInterrupt

            exit_armed = False

            if not user_input:
                continue

            if user_input.startswith("/heal"):
                if not _require_repowise("/heal", repowise_available):
                    continue
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
                    messages[0]["content"] = build_system_prompt(project_structure, conversation_summary, repowise_available)
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
                    if os.path.exists(history_path()):
                        os.remove(history_path())
                    if os.path.exists(memory_path()):
                        os.remove(memory_path())
                    conversation_summary = ""
                    project_structure = generate_local_project_map()
                    messages = [{"role": "system", "content": build_system_prompt(project_structure, "", repowise_available)}]
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
                            current_model = catalog.free_coding_candidate_ids()[0]
                            print_success(f"Auto-Routing Engine RE-ENABLED. Now using: {current_model}")
                        elif new_model.lower() == "budget":
                            budget_ids = catalog.budget_candidate_ids()
                            if not budget_ids:
                                print_warning("No paid model currently qualifies for the budget tier.")
                            else:
                                current_model = budget_ids[0]
                                user_manually_selected_model = True
                                print_success(f"Budget tier selected. Now using: {current_model}")
                        elif new_model not in catalog.all_known_model_ids():
                            console.print(
                                f"  [bold orange3]![/]  Unknown model '{new_model}'. "
                                "Run [cyan]/model[/] to see the current model, "
                                "or [cyan]/model budget[/] / [cyan]/model auto[/] for a live pick."
                            )
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
                    repowise.reset_cache()
                    checks = run_doctor()
                    summary = format_doctor_summary(checks)
                    console.print(make_response_panel(summary))

                    # Re-detecting can flip availability if the user just installed
                    # Repowise. Keep the prompt and the tool schema in step with it.
                    if repowise.is_available() != repowise_available:
                        repowise_available = repowise.is_available()
                        available_tools = get_available_tools(repowise_available)
                        messages[0]["content"] = build_system_prompt(
                            project_structure, conversation_summary, repowise_available
                        )
                        state = "enabled" if repowise_available else "disabled"
                        print_success(f"Repowise {state}. Tools and instructions updated for this session.")
                elif cmd == "/report":
                    if not _require_repowise("/report", repowise_available):
                        continue
                    try:
                        report_path = generate_repo_report()
                        print_success(f"Repo health report generated: {report_path}")
                    except Exception as e:
                        print_error(f"Failed to generate report: {e}")
                elif cmd == "/guard on":
                    if not _require_repowise("/guard", repowise_available):
                        continue
                    _install_guard_hook()
                elif cmd == "/guard off":
                    _remove_guard_hook()
                elif cmd == "/approve":
                    state = "ON" if approval_state.auto_approve_files else "OFF"
                    console.print(f"  [bold blue]i[/]  Auto-approve for file writes/edits/deletes is: {state}")
                    console.print("  [dim]run_command always prompts, regardless of this setting.[/]")
                elif cmd == "/approve on":
                    approval_state.enable()
                    print_success("Auto-approve ENABLED for file writes, edits, and deletes.")
                elif cmd == "/approve off":
                    approval_state.disable()
                    print_success("Auto-approve DISABLED. TermiCode will prompt for file changes again.")
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

            # Fetched once per turn (cache-first, so this is normally instant)
            # and reused below for the 429 fallback chain, so routing and
            # fallback are working from the exact same live ranking.
            candidates = catalog.free_coding_candidate_ids()

            selected_model = route_model(
                user_input,
                current_model,
                candidates,
                user_manually_selected_model,
                len(messages),
            )
            if selected_model != current_model:
                console.print(f"  [dim cyan]Auto-routed to:[/] [cyan]{selected_model}[/]")
                current_model = selected_model

            max_iterations = 30
            iteration = 0
            recent_tool_calls = []

            try:
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
                        accumulated_content, accumulated_tool_calls, usage_tokens, finish_reason, current_model = _stream_with_fallback(
                            client,
                            current_model,
                            pruned_messages,
                            available_tools,
                            user_manually_selected_model,
                            candidates,
                        )
                        session_tokens += usage_tokens
                    except RateLimitError as rate_limit_err:
                        print_rate_limit_exhausted()
                        print_api_error(rate_limit_err)
                        break
                    except Exception as api_err:
                        print_api_error(api_err)
                        break

                    was_truncated = finish_reason == "length"

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
                            # Only the last call in a truncated turn can be incomplete,
                            # and only if its arguments no longer parse. Earlier calls
                            # arrived in full and still run.
                            if (
                                was_truncated
                                and tool_call_data is message_dict["tool_calls"][-1]
                                and not _has_complete_arguments(tool_call_data)
                            ):
                                print_warning(
                                    f"[bold]{tool_call_data['function']['name']}[/] was cut off at the "
                                    f"{MAX_COMPLETION_TOKENS:,}-token limit and was not executed. "
                                    "Asking the model to split the work."
                                )
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call_data["id"],
                                    "name": tool_call_data["function"]["name"],
                                    "content": TRUNCATED_TOOL_CALL_NOTICE,
                                })
                                continue

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
                    if was_truncated:
                        print_truncation_warning(MAX_COMPLETION_TOKENS)
                    messages.append({"role": "assistant", "content": accumulated_content})
                    save_session(messages, conversation_summary)
                    break

            except KeyboardInterrupt:
                # Repair before anything else: an unanswered tool call makes
                # every later request invalid, so the session would be dead.
                pending = _close_unanswered_tool_calls(messages)
                save_session(messages, conversation_summary)
                print_cancelled(pending)
                continue

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
