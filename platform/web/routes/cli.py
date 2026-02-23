"""
CLI API — Execute predefined CLI commands (not full shell)
"""

import logging
import subprocess
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class CLICommand(BaseModel):
    """CLI command request."""

    command: str
    args: list[str] = []


class CLIResponse(BaseModel):
    """CLI command response."""

    success: bool
    output: str
    error: str = ""
    exit_code: int = 0


# Whitelist of allowed CLI commands (security: no arbitrary shell execution)
ALLOWED_COMMANDS = {
    # Git hooks quality tools
    "make": {
        "allowed_args": [
            "install-hooks",
            "install-deps",
            "quality",
            "quality-full",
            "test-coverage",
            "test-skills",
            "test-skills-verbose",
            "load-demo-skills",
            "test",
            "dev",
            "run",
            "stop",
            "logs",
        ],
        "description": "Run Makefile targets",
    },
    # Skills injection
    "python3": {
        "allowed_args": [
            "-m",
            "skills_injection.test_real_missions",
            "-m",
            "skills_injection.load_demo_skills",
            "--version",
            "--help",
        ],
        "description": "Run Python scripts",
    },
    # Git commands (read-only)
    "git": {
        "allowed_args": [
            "status",
            "log",
            "--oneline",
            "-1",
            "-5",
            "-10",
            "branch",
            "diff",
            "--stat",
            "show",
            "HEAD",
            "origin/master",
        ],
        "description": "Git commands (read-only)",
    },
    # Quality tools
    "ruff": {
        "allowed_args": ["check", "format", "--help", "--version", "."],
        "description": "Ruff linter",
    },
    "pytest": {
        "allowed_args": [
            "--version",
            "--help",
            "-v",
            "--cov=platform",
            "--cov=skills_injection",
            "--cov-report=term",
        ],
        "description": "Pytest test runner",
    },
    # System info
    "ls": {
        "allowed_args": ["-la", "-l", "-a", "skills/", "platform/", "scripts/"],
        "description": "List files",
    },
    "pwd": {"allowed_args": [], "description": "Print working directory"},
    "whoami": {"allowed_args": [], "description": "Show current user"},
    # Help
    "help": {"allowed_args": [], "description": "Show available commands"},
}


def validate_command(command: str, args: list[str]) -> tuple[bool, str]:
    """Validate that command and args are allowed."""

    if command == "help":
        return True, ""

    if command not in ALLOWED_COMMANDS:
        return False, f"Command '{command}' not allowed. Use 'help' to see available commands."

    allowed_config = ALLOWED_COMMANDS[command]
    allowed_args_set = set(allowed_config["allowed_args"])

    # Check if all args are in whitelist
    for arg in args:
        if arg not in allowed_args_set:
            return False, f"Argument '{arg}' not allowed for command '{command}'"

    return True, ""


def execute_help() -> str:
    """Generate help text with available commands."""
    help_text = "Available CLI Commands:\n\n"

    for cmd, config in ALLOWED_COMMANDS.items():
        help_text += f"  {cmd:15} - {config['description']}\n"
        if config["allowed_args"]:
            args_preview = ", ".join(config["allowed_args"][:5])
            if len(config["allowed_args"]) > 5:
                args_preview += ", ..."
            help_text += f"                  Args: {args_preview}\n"

    help_text += "\nExamples:\n"
    help_text += "  make install-hooks\n"
    help_text += "  make test-skills\n"
    help_text += "  git status\n"
    help_text += "  ruff check .\n"
    help_text += "  python3 -m skills_injection.test_real_missions\n"

    return help_text


@router.post("/api/cli/execute", response_model=CLIResponse)
async def execute_cli_command(cmd: CLICommand) -> CLIResponse:
    """
    Execute a whitelisted CLI command.

    Security: Only predefined commands with whitelisted args are allowed.
    No arbitrary shell execution.
    """

    # Handle help command
    if cmd.command == "help":
        return CLIResponse(success=True, output=execute_help(), exit_code=0)

    # Route sf commands to SF native commands
    if cmd.command == "sf":
        from .sf_commands import SFCommandRequest, execute_sf_command
        sf_req = SFCommandRequest(command=" ".join(cmd.args), args=[])
        return await execute_sf_command(sf_req)


    # Validate command
    is_valid, error_msg = validate_command(cmd.command, cmd.args)
    if not is_valid:
        return CLIResponse(success=False, output="", error=error_msg, exit_code=1)

    # Build command array (no shell injection possible)
    command_array = [cmd.command] + cmd.args

    try:
        logger.info(f"Executing CLI command: {' '.join(command_array)}")

        # Execute with timeout
        import os

        cwd = "/app" if os.path.exists("/app") else os.getcwd()

        # Ensure proper PATH environment
        env = os.environ.copy()
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get("PATH", "")

        result = subprocess.run(
            command_array,
            capture_output=True,
            text=True,
            timeout=60,  # 60 seconds max
            cwd=cwd,
            env=env,
        )

        return CLIResponse(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            exit_code=result.returncode,
        )

    except subprocess.TimeoutExpired:
        return CLIResponse(
            success=False, output="", error="Command timeout (60s limit exceeded)", exit_code=124
        )
    except FileNotFoundError:
        return CLIResponse(
            success=False,
            output="",
            error=f"Command '{cmd.command}' not found in system",
            exit_code=127,
        )
    except Exception as e:
        logger.error(f"CLI execution error: {e}")
        return CLIResponse(
            success=False, output="", error=f"Execution error: {str(e)}", exit_code=1
        )


@router.get("/api/cli/commands")
async def list_commands() -> dict[str, Any]:
    """List all available CLI commands."""
    return {
        "commands": [
            {
                "name": cmd,
                "description": config["description"],
                "allowed_args": config["allowed_args"],
            }
            for cmd, config in ALLOWED_COMMANDS.items()
        ]
    }
