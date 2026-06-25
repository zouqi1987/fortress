"""Risk personalization — weight tables for fund scoring by class × investor profile.

Zero I/O. Pure data + helper functions: maps fortress fund types to scoring
classes and returns the dimension weight dict for a given (fund_type_class,
risk_profile) combination.

Methodology basis:
- Active funds (bond/mixed/stock) — Morningstar Medalist active pillar weights
  (People 45% / Process 45% / Parent 10%) refracted into 5 dimensions. Active
  management is evaluated on judgment (institutional_consensus), execution
  (peer_performance), risk discipline (risk_control), repeat performance
  (persistence), and cost (fee). Aggressive profiles shift toward
  peer_performance; conservative profiles shift toward risk_control.
- Passive funds (index) — Morningstar Medalist passive pillar weights
  (People 10% / Process 80%) refracted with fee heavily weighted: tracking
  error and cost dominate passive fund selection, so fee weight rises to
  0.40–0.50 across profiles.
- Money funds — only 3 dimensions (institutional_consensus / peer_performance /
  fee). Amortized-cost accounting eliminates NAV volatility, so risk_control
  and persistence are structurally N/A — their inclusion would be noise.

The 9 rows of WEIGHTS each sum to exactly 1.0.
"""

# fortress fund_type → scoring class
_FUND_TYPE_CLASS: dict[str, str] = {
    "bond": "active",
    "mixed": "active",
    "stock": "active",
    "index": "passive",
    "money": "money",
}

# 9 combinations: 3 fund-type classes × 3 risk profiles.
# Each row sums to exactly 1.0.
WEIGHTS: dict[str, dict[str, dict[str, float]]] = {
    "active": {
        # Morningstar Medalist active: People 45%/Process 45%/Parent 10%.
        # Conservative profile emphasizes risk_control (0.30) over peer_performance (0.10).
        "conservative": {
            "institutional_consensus": 0.25,
            "peer_performance": 0.10,
            "risk_control": 0.30,
            "persistence": 0.15,
            "fee": 0.20,
        },
        "moderate": {
            "institutional_consensus": 0.25,
            "peer_performance": 0.25,
            "risk_control": 0.20,
            "persistence": 0.10,
            "fee": 0.20,
        },
        # Aggressive profile shifts toward peer_performance (0.40).
        "aggressive": {
            "institutional_consensus": 0.20,
            "peer_performance": 0.40,
            "risk_control": 0.10,
            "persistence": 0.10,
            "fee": 0.20,
        },
    },
    "passive": {
        # Morningstar Medalist passive: People 10%/Process 80%.
        # Fee dominates passive selection: tracking error + cost.
        "conservative": {
            "institutional_consensus": 0.20,
            "peer_performance": 0.15,
            "risk_control": 0.15,
            "persistence": 0.10,
            "fee": 0.40,
        },
        "moderate": {
            "institutional_consensus": 0.15,
            "peer_performance": 0.20,
            "risk_control": 0.10,
            "persistence": 0.10,
            "fee": 0.45,
        },
        "aggressive": {
            "institutional_consensus": 0.10,
            "peer_performance": 0.25,
            "risk_control": 0.05,
            "persistence": 0.10,
            "fee": 0.50,
        },
    },
    "money": {
        # Money market funds use amortized-cost accounting → no volatility.
        # risk_control and persistence structurally N/A.
        "conservative": {
            "institutional_consensus": 0.40,
            "peer_performance": 0.30,
            "fee": 0.30,
        },
        "moderate": {
            "institutional_consensus": 0.35,
            "peer_performance": 0.35,
            "fee": 0.30,
        },
        "aggressive": {
            "institutional_consensus": 0.30,
            "peer_performance": 0.40,
            "fee": 0.30,
        },
    },
}

_VALID_FUND_CLASSES = frozenset(WEIGHTS.keys())
_VALID_RISK_LEVELS = frozenset(("conservative", "moderate", "aggressive"))


def classify_fund_type(fund_type: str) -> str:
    """Map a fortress fund type to its scoring class.

    Args:
        fund_type: One of "bond", "mixed", "stock", "index", "money"
                   (the 5 fund_type values used in PoolFund/FundInfo).

    Returns:
        "active"  — for bond/mixed/stock (actively managed).
        "passive" — for index (tracks a benchmark).
        "money"   — for money (money market fund).

    Raises:
        ValueError: If fund_type is not one of the 5 known fortress types.
                   Surfaces typos / corrupt data immediately rather than
                   silently scoring as a default class.
    """
    cls = _FUND_TYPE_CLASS.get(fund_type)
    if cls is None:
        raise ValueError(f"未知基金类型: {fund_type!r}")
    return cls


def get_weights(fund_type_class: str, risk_level: str) -> dict[str, float]:
    """Return the dimension weight dict for (fund_type_class, risk_level).

    The returned dict sums to 1.0 and contains either 5 dimensions
    (active/passive: institutional_consensus, peer_performance, risk_control,
    persistence, fee) or 3 dimensions (money: institutional_consensus,
    peer_performance, fee).

    Args:
        fund_type_class: "active", "passive", or "money"
                        (output of classify_fund_type).
        risk_level:      "conservative", "moderate", or "aggressive".

    Returns:
        Reference to the WEIGHTS row (not a copy — weight tables are
        immutable in practice; avoid copy overhead at hot paths).

    Raises:
        ValueError: If fund_type_class or risk_level is invalid.
    """
    if fund_type_class not in _VALID_FUND_CLASSES:
        raise ValueError(f"未知基金类型类: {fund_type_class!r}")
    if risk_level not in _VALID_RISK_LEVELS:
        raise ValueError(f"未知风险等级: {risk_level!r}")
    return WEIGHTS[fund_type_class][risk_level]


_STAGE1_DIMS = ("institutional_consensus", "peer_performance", "fee")


def get_weights_light(fund_type_class: str, risk_level: str) -> dict[str, float]:
    """Stage 1 weights — 3 NavStore-free dims, renormalized to sum 1.0.

    For money funds: identical to get_weights (already 3-dim, no loss).
    For active/passive: drops risk_control + persistence, renormalizes
    the remaining 3 dims (consensus/peer/fee) to sum to 1.0.

    Used by score_funds_light to pre-rank the full pool without NavStore.

    Args:
        fund_type_class: "active", "passive", or "money".
        risk_level:      "conservative", "moderate", or "aggressive".

    Returns:
        Dict of 3 dimension weights summing to 1.0.

    Raises:
        ValueError: If fund_type_class or risk_level is invalid.
    """
    full = get_weights(fund_type_class, risk_level)  # raises ValueError if invalid
    available = {k: v for k, v in full.items() if k in _STAGE1_DIMS}
    total = sum(available.values())
    if total == 0:
        raise ValueError(
            f"Stage 1 dimensions all zero for {fund_type_class}/{risk_level}"
        )
    return {k: v / total for k, v in available.items()}
