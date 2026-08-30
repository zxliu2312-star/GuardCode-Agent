"""
Security module for GuardCode Agent

Provides risk classification and code scanning capabilities.
"""

from .risk_classifier import RiskLevel, classify_risk
from .user_confirm import confirm_operation, format_blocked_message

__all__ = [
    "RiskLevel",
    "classify_risk",
    "confirm_operation",
    "format_blocked_message",
]
