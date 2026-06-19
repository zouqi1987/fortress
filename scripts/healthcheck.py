#!/usr/bin/env python3
"""End-to-end smoke test for the fortress agent pipeline.

Usage: python scripts/healthcheck.py

Validates all three layers (engine → data → agent) work end-to-end
without external API calls. Uses in-memory data and mock sources.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import mkdtemp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EXIT_OK = 0
EXIT_FAIL = 1
errors: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> None:
    status = "✅" if condition else "❌"
    print(f"  {status} {description}")
    if not condition:
        errors.append(f"{description}: {detail}")


def main() -> int:
    print("=" * 60)
    print("🏰 Fortress E2E Health Check")
    print("=" * 60)

    tmpdir = Path(mkdtemp())

    # ── 1. Engine: Ledger ────────────────────────────────────────────
    print("\n📒 Engine: Ledger")
    from src.engine.ledger import (
        Account, AccountType, Split, Transaction, validate_transaction,
    )

    txn = Transaction(
        id="e2e-001", date=date.today(), description="申购基金",
        splits=(
            Split("assets:funds:000001", Decimal("10000.00")),
            Split("assets:cash", Decimal("-10000.00")),
        ),
    )
    violations = validate_transaction(txn)
    check("Transaction validation", len(violations) == 0, str(violations))

    # ── 2. Engine: Risk Profile ──────────────────────────────────────
    print("\n⚖️  Engine: Risk Profile")
    from src.engine.risk_profile import InvestmentHorizon, assess_risk_profile

    profile = assess_risk_profile(
        InvestmentHorizon.LONG, Decimal("20"), 4, 3, 3,
    )
    check("Risk score range", 0 <= profile.total_score <= 100, str(profile.total_score))
    check("Risk level assigned", profile.level is not None)

    # ── 3. Engine: Allocation ────────────────────────────────────────
    print("\n🏗️  Engine: Allocation")
    from src.engine.allocation import build_allocation

    plan = build_allocation(profile.level, Decimal("500000"))
    check("Buckets created", len(plan.buckets) > 0, str(len(plan.buckets)))
    check("Percentages sum 100", plan.equity_pct + plan.bond_pct + plan.cash_pct == 100)
    check("Total matches", plan.total == Decimal("500000"))

    # ── 4. Engine: Stress Test ───────────────────────────────────────
    print("\n🌪️  Engine: Stress Test")
    from src.engine.stress_tester import HISTORICAL_SCENARIOS, run_stress_test

    pf = {"equity": Decimal("300000"), "bond": Decimal("150000"), "cash": Decimal("50000")}
    result = run_stress_test(pf, HISTORICAL_SCENARIOS[0])
    check("Loss calculated", result.total_loss != Decimal("0"), str(result.total_loss))
    check("Final value positive", result.final_value > Decimal("0"))

    # ── 5. Data: Portfolio DB ────────────────────────────────────────
    print("\n🗄️  Data: Portfolio DB")
    from src.data.portfolio_db import PortfolioDB

    db_path = str(tmpdir / "e2e.db")
    with PortfolioDB(db_path) as db:
        acct = Account("assets:cash", AccountType.ASSET, "CNY", "现金")
        db.create_account(acct)
        acct2 = Account("assets:funds:000001", AccountType.ASSET, "000001", "fund")
        db.create_account(acct2)
        db.create_transaction(txn)

        got = db.get_transaction("e2e-001")
        check("Transaction stored and retrieved", got is not None and got.id == "e2e-001")

    # ── 6. Agent: Graph ──────────────────────────────────────────────
    print("\n🤖 Agent: LangGraph Pipeline")
    from src.agent.graph import build_graph
    from src.agent.state import create_initial_state

    state = create_initial_state("A", "e2e test — allocate new portfolio")
    state["portfolio"] = {"equity": Decimal("0"), "bond": Decimal("0"), "cash": Decimal("500000")}
    state["risk_profile"] = profile

    graph = build_graph()
    result = graph.invoke(state)

    check("Report generated", "report_html" in result, "")
    check("Report has content", len(result.get("report_html", "")) > 100, f"length={len(result.get('report_html', ''))}")
    check("No agent errors", len(result.get("errors", [])) == 0, str(result.get("errors")))

    # ── 7. Redlines: Rules ───────────────────────────────────────────
    print("\n🔒 Redlines: Hard Rules")
    from src.datatypes import FundInfo
    from src.redlines.hard_rules import HARD_RULES, evaluate_rules

    fund = FundInfo("000001", "good fund", "mixed", Decimal("5_000_000_000"), Decimal("0.010"), date(2015, 1, 1))
    violations = evaluate_rules(HARD_RULES, fund, Decimal("50000"), Decimal("500000"))
    check("Clean fund passes all rules", len(violations) == 0, str(violations))

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"❌ {len(errors)} check(s) failed:")
        for e in errors:
            print(f"   - {e}")
        return EXIT_FAIL
    else:
        print("✅ All E2E checks passed!")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
