"""
Risk classification system for GuardCode Agent

Classifies tool operations into risk levels (SAFE, DANGEROUS, BLOCKED)
based on configurable patterns and rules.
"""

import re
from enum import Enum
from typing import Dict, Any, List


class RiskLevel(Enum):
    """Risk level classification for tool operations."""
    SAFE = "safe"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


# Safe command patterns - commands that are generally safe to auto-approve
SAFE_PATTERNS: List[re.Pattern] = [
    # Read-only operations
    re.compile(r"^ls\s+"),
    re.compile(r"^dir\s+"),
    re.compile(r"^cat\s+"),
    re.compile(r"^head\s+"),
    re.compile(r"^tail\s+"),
    re.compile(r"^grep\s+"),
    re.compile(r"^find\s+"),
    re.compile(r"^git\s+status"),
    re.compile(r"^git\s+log"),
    re.compile(r"^git\s+diff"),
    re.compile(r"^git\s+show"),
    re.compile(r"^git\s+branch"),
    
    # Info commands
    re.compile(r"^pwd$"),
    re.compile(r"^whoami$"),
    re.compile(r"^echo\s+"),
    re.compile(r"^env$"),
    re.compile(r"^which\s+"),
    re.compile(r"^where\s+"),
    
    # Python execution (non-destructive)
    re.compile(r"^python\s+.*\.py$"),
    re.compile(r"^python3\s+.*\.py$"),
    re.compile(r"^python\s+-m\s+pytest"),
    re.compile(r"^pytest(\s+|$)"),
    re.compile(r"^python\s+-m\s+unittest"),
    
    # Package managers (read-only)
    re.compile(r"^pip\s+list"),
    re.compile(r"^pip\s+show"),
    re.compile(r"^npm\s+list"),
    re.compile(r"^npm\s+ls"),
    
    # Build and test commands
    re.compile(r"^make\s+test"),
    re.compile(r"^npm\s+test"),
    re.compile(r"^npm\s+run\s+test"),
    re.compile(r"^cargo\s+test"),
    re.compile(r"^go\s+test"),
]


# Dangerous command patterns - commands that require user confirmation
DANGEROUS_PATTERNS: List[re.Pattern] = [
    # File deletion
    re.compile(r"\brm\s+"),
    re.compile(r"\bdel\s+"),
    re.compile(r"\brmdir\s+"),
    re.compile(r"Remove-Item"),
    
    # Force/recursive deletion
    re.compile(r"-rf\b"),
    re.compile(r"-fr\b"),
    re.compile(r"--force"),
    re.compile(r"-Force"),
    re.compile(r"-Recurse"),
    
    # Wildcards with deletion
    re.compile(r"rm.*\*"),
    re.compile(r"del.*\*"),
    
    # System modification
    re.compile(r"\bsudo\s+"),
    re.compile(r"\bsu\s+"),
    re.compile(r"^chmod\s+"),
    re.compile(r"^chown\s+"),
    
    # Process control
    re.compile(r"\bkill\s+"),
    re.compile(r"\bkillall\s+"),
    re.compile(r"Stop-Process"),
    
    # Network operations
    re.compile(r"\bcurl\s+.*-X\s+(POST|PUT|DELETE)"),
    re.compile(r"\bwget\s+"),
    re.compile(r"Invoke-WebRequest.*-Method\s+(Post|Put|Delete)"),
    
    # Package installation/removal
    re.compile(r"^pip\s+install"),
    re.compile(r"^pip\s+uninstall"),
    re.compile(r"^npm\s+install"),
    re.compile(r"^npm\s+uninstall"),
    re.compile(r"^apt-get\s+install"),
    re.compile(r"^apt-get\s+remove"),
    re.compile(r"^yum\s+install"),
    re.compile(r"^yum\s+remove"),
    
    # Git destructive operations
    re.compile(r"^git\s+reset\s+--hard"),
    re.compile(r"^git\s+clean\s+-.*f"),
    re.compile(r"^git\s+push\s+.*--force"),
    re.compile(r"^git\s+branch\s+-D"),
    
    # Database operations
    re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    
    # Shell redirection that overwrites
    re.compile(r">\s*[^>]"),  # Single > (overwrite)
    
    # Format/partition operations
    re.compile(r"\bformat\s+"),
    re.compile(r"\bfdisk\s+"),
    re.compile(r"\bmkfs\s+"),
]


def classify_risk(
    tool_name: str,
    args: Dict[str, Any],
    config: Dict[str, Any]
) -> RiskLevel:
    """
    Classify the risk level of a tool operation.
    
    Args:
        tool_name: Name of the tool to execute
        args: Arguments passed to the tool
        config: Configuration dictionary containing security settings
        
    Returns:
        RiskLevel indicating the classification
        
    Examples:
        >>> classify_risk("read_file", {"path": "test.txt"}, {})
        RiskLevel.SAFE
        
        >>> classify_risk("delete_file", {"path": "test.txt"}, {})
        RiskLevel.DANGEROUS
        
        >>> classify_risk("run_command", {"command": "rm -rf /"}, {})
        RiskLevel.BLOCKED
    """
    # Extract security configuration
    security_config = config.get("security", {})
    always_block = security_config.get("always_block", [])
    auto_approve = security_config.get("auto_approve", [])
    
    # Check always_block patterns first
    if tool_name == "run_command":
        command = args.get("command", "")
        
        # Check if command matches any always_block pattern
        for pattern in always_block:
            if _matches_pattern(command, pattern):
                return RiskLevel.BLOCKED
        
        # Check if command matches any auto_approve pattern
        for pattern in auto_approve:
            if _matches_pattern(command, pattern):
                return RiskLevel.SAFE
        
        # Check dangerous patterns
        for dangerous_pattern in DANGEROUS_PATTERNS:
            if dangerous_pattern.search(command):
                return RiskLevel.DANGEROUS
        
        # Check safe patterns
        for safe_pattern in SAFE_PATTERNS:
            if safe_pattern.search(command):
                return RiskLevel.SAFE
        
        # Default to DANGEROUS for unknown commands (conservative)
        return RiskLevel.DANGEROUS
    
    elif tool_name == "delete_file":
        # File deletion is always dangerous
        return RiskLevel.DANGEROUS
    
    elif tool_name in ["read_file", "list_files"]:
        # Read-only operations are safe
        return RiskLevel.SAFE
    
    elif tool_name == "write_file":
        # File writing is generally safe, but could be dangerous
        # in some contexts (e.g., overwriting important files)
        # For now, classify as SAFE since we're within workspace
        return RiskLevel.SAFE
    
    else:
        # Unknown tools default to DANGEROUS (conservative)
        return RiskLevel.DANGEROUS


def _matches_pattern(text: str, pattern: str) -> bool:
    """
    Check if text matches a pattern (supports both regex and simple strings).
    
    Args:
        text: Text to match against
        pattern: Pattern to match (string or regex pattern)
        
    Returns:
        True if pattern matches, False otherwise
    """
    try:
        # Try as regex first
        regex = re.compile(pattern)
        return regex.search(text) is not None
    except re.error:
        # Fall back to simple substring match
        return pattern in text
