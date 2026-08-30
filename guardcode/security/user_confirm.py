"""
User confirmation module for dangerous operations

Provides interactive confirmation prompts for operations classified as dangerous.
"""

import json
from typing import Dict, Any


def confirm_operation(tool_name: str, args: Dict[str, Any]) -> bool:
    """
    Prompt user to confirm a dangerous operation.
    
    Args:
        tool_name: Name of the tool to execute
        args: Arguments to pass to the tool
        
    Returns:
        True if user confirms, False if user rejects
        
    Examples:
        >>> confirm_operation("delete_file", {"path": "test.txt"})
        ⚠️  DANGEROUS OPERATION DETECTED
        Tool: delete_file
        Arguments:
          path: test.txt
        
        Do you want to proceed? (y/n): y
        True
    """
    # Print warning header
    print("\n" + "=" * 60)
    print("⚠️  DANGEROUS OPERATION DETECTED")
    print("=" * 60)
    
    # Display tool name
    print(f"\nTool: {tool_name}")
    
    # Display arguments in a readable format
    print("\nArguments:")
    for key, value in args.items():
        # Format the value nicely
        if isinstance(value, str) and len(value) > 100:
            # Truncate long strings
            display_value = value[:100] + "..."
        elif isinstance(value, (dict, list)):
            # Pretty print complex types
            display_value = json.dumps(value, indent=2, ensure_ascii=False)
        else:
            display_value = value
        
        print(f"  {key}: {display_value}")
    
    print("\n" + "-" * 60)
    
    # Prompt user for confirmation
    while True:
        try:
            response = input("Do you want to proceed? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                print("✓ Operation approved by user")
                print("=" * 60 + "\n")
                return True
            elif response in ['n', 'no']:
                print("✗ Operation rejected by user")
                print("=" * 60 + "\n")
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
        except EOFError:
            # Handle EOF (e.g., when running in non-interactive mode)
            print("\n✗ Cannot confirm in non-interactive mode. Operation rejected.")
            print("=" * 60 + "\n")
            return False
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\n✗ Operation cancelled by user (Ctrl+C)")
            print("=" * 60 + "\n")
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
