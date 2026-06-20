"""MCP tool: redline rules inspection."""
from src.redlines.hard_rules import HARD_RULES, Severity


def list_hard_rules() -> dict:
    """List all 5 hard redline rules with their definitions.

    Returns:
        dict with rules list — each rule has id, severity, and message.
    """
    return {
        "count": len(HARD_RULES),
        "rules": [
            {
                "id": rule.id,
                "severity": rule.severity.value,
                "message": rule.message,
            }
            for rule in HARD_RULES
        ],
    }


def _severity_label(sev: Severity) -> str:
    """Human-readable severity label."""
    return "REJECT" if sev == Severity.REJECT else "WARN"
