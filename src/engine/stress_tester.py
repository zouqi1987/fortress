"""Scenario stress testing engine.

Zero I/O. Takes portfolio allocation + scenario definition, returns impact analysis.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Scenario:
    """A stress scenario definition. All shocks are decimal percentages.

    equity_shock=-0.40 means equity drops 40%.
    Fields left at 0 mean no shock to that asset class.
    """

    name: str
    equity_shock: Decimal = Decimal("0")
    bond_shock: Decimal = Decimal("0")
    cash_shock: Decimal = Decimal("0")


@dataclass(frozen=True)
class StressResult:
    """Result of running a scenario against a portfolio."""

    scenario_name: str
    equity_impact: Decimal
    bond_impact: Decimal
    cash_impact: Decimal
    total_loss: Decimal  # negative = loss, positive = gain
    final_value: Decimal
    loss_pct: Decimal  # -0.24 = 24% loss


# ── Historical scenarios ─────────────────────────────────────────────


HISTORICAL_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(name="2008 全球金融危机", equity_shock=Decimal("-0.50"), bond_shock=Decimal("0.05")),
    Scenario(name="2015 A股暴跌", equity_shock=Decimal("-0.40"), bond_shock=Decimal("0.02")),
    Scenario(name="2020 新冠冲击", equity_shock=Decimal("-0.30"), bond_shock=Decimal("0.10")),
    Scenario(name="利率大幅上行", equity_shock=Decimal("-0.15"), bond_shock=Decimal("-0.10")),
    Scenario(name="人民币贬值压力", equity_shock=Decimal("-0.10"), bond_shock=Decimal("-0.05")),
)


def run_stress_test(portfolio: dict[str, Decimal], scenario: Scenario) -> StressResult:
    """Apply a stress scenario to a portfolio allocation.

    Args:
        portfolio: {"equity": amount, "bond": amount, "cash": amount}
        scenario: Shock scenario to apply.

    Returns:
        StressResult with per-asset impacts, total loss, and final value.
    """
    equity = portfolio.get("equity", Decimal("0"))
    bond = portfolio.get("bond", Decimal("0"))
    cash = portfolio.get("cash", Decimal("0"))
    initial_total = equity + bond + cash

    equity_impact = (equity * scenario.equity_shock).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    bond_impact = (bond * scenario.bond_shock).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cash_impact = (cash * scenario.cash_shock).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_loss = equity_impact + bond_impact + cash_impact
    final_value = (initial_total + total_loss).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if initial_total > Decimal("0"):
        loss_pct = (total_loss / initial_total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        loss_pct = Decimal("0")

    return StressResult(
        scenario_name=scenario.name,
        equity_impact=equity_impact,
        bond_impact=bond_impact,
        cash_impact=cash_impact,
        total_loss=total_loss,
        final_value=final_value,
        loss_pct=loss_pct,
    )
