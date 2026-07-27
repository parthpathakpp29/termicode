import subprocess


# A single "pip install <one package>" measured at 41s on an ordinary machine
# in this project's own testing -- 30s left routine installs and test suites,
# exactly what this tool exists to run, timing out before they could finish.
COMMAND_TIMEOUT_SECONDS = 180


def run_command_approved(command: str) -> str:
    """Executes a shell command. Caller must obtain user approval first."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
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
        return f"Error: The command took too long to execute and timed out ({COMMAND_TIMEOUT_SECONDS}-second limit)."
    except OSError as e:
        return f"Error executing command: {e}"
