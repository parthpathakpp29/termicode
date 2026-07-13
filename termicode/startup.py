import os
import subprocess
import sys

from openai import OpenAI

from termicode.ui import console, print_api_error, print_error, print_warning


def validate_startup() -> OpenAI:
    """Validate environment variables and OpenRouter API connectivity before starting."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print_error("OPENROUTER_API_KEY is not set.")
        console.print("  [dim]Get a free key at[/] [link=https://openrouter.ai/keys]openrouter.ai/keys[/]")
        console.print("  [dim]Create a[/] [cyan].env[/] [dim]file in this directory with:[/]")
        console.print("  [white]OPENROUTER_API_KEY=your_key_here[/]\n")
        sys.exit(1)

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://termicode.ai",
                "X-OpenRouter-Title": "TermiCode Nexus",
            },
        )
    except Exception as e:
        print_error(f"Failed to initialize OpenRouter client: {e}")
        sys.exit(1)

    console.print("  [dim]Checking OpenRouter API connection...[/]", end="")
    try:
        client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
        )
        console.print(" [bold green]OK[/]")
    except Exception as e:
        console.print(" [bold red]FAILED[/]\n")
        print_api_error(e)
        console.print(
            "  [dim]Verify your API key, internet connection, and OpenRouter status at[/] "
            "[link=https://status.openrouter.ai]status.openrouter.ai[/]\n"
        )
        sys.exit(1)

    console.print("[dim] Checking Repowise MCP Engine...[/]", end="")
    try:
        subprocess.run(["repowise", "--version"], capture_output=True, check=True, text=True)
        console.print(" [bold green]OK[/]")

        console.print("  [dim]Indexing Codebase (Zero-LLM)...[/]", end="")
        subprocess.run(["repowise", "init", "--index-only", "-y"], capture_output=True)
        console.print("[bold green]OK[/]")

    except FileNotFoundError:
        console.print(" [bold red]FAILED[/]\n")
        print_error("Repowise is not installed. Please open your terminal and run:\npip install repowise")
        sys.exit(1)
    except Exception as e:
        console.print(" [bold red]FAILED[/]\n")
        print_warning(f"Repowise indexing encountered a minor issue: {e}")

    return client
