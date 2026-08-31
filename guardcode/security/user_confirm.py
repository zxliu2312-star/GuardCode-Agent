"""
User confirmation module for dangerous operations

Provides interactive confirmation prompts for operations classified as dangerous.
Uses Rich formatting for clear, colored terminal output.
"""

import json
from typing import Dict, Any

from ..ui.console import console, print_confirm_prompt


def confirm_operation(tool_name: str, args: Dict[str, Any]) -> bool:
    """Prompt user to confirm a dangerous operation.

    Uses Rich formatting for clear visual output.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool

    Returns:
        True if user confirms, False if user rejects

    Examples:
        >>> confirm_operation("delete_file", {"path": "test.txt"})
        ┌──────────────────────────────────────────────────────┐
        │ 🛡 Dangerous Operation                               │
        │ Tool: delete_file                                    │
        │ Arguments:                                           │
        │   path: test.txt                                     │
        └──────────────────────────────────────────────────────┘
        ❓ Confirm: Do you want to proceed? (y/n) y
        True
    """
    # Print Rich formatted confirmation prompt
    print_confirm_prompt(tool_name, args)

    # Prompt user for confirmation
    while True:
        try:
            response = input().strip().lower()

            if response in ['y', 'yes']:
                console.print("[green]✓ Operation approved by user[/green]")
                return True
            elif response in ['n', 'no']:
                console.print("[red]✗ Operation rejected by user[/red]")
                return False
            else:
                console.print("[yellow]Invalid input. Please enter 'y' or 'n'.[/yellow]")
                console.print("[magenta]❓ Confirm:[/magenta] (y/n)", end=" ")
        except EOFError:
            # Handle EOF (e.g., when running in non-interactive mode)
            console.print("\n[red]✗ Cannot confirm in non-interactive mode. Operation rejected.[/red]")
            return False
        except KeyboardInterrupt:
            # Handle Ctrl+C
            console.print("\n[red]✗ Operation cancelled by user (Ctrl+C)[/red]")
            return False


def format_blocked_message(tool_name: str, args: Dict[str, Any], reason: str = "") -> str:
    """
    Format a message for blocked operations.

    Args:
        tool_name: Name of the blocked tool
        args: Arguments that were attempted
        reason: Optional reason for blocking

    Returns:
        Formatted error message
    """
    message_parts = [
        "\n" + "=" * 60,
        "🚫 OPERATION BLOCKED",
        "=" * 60,
        f"\nTool: {tool_name}",
        "\nArguments:"
    ]

    for key, value in args.items():
        if isinstance(value, str) and len(value) > 100:
            display_value = value[:100] + "..."
        else:
            display_value = value
        message_parts.append(f"  {key}: {display_value}")

    if reason:
        message_parts.append(f"\nReason: {reason}")
    else:
        message_parts.append("\nReason: This operation matches a blocked pattern in your security configuration.")

    message_parts.append("\nThis operation cannot be performed for security reasons.")
    message_parts.append("=" * 60 + "\n")

    return "\n".join(message_parts)
