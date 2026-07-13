import subprocess


def run_command_approved(command: str) -> str:
    """Executes a shell command. Caller must obtain user approval first."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=30,
        )

        output = ""
        if result.stdout:
            output += f"--- Standard Output ---\n{result.stdout}\n"
        if result.stderr:
            output += f"--- Errors/Warnings ---\n{result.stderr}\n"

        if not output:
            return "Command executed successfully with no output returned."

        return output

    except subprocess.TimeoutExpired:
        return "Error: The command took too long to execute and timed out (30-second limit)."
    except OSError as e:
        return f"Error executing command: {e}"
