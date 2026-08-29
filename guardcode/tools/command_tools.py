"""Command execution tool restricted to the initialized workspace."""

import subprocess
from typing import Any

from ..workspace import get_workspace
from .base import register_tool


@register_tool(
    name="run_command",
    description="Run a shell command in the workspace and return its output",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute in the workspace"
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default: 30)"
            }
        },
        "required": ["command"]
    }
)
def run_command(command: str, timeout: int = 30) -> dict[str, Any]:
    """Run a command within the initialized workspace."""
    if timeout <= 0:
        return {
            "success": False,
            "result": "",
            "error": "Timeout must be greater than zero",
            "exit_code": None,
        }

    try:
        completed = subprocess.run(
            command,
            cwd=get_workspace().workspace_root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "success": False,
            "result": error.stdout or "",
            "error": error.stderr or f"Command timed out after {timeout} seconds",
            "exit_code": None,
        }
    except OSError as error:
        return {
            "success": False,
            "result": "",
            "error": f"Failed to run command: {error}",
            "exit_code": None,
        }

    return {
        "success": completed.returncode == 0,
        "result": completed.stdout,
        "error": completed.stderr,
        "exit_code": completed.returncode,
    }
