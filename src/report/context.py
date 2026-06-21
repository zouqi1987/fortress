"""Report context builder — converts ConversationState dataclasses into
Jinja2-friendly dicts with Chinese display names and formatted numbers.

Pure function: state → context dict.  Zero I/O, no side effects.
"""
from datetime import date
from decimal import Decimal

from src.agent.state import ConversationState
from src.datatypes import fmt_amount

# ── Display mappings ──────────────────────────────────────────────────

_RISK_LEVEL_ZH = {
    "conservative": "保守型",
    "moderate": "稳健型",
    "aggressive": "进取型",
}

_HEALTH_GRADE_LABEL = {
    "A": "优秀", "B": "良好", "C": "一般", "D": "较差", "F": "差",
}

_AUDIT_SEVERITY_ZH = {
    "pass": "通过", "warn": "注意", "reject": "不通过",
}

_PATH_NAMES = {"A": "底仓配置", "B": "机会捕捉", "C": "持仓诊断"}

_ASSET_LABELS = {
    "equity": "权益类", "bond": "债券类", "cash": "现金类",
}


# ── Helpers ───────────────────────────────────────────────────────────

def _pct(v: Decimal | int | float) -> str:
    """Format a ratio (e.g. 0.35) as percentage string (35.0%)."""
    return f"{float(v) * 100:.1f}%"


def _amount(v: Decimal | int | float) -> str:
    """Format monetary amount using default fmt_amount."""
    return fmt_amount(Decimal(v)) if not isinstance(v, Decimal) else fmt_amount(v)


# ── Main builder ──────────────────────────────────────────────────────

def build_context(state: ConversationState) -> dict:
    """Convert ConversationState into a Jinja2 template context dict.

    Returns a dict ready for jinja2.Template.render(**ctx).
    All Decimal values are pre-formatted as display strings.
    """
    ctx: dict[str, object] = {
        "path": state.get("path", "A"),
        "path_name": _PATH_NAMES.get(state.get("path", "A"), "分析"),
        "date": date.today().isoformat(),
        "report_id": _report_id(state),
    }

    # Portfolio
    portfolio = state.get("portfolio")
    if portfolio:
        ctx["portfolio"] = [
            {"name": _ASSET_LABELS.get(k, k), "amount": _amount(v)}
            for k, v in portfolio.items()
        ]
        ctx["portfolio_total"] = _amount(
            sum(Decimal(str(v)) for v in portfolio.values())
        )

    # Risk profile
    risk = state.get("risk_profile")
    if risk:
        ctx["risk_profile"] = {
            "level": _RISK_LEVEL_ZH.get(str(risk.level.value), str(risk.level.value)),
            "total_score": risk.total_score,
            "scores": {
                "horizon": risk.scores.horizon,
                "loss_tolerance": risk.scores.loss_tolerance,
                "income_stability": risk.scores.income_stability,
                "experience": risk.scores.experience,
                "liquidity": risk.scores.liquidity,
            },
            "warnings": list(getattr(risk, "warnings", [])),
        }

    # Debate (path B)
    debate = state.get("debate_result")
    if debate:
        ctx["debate_result"] = debate  # Already HTML from debater node

    # Allocation plan
    plan = state.get("allocation_plan")
    if plan:
        ctx["allocation_plan"] = {
            "equity_pct": plan.equity_pct,
            "bond_pct": plan.bond_pct,
            "cash_pct": plan.cash_pct,
            "total": _amount(plan.total),
            "layers": [
                {
                    "name": ly.name,
                    "equity_pct": ly.equity_pct,
                    "bond_pct": ly.bond_pct,
                    "cash_pct": ly.cash_pct,
                    "description": ly.description,
                }
                for ly in plan.layers
            ],
            "buckets": [
                {
                    "name": b.name,
                    "amount": _amount(b.amount),
                    "fund_type": b.fund_type,
                    "layer": b.layer,
                }
                for b in plan.buckets
            ],
        }

    # Audit results
    audits = state.get("audit_results")
    if audits:
        ctx["audit_results"] = [
            {
                "fund_code": a.fund_code,
                "passed": a.passed,
                "severity": _AUDIT_SEVERITY_ZH.get(a.severity, a.severity),
                "severity_class": a.severity,
                "reasons": list(a.reasons),
                "icon": "pass" if a.passed else ("warn" if a.severity == "warn" else "reject"),
            }
            for a in audits
        ]

    # Stress test
    stress = state.get("stress_result")
    if stress:
        ctx["stress_result"] = {
            "scenario_name": stress.scenario_name,
            "equity_impact": _amount(stress.equity_impact),
            "bond_impact": _amount(stress.bond_impact),
            "cash_impact": _amount(stress.cash_impact),
            "total_loss": _amount(stress.total_loss),
            "loss_pct": _pct(stress.loss_pct),
            "final_value": _amount(stress.final_value),
        }

    # Health check
    health = state.get("health_check")
    if health:
        ctx["health_check"] = {
            "overall_score": health.overall_score,
            "grade": health.grade,
            "grade_label": _HEALTH_GRADE_LABEL.get(health.grade, health.grade),
            "drift_score": health.drift_score,
            "diversification_score": health.diversification_score,
            "fee_score": health.fee_score,
            "drawdown_score": health.drawdown_score,
            "warnings": list(getattr(health, "warnings", [])),
        }

    # Errors
    errors = state.get("errors", [])
    if errors:
        ctx["errors"] = list(errors)

    return ctx


def _report_id(state: ConversationState) -> str:
    """Generate a short report ID for tracking."""
    from hashlib import sha1
    fingerprint = sha1(
        f"{state.get('path','')}{state.get('user_message','')}".encode()
    ).hexdigest()[:8]
    return f"FR-{date.today().strftime('%Y%m%d')}-{fingerprint}"
