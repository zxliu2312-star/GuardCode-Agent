"""
Demo script for user confirmation functionality

Run this script to see how the user confirmation prompts work.
"""

from guardcode.security import (
    RiskLevel,
    classify_risk,
    confirm_operation,
    format_blocked_message
)


def demo_safe_operation():
    """Demo a safe operation (no confirmation needed)."""
    print("\n" + "=" * 60)
    print("Demo 1: Safe Operation (read_file)")
    print("=" * 60)
    
    config = {}
    tool_name = "read_file"
    args = {"path": "example.txt"}
    
    risk = classify_risk(tool_name, args, config)
    print(f"\nRisk Level: {risk.value}")
    
    if risk == RiskLevel.SAFE:
        print("✓ Operation is safe, no confirmation needed")
    

def demo_dangerous_operation():
    """Demo a dangerous operation (requires confirmation)."""
    print("\n" + "=" * 60)
    print("Demo 2: Dangerous Operation (delete_file)")
    print("=" * 60)
    
    config = {}
    tool_name = "delete_file"
    args = {"path": "important_file.txt"}
    
    risk = classify_risk(tool_name, args, config)
    print(f"\nRisk Level: {risk.value}")
    
    if risk == RiskLevel.DANGEROUS:
        print("\n⚠️  This operation requires user confirmation")
        confirmed = confirm_operation(tool_name, args)
        
        if confirmed:
            print("Operation would proceed...")
        else:
            print("Operation was cancelled")


def demo_blocked_operation():
    """Demo a blocked operation."""
    print("\n" + "=" * 60)
    print("Demo 3: Blocked Operation (rm -rf /)")
    print("=" * 60)
    
    config = {
        "security": {
            "always_block": [r"rm -rf /"]
        }
    }
    tool_name = "run_command"
    args = {"command": "rm -rf /"}
    
    risk = classify_risk(tool_name, args, config)
    print(f"\nRisk Level: {risk.value}")
    
    if risk == RiskLevel.BLOCKED:
        print("\n🚫 This operation is blocked by security policy")
        print(format_blocked_message(tool_name, args))


def demo_dangerous_command():
    """Demo a dangerous command (requires confirmation)."""
    print("\n" + "=" * 60)
    print("Demo 4: Dangerous Command (pip install)")
    print("=" * 60)
    
    config = {}
    tool_name = "run_command"
    args = {"command": "pip install suspicious-package"}
    
    risk = classify_risk(tool_name, args, config)
    print(f"\nRisk Level: {risk.value}")
    
    if risk == RiskLevel.DANGEROUS:
        print("\n⚠️  This operation requires user confirmation")
        confirmed = confirm_operation(tool_name, args)
        
        if confirmed:
            print("Operation would proceed...")
        else:
            print("Operation was cancelled")


def demo_auto_approved():
    """Demo an auto-approved operation."""
    print("\n" + "=" * 60)
    print("Demo 5: Auto-Approved Operation")
    print("=" * 60)
    
    config = {
        "security": {
            "auto_approve": [r"rm .*\.pyc$"]
        }
    }
    tool_name = "run_command"
    args = {"command": "rm cache.pyc"}
    
    risk = classify_risk(tool_name, args, config)
    print(f"\nCommand: {args['command']}")
    print(f"Risk Level: {risk.value}")
    
    if risk == RiskLevel.SAFE:
        print("✓ Operation is auto-approved by security policy")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("GuardCode Security System Demo")
    print("=" * 60)
    
    # Demo 1: Safe operation
    demo_safe_operation()
    
    # Demo 2: Dangerous operation (interactive)
    demo_dangerous_operation()
    
    # Demo 3: Blocked operation
    demo_blocked_operation()
    
    # Demo 4: Dangerous command (interactive)
    demo_dangerous_command()
    
    # Demo 5: Auto-approved operation
    demo_auto_approved()
    
    print("\n" + "=" * 60)
    print("Demo Complete")
    print("=" * 60 + "\n")
