"""Fund screening and ranking engine.

Zero I/O. Pure functions: receive FundInfo list + config, return scored results.

Unified scoring (score_funds): 5 weighted dimensions grounded in Morningstar
Medalist + 济安金信 methodology. NAV from NavStore. Funds with insufficient
data are excluded — never fabricated.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from src.datatypes import FundInfo, InsufficientDataError, fmt_amount
from src.engine.institutional_consensus import score_institutional_consensus
from src.engine.peer_scoring import score_peer_performance
from src.engine.risk_personalization import classify_fund_type, get_weights

if TYPE_CHECKING:
    from src.data.sources.fund_pool import PoolFund
    from src.data.sources.nav_store import NavStore


@dataclass(frozen=True)
class ScreenConfig:
    """Screening parameters. All optional — omit to skip filter."""

    min_net_asset_value: Decimal = Decimal("0")
    allowed_types: frozenset[str] = field(default_factory=lambda: frozenset({"stock", "bond", "mixed", "index", "money"}))
    min_inception_date: date | None = None  # None = no inception filter
    max_fee_rate: Decimal = Decimal("0.03")


@dataclass(frozen=True)
class ScreenResult:
    fund: FundInfo
    score: int  # 0–100, higher = better
    warnings: tuple[str, ...]
    dimension_breakdown: dict[str, int] = field(default_factory=dict)


# ── Unified scoring (score_funds) ─────────────────────────────────────


def score_funds(
    funds: list[FundInfo],
    config: ScreenConfig,
    nav_store: "NavStore",
    pool_index: dict[str, "PoolFund"],
    category_averages: dict[str, dict[str, float]],
    risk_level: str = "moderate",
) -> list[ScreenResult]:
    """Unified fund scoring — 5 weighted dimensions.

    Dimensions (each 0-100, then weighted by fund-type × risk-profile):
      - institutional_consensus: 4 agency ratings (PoolFund)
      - peer_performance: 5-period excess vs category avg (PoolFund)
      - risk_control: NAV volatility + max drawdown (NavStore) — not for money
      - persistence: NAV return stability (NavStore) — not for money
      - fee: fee rate (FundInfo)

    Funds with insufficient data are EXCLUDED (not scored with fabricated values):
      - All 4 agency ratings = 0 → excluded
      - NAV < 63 points (non-money) → excluded
      - Fund not in pool_index → excluded

    Args:
        funds: List of funds to screen.
        config: Screening parameters (filters).
        nav_store: Persistent NAV time-series store.
        pool_index: {code: PoolFund} for ratings + returns.
        category_averages: {fund_type: {period: avg_return}} from compute_category_averages.
        risk_level: "conservative" | "moderate" | "aggressive".

    Returns:
        ScreenResult list sorted by score descending. Each has dimension_breakdown.
    """
    results: list[ScreenResult] = []

    for fund in funds:
        # ── Hard filters (same as screen_funds) ─────────────────────
        if fund.net_asset_value < config.min_net_asset_value:
            continue
        if fund.type not in config.allowed_types:
            continue
        if config.min_inception_date is not None and fund.inception_date > config.min_inception_date:
            continue
        if fund.fee_rate > config.max_fee_rate:
            continue

        # ── Get PoolFund (required for consensus + peer) ──────────────
        pool_fund = pool_index.get(fund.code)
        if pool_fund is None:
            continue  # excluded — no pool data

        fund_class = classify_fund_type(fund.type)
        weights = get_weights(fund_class, risk_level)  # raises ValueError if invalid
        dimensions: dict[str, int] = {}
        warnings: list[str] = []

        # ── Dimension 1: Institutional consensus ─────────────────────
        try:
            ratings = {
                "morningstar": pool_fund.rating_morningstar,
                "shanghai": pool_fund.rating_shanghai,
                "zhaoshang": pool_fund.rating_zhaoshang,
                "jiAn": pool_fund.rating_jiAn,
            }
            dimensions["institutional_consensus"] = score_institutional_consensus(ratings)
        except InsufficientDataError:
            continue  # excluded — no ratings

        # ── Dimension 2: Peer performance ────────────────────────────
        fund_returns = {
            "ret_1m": pool_fund.ret_1m,
            "ret_3m": pool_fund.ret_3m,
            "ret_6m": pool_fund.ret_6m,
            "ret_1y": pool_fund.ret_1y,
            "ret_3y": pool_fund.ret_3y,
        }
        cat_key = pool_fund.raw_type or pool_fund.fund_type
        cat_avg = category_averages.get(cat_key, category_averages.get(fund.type, {}))
        if not cat_avg:
            continue  # excluded — no category averages for this fund type
        try:
            dimensions["peer_performance"] = score_peer_performance(fund_returns, cat_avg)
        except InsufficientDataError:
            continue  # excluded — no returns

        # ── Dimension 3: Fee ──────────────────────────────────────────
        dimensions["fee"] = _score_fee(fund.fee_rate)

        # ── Dimensions 4-5: Risk control + Persistence (not for money) ─
        if fund_class != "money":
            nav_series = nav_store.get_nav_series(fund.code)
            if len(nav_series) < 63:
                continue  # excluded — insufficient NAV
            # Rescale: score_risk_control returns 0-20, ×5 → 0-100
            dimensions["risk_control"] = score_risk_control(nav_series) * 5
            # Rescale: score_consistency returns 0-10, ×10 → 0-100
            dimensions["persistence"] = score_consistency(nav_series) * 10

        # ── Weighted final score ──────────────────────────────────────
        score = int(sum(dimensions[d] * weights[d] for d in weights))

        # ── Warnings (ported from screen_funds) ──────────────────────
        if fund.net_asset_value < Decimal("200_000_000"):
            warnings.append(f"基金规模 {fmt_amount(fund.net_asset_value)} 低于2亿")
        if (date.today() - fund.inception_date).days < 365:
            warnings.append(f"基金成立不足1年 ({fund.inception_date})")
        if fund.fee_rate > Decimal("0.015"):
            warnings.append(f"费率偏高 ({float(fund.fee_rate):.1%})")

        results.append(ScreenResult(
            fund=fund, score=score, warnings=tuple(warnings),
            dimension_breakdown=dimensions,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _score_fee(fee_rate: Decimal) -> int:
    """Score fee 0-100. Lower fee = higher score.

    Morningstar: fee is paramount — "expenses have as much weight as the
    other pillars combined." Fee tiers aligned with industry standards.
    """
    fee_pct = float(fee_rate) * 100  # Decimal 0.015 → 1.5%
    if fee_pct <= 0.15:
        return 100
    if fee_pct <= 0.50:
        return 85
    if fee_pct <= 1.00:
        return 70
    if fee_pct <= 1.50:
        return 55
    if fee_pct <= 2.00:
        return 35
    return 15


# ── Preserved scoring helpers (used by score_funds) ──────────────────


def _compute_metrics(navs: list[float]) -> tuple[float, float] | None:
    """Compute 1-year return and annualized volatility from NAV sequence.

    Returns (ret_1y, ann_vol) or None if insufficient data (< 63 points).
    Used by score_risk_control to avoid DRY violation.
    """
    if len(navs) < 63:
        return None
    prices = [float(v) for v in navs]
    ret_1y = (prices[-1] / prices[0] - 1) if prices[0] > 0 else 0.0
    daily_returns = [
        prices[i] / prices[i - 1] - 1
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]
    if len(daily_returns) < 10:
        return None
    mean_r = sum(daily_returns) / len(daily_returns)
    variance = sum((x - mean_r) ** 2 for x in daily_returns) / len(daily_returns)
    ann_vol = variance ** 0.5 * (252 ** 0.5)
    return (ret_1y, ann_vol)


def score_risk_control(navs: list[float]) -> int:
    """Score risk control (0–20). Lower drawdown + lower volatility = higher.

    Uses _compute_metrics for shared volatility/drawdown computation.
    """
    if len(navs) < 63:
        return 0

    prices = [float(v) for v in navs]

    # Max drawdown penalty (0–10)
    peak = prices[0]
    max_dd = 0.0
    for v in prices[1:]:
        if v > peak:
            peak = v
        dd = (v / peak - 1)
        if dd < max_dd:
            max_dd = dd

    dd_score = 10
    if max_dd < -0.30:
        dd_score = 0
    elif max_dd < -0.20:
        dd_score = 2
    elif max_dd < -0.10:
        dd_score = 5
    elif max_dd < -0.05:
        dd_score = 8

    # Volatility penalty (0–10) — uses shared helper
    metrics = _compute_metrics(navs)
    if metrics is None:
        return dd_score

    ann_vol = metrics[1]

    vol_score = 10
    if ann_vol > 0.40:
        vol_score = 0
    elif ann_vol > 0.25:
        vol_score = 3
    elif ann_vol > 0.15:
        vol_score = 5
    elif ann_vol > 0.08:
        vol_score = 8

    return dd_score + vol_score


def score_consistency(navs: list[float]) -> int:
    """Score return consistency (0–10). Based on quarterly positive rate."""
    if len(navs) < 126:
        return 0

    # Approximate quarters using 63-day windows
    quarter_size = 63
    quarters_positive = 0
    quarters_total = 0

    for start_idx in range(0, len(navs) - quarter_size, quarter_size):
        end_idx = start_idx + quarter_size
        if end_idx > len(navs):
            break
        if navs[start_idx] > 0:
            q_return = navs[end_idx - 1] / navs[start_idx] - 1
            if q_return > 0:
                quarters_positive += 1
            quarters_total += 1

    if quarters_total == 0:
        return 0

    ratio = quarters_positive / quarters_total
    return min(10, int(ratio * 10))
