"""
Security module for GuardCode Agent

Provides risk classification and code scanning capabilities.
"""

from .risk_classifier import RiskLevel, classify_risk

__all__ = ["RiskLevel", "classify_risk"]
