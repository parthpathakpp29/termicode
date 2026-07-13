import ast

from rich import box
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


console = Console()

CLR_TERMICODE = "bold cyan"
CLR_USER = "bold white"
CLR_TOOL = "bold yellow"
CLR_RESULT = "dim white"
CLR_WARN = "bold orange3"
CLR_ERROR = "bold red"
CLR_SUCCESS = "bold green"
CLR_GUARD = "bold magenta"
CLR_INFO = "bold blue"


def print_banner():
    """Prints the TermiCode startup banner."""
    banner_text = Text()
    banner_text.append("  TERMICODE", style="bold cyan")
    banner_text.append("  -  AI Coding Assistant", style="dim white")
    banner_text.append("  -  OpenRouter-Powered", style="dim cyan")
    console.print(Panel(
        banner_text,
        border_style="cyan",
        padding=(0, 2),
        box=box.DOUBLE_EDGE,
    ))
    console.print()


def print_startup_info(rehydrated: bool, history_file: str):
    """Prints session startup status."""
    if rehydrated:
        console.print(f"  [bold green]*[/] [dim]Session restored from[/] [cyan]{history_file}[/]")
    else:
        console.print("  [bold green]*[/] [dim]Fresh session started.[/]")
    console.print(
        "  [dim]Type your message and press Enter.  "
        "Type[/] [bold cyan]/help[/] [dim]for commands.[/]"
    )
    console.print(Rule(style="dim cyan"))
    console.print()


def print_help():
    """Prints available slash commands."""
    table = Table(
        title="Available Commands",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Command", style="bold white", width=20)
    table.add_column("Description", style="dim white")
    table.add_row("/help", "Show this help menu")
    table.add_row("/clear", "Clear terminal screen")
    table.add_row("/map", "Print the current project file map")
    table.add_row("/tools", "List all tools available to TermiCode")
    table.add_row("/heal <file>", "Autonomously diagnose and refactor a specific file")
    table.add_row("/undo <file>", "Instantly roll back a file to its most recent backup")
    table.add_row("/reset", "Wipe chat history and start fresh")
    table.add_row("/exit", "Save session and quit")
    table.add_row("/model", "Shows which model is in use")
    table.add_row("/stats", "Show token usage")
    table.add_row("/doctor", "Check local setup, dependencies, Git, and Repowise")
    table.add_row("/report", "Generate a Markdown repo health report")
    table.add_row("/guard on|off", "Toggle the Git pre-commit interceptor")
    table.add_row("/ripple <prompt>", "Execute an architecture change and fix cascading dependencies")
    console.print(table)
    console.print()


def print_project_map(project_map: str):
    """Renders the project map in a panel."""
    console.print(Panel(
        project_map,
        title="[bold cyan]Project Map[/]",
        border_style="cyan",
        box=box.ROUNDED,
    ))


def print_tool_list(available_tools: list):
    """Renders the available tools as a table."""
    table = Table(
        title="TermiCode Tools",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
    )
    table.add_column("Tool Name", style="bold white", width=20)
    table.add_column("Description", style="dim white")
    for tool in available_tools:
        fn = tool["function"]
        table.add_row(fn["name"], fn["description"][:80])
    console.print(table)
    console.print()


def print_thinking_spinner() -> Live:
    """Returns a Live spinner context manager for the thinking state."""
    spinner = Spinner("dots2", text=Text(" TermiCode is thinking...", style="dim cyan"))
    return Live(spinner, console=console, refresh_per_second=12, transient=True)


def print_termicode_response(content: str):
    """Renders TermiCode's final text response as rich Markdown."""
    md = Markdown(content)
    console.print(Panel(
        md,
        title="[bold cyan]TermiCode[/]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    ))


def print_tool_triggered(name: str, args: dict):
    """Renders the tool call announcement."""
    args = args or {}
    args_text = "  ".join([f"[dim]{k}:[/] [white]{escape(str(v)[:80])}[/]" for k, v in args.items()])
    console.print(f"  [bold yellow]*[/]  [yellow]{name}[/]  [dim]->[/]  {args_text}")


def print_tool_result(result: str):
    """Renders the tool result in a compact panel."""
    result_str = str(result)
    if len(result_str) > 300:
        console.print(Panel(
            result_str[:2000] + ("\n[dim]... (truncated)[/]" if len(result_str) > 2000 else ""),
            title="[dim]Tool Result[/]",
            border_style="dim yellow",
            box=box.SIMPLE_HEAVY,
            padding=(0, 1),
        ))
    else:
        console.print(f"  [dim yellow]->[/] [dim]{result_str}[/]")


def print_token_guard(before: int, after: int):
    """Renders the token guard pruning notice."""
    console.print(
        f"  [bold magenta]*[/] [dim]Token Guard:[/] "
        f"[magenta]{before}[/] [dim]->[/] [magenta]{after}[/] [dim]messages[/]"
    )


def print_loop_detected(tool_name: str):
    """Renders a loop detection warning."""
    console.print(f"  [bold orange3]![/]  [orange3]Loop detected[/] [dim]on[/] [yellow]{tool_name}[/]")


def print_warning(msg: str):
    console.print(f"  [bold orange3]![/]  {msg}")


def print_error(msg: str):
    console.print("\n  [bold red]x[/]  ", end="")
    console.print(msg, markup=False)


def print_success(msg: str):
    console.print(f"  [bold green]OK[/]  {msg}")


def print_api_error(err):
    err_str = str(err)

    if "429" in err_str and "Rate limit reached" in err_str:
        try:
            dict_str = err_str.split(" - ", 1)[1]
            err_dict = ast.literal_eval(dict_str)
            clean_msg = err_dict.get("error", {}).get("message", err_str)
            console.print(Panel(
                f"[bold orange3]Rate Limit Exceeded (429)[/]\n\n[white]{clean_msg}[/]",
                title="[bold red]API Error[/]",
                border_style="red",
                box=box.ROUNDED,
            ))
            return
        except Exception:
            pass

    console.print(Panel(
        err_str,
        title="[bold red]API Error[/]",
        border_style="red",
        box=box.ROUNDED,
    ))


def print_security_alert(action: str, file_path: str) -> bool:
    """Renders a security confirmation prompt and returns bool approval."""
    console.print(Panel(
        f"[bold white]{action}[/]\n[dim]File:[/] [cyan]{file_path}[/]",
        title="[bold red]Security Alert[/]",
        border_style="red",
        box=box.HEAVY,
        padding=(0, 2),
    ))
    answer = console.input("  [bold]Allow? ([green]y[/]/[red]N[/]):[/] ").strip().lower()
    return answer == "y"


def print_command_alert(command: str) -> bool:
    """Renders a terminal command confirmation prompt."""
    console.print(Panel(
        f"[bold white]{command}[/]",
        title="[bold red]Terminal Command Request[/]",
        border_style="red",
        box=box.HEAVY,
        padding=(0, 2),
    ))
    answer = console.input("  [bold]Execute? ([green]y[/]/[red]N[/]):[/] ").strip().lower()
    return answer == "y"


def print_backup_notice(backup_path: str):
    console.print(f"  [dim green]-> Snapshot:[/] [dim]{backup_path}[/]")


def make_response_panel(content: str) -> Panel:
    return Panel(
        Markdown(content),
        title="[bold cyan]TermiCode[/]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
