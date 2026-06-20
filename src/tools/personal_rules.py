"""MCP tool: personal redline rule management.

Users can add/remove/list/clear personal investment rules via MCP.
Rules persist in-memory for the lifetime of the server process.
"""
from decimal import Decimal, InvalidOperation

from src.redlines.personal_rules import PersonalRule, PersonalRuleSet

# Module-level state — shared across all MCP calls within this server instance.
_ruleset = PersonalRuleSet()


def manage_personal_rules(
    action: str,
    rule_id: str = "",
    description: str = "",
    fund_types_blacklist: str = "",
    max_single_position: float | None = None,
    min_fund_size: float | None = None,
) -> dict:
    """Add, remove, list, or clear personal investment rules.

    Args:
        action: "add" | "remove" | "list" | "clear"
        rule_id: Unique rule identifier (required for add/remove).
        description: Human-readable rule description.
        fund_types_blacklist: Comma-separated fund types to block, e.g. "stock,mixed".
        max_single_position: Max CNY per fund (None = no limit).
        min_fund_size: Min fund net asset value in CNY (None = no limit).
    """
    if action == "list":
        return _list_rules()

    if action == "clear":
        _ruleset.clear()
        return {"status": "ok", "message": "All personal rules cleared.", "active_count": 0}

    if action == "add":
        if not rule_id:
            return {"error": "rule_id is required for action='add'."}
        return _add_rule(rule_id, description, fund_types_blacklist, max_single_position, min_fund_size)

    if action == "remove":
        if not rule_id:
            return {"error": "rule_id is required for action='remove'."}
        _ruleset.remove(rule_id)
        return {"status": "ok", "message": f"Rule '{rule_id}' removed.", "active_count": len(_ruleset.active)}

    return {"error": f"Unknown action: {action!r}. Use 'add', 'remove', 'list', or 'clear'."}


def _list_rules() -> dict:
    rules = _ruleset.active
    return {
        "active_count": len(rules),
        "rules": [
            {
                "id": r.id,
                "description": r.description,
                "fund_types_blacklist": sorted(r.fund_types_blacklist),
                "max_single_position": float(r.max_single_position) if r.max_single_position is not None else None,
                "min_fund_size": float(r.min_fund_size) if r.min_fund_size is not None else None,
            }
            for r in rules
        ],
    }


def _add_rule(rule_id, description, fund_types_blacklist, max_single_position, min_fund_size) -> dict:
    types: frozenset[str] = frozenset()
    if fund_types_blacklist:
        types = frozenset(t.strip() for t in fund_types_blacklist.split(",") if t.strip())

    try:
        max_pos = Decimal(str(max_single_position)) if max_single_position is not None else None
    except (InvalidOperation, ValueError, TypeError):
        return {"error": f"Invalid max_single_position: {max_single_position!r}"}

    try:
        min_size = Decimal(str(min_fund_size)) if min_fund_size is not None else None
    except (InvalidOperation, ValueError, TypeError):
        return {"error": f"Invalid min_fund_size: {min_fund_size!r}"}

    rule = PersonalRule(
        id=rule_id,
        description=description,
        fund_types_blacklist=types,
        max_single_position=max_pos,
        min_fund_size=min_size,
    )
    _ruleset.add(rule)
    return {
        "status": "ok",
        "message": f"Rule '{rule_id}' added.",
        "active_count": len(_ruleset.active),
        "rule": {
            "id": rule.id,
            "description": rule.description,
            "fund_types_blacklist": sorted(rule.fund_types_blacklist),
            "max_single_position": float(rule.max_single_position) if rule.max_single_position is not None else None,
            "min_fund_size": float(rule.min_fund_size) if rule.min_fund_size is not None else None,
        },
    }
