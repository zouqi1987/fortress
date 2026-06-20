"""Fund screening and ranking engine.

Zero I/O. Pure functions: receive FundInfo list + config, return scored results.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from src.datatypes import FundInfo, fmt_amount


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


def screen_funds(funds: list[FundInfo], config: ScreenConfig) -> list[ScreenResult]:
    """Filter and score a list of funds.

    Returns results sorted by score descending. Funds that fail hard filters
    are excluded entirely. Warnings are informational and don't exclude.
    """
    results: list[ScreenResult] = []

    for fund in funds:
        # ── Hard filters ────────────────────────────────────────────
        if fund.net_asset_value < config.min_net_asset_value:
            continue
        if fund.type not in config.allowed_types:
            continue
        # Exclude funds newer than min_inception_date (None = no filter)
        if config.min_inception_date is not None and fund.inception_date > config.min_inception_date:
            continue
        if fund.fee_rate > config.max_fee_rate:
            continue

        # ── Scoring (0–100) ─────────────────────────────────────────
        score = 0
        warnings: list[str] = []

        # Size score (0–30): bigger is better, up to 10B
        size_val = min(fund.net_asset_value, Decimal("10_000_000_000"))
        score += int(size_val * Decimal("30") / Decimal("10_000_000_000"))

        # Age score (0–20): older is better, up to 10 years
        age_days = (date.today() - fund.inception_date).days
        score += min(20, age_days // 180)  # ~0.5 point per half-year

        # Fee score (0–25): lower is better
        if fund.fee_rate <= Decimal("0.005"):
            score += 25
        elif fund.fee_rate <= Decimal("0.010"):
            score += 20
        elif fund.fee_rate <= Decimal("0.015"):
            score += 15
        elif fund.fee_rate <= Decimal("0.020"):
            score += 10
        else:
            score += 5

        # Type diversification bonus (0–15)
        type_bonus = {"bond": 15, "mixed": 12, "index": 10, "stock": 8, "money": 5}
        score += type_bonus.get(fund.type, 5)

        # Remaining to 100: complexity bonus
        score += 10

        # ── Warnings ─────────────────────────────────────────────────
        if fund.net_asset_value < Decimal("200_000_000"):
            warnings.append(f"基金规模 {fmt_amount(fund.net_asset_value)} 低于2亿")
        if (date.today() - fund.inception_date).days < 365:
            warnings.append(f"基金成立不足1年 ({fund.inception_date})")
        if fund.fee_rate > Decimal("0.015"):
            warnings.append(f"费率偏高 ({float(fund.fee_rate):.1%})")  # float() OK: format-only

        results.append(ScreenResult(fund=fund, score=score, warnings=tuple(warnings)))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ── v2 Performance Scoring Functions ──────────────────────────────────


def score_performance(navs: list[float]) -> int:
    """Score multi-period returns (0–25). Recent periods weighted higher.

    1m:3pts 3m:5pts 6m:5pts 1y:7pts 3y:5pts. Positive → full; zero → half.
    """
    if len(navs) < 22:
        return 0

    periods = {"1m": (21, 3), "3m": (63, 5), "6m": (126, 5), "1y": (252, 7)}
    score = 0

    for _, (days, pts) in periods.items():
        if len(navs) <= days:
            continue
        start_nav = navs[-days - 1] if len(navs) > days else navs[0]
        end_nav = navs[-1]
        if start_nav <= 0:
            continue
        ret = (end_nav / start_nav - 1)
        if ret > 0:
            score += pts
        elif ret > -0.05:
            score += pts // 2

    return min(25, score)


def score_risk_control(navs: list[float]) -> int:
    """Score risk control (0–20). Lower drawdown + lower volatility = higher."""
    if len(navs) < 63:
        return 0

    # Max drawdown penalty (0–10)
    peak = navs[0]
    max_dd = 0.0
    for v in navs[1:]:
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

    # Volatility penalty (0–10)
    daily_returns = [
        navs[i] / navs[i - 1] - 1
        for i in range(1, len(navs))
        if navs[i - 1] > 0
    ]
    if len(daily_returns) < 10:
        return dd_score

    mean_r = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
    ann_vol = variance ** 0.5 * (252 ** 0.5)

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


def score_manager(manager) -> int:
    """Score fund manager quality (0–5). Based on tenure and return."""
    if manager is None:
        return 0

    score = 0

    # Tenure: 3+ years = 3pts, 1-3 = 2pts, <1 = 1pt, 0 = 0
    if manager.tenure_days > 1095:
        score += 3
    elif manager.tenure_days > 365:
        score += 2
    elif manager.tenure_days > 0:
        score += 1

    # Cumulative return: parse and score
    ret_str = manager.cumulative_return.replace("+", "").replace("%", "")
    try:
        cum_ret = float(ret_str)
        if cum_ret > 50:
            score += 2
        elif cum_ret > 10:
            score += 1
    except (ValueError, AttributeError):
        pass

    # Penalty for managing too many funds (>5)
    if manager.fund_count > 5:
        score = max(0, score - 1)

    return min(5, score)

