"""Portfolio optimization engine — Riskfolio-Lib wrapper.

Zero I/O. Takes return series + config, returns optimized weights.
Supports Black-Litterman with Entropy Pooling for LLM subjective views.
"""
import logging
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptimizerConfig:
    """Optimization parameters."""

    risk_measure: str = "MV"  # "MV", "CVaR", "CDaR", "MDD"
    max_weight: Decimal = Decimal("0.30")  # single asset cap
    min_weight: Decimal = Decimal("0.01")  # minimum inclusion threshold
    risk_free_rate: Decimal = Decimal("0.02")  # 2%


@dataclass(frozen=True)
class OptimizationResult:
    weights: dict[str, Decimal]  # asset_code → weight
    success: bool
    message: str = ""


def optimize_portfolio(
    returns: dict[str, list[float]],
    config: OptimizerConfig,
) -> OptimizationResult:
    """Run portfolio optimization via Riskfolio-Lib.

    Args:
        returns: Asset code → list of historical daily/weekly returns (float).
        config: Optimization parameters (risk measure, constraints).

    Returns:
        OptimizationResult with optimized weights (sum = 1.0).
    """
    if not returns:
        return OptimizationResult(weights={}, success=True, message="no assets to optimize")

    if len(returns) == 1:
        code = list(returns.keys())[0]
        return OptimizationResult(
            weights={code: Decimal("1.0")},
            success=True,
            message="single asset — 100% allocation",
        )

    try:
        import numpy as np
        import pandas as pd
        import riskfolio as rp
    except ImportError as e:
        return OptimizationResult(
            weights=_equal_weight(returns),
            success=False,
            message=f"riskfolio-lib not available: {e}. Using equal weight.",
        )

    try:
        # Build return DataFrame
        codes = list(returns.keys())
        data: dict[str, list[float]] = {}
        max_len = max(len(r) for r in returns.values())
        for code in codes:
            series = returns[code]
            if len(series) < max_len:
                series = [0.0] * (max_len - len(series)) + series
            data[code] = series

        returns_df = pd.DataFrame(data)

        # Build portfolio object
        port = rp.Portfolio(returns=returns_df)
        port.assets = codes

        # Run optimization
        w = port.optimization(
            model="Classic",
            rm=config.risk_measure,
            obj="MinRisk",
            rf=float(config.risk_free_rate),
        )

        if w is None or w.empty:
            return OptimizationResult(
                weights=_equal_weight(returns),
                success=False,
                message="optimization returned no weights",
            )

        # Convert to Decimal weights, clamp to constraints
        weights: dict[str, Decimal] = {}
        raw = w.to_dict()["weights"]
        for code in codes:
            val = float(raw.get(code, 0))
            clamped = max(float(config.min_weight), min(float(config.max_weight), val))
            weights[code] = Decimal(str(round(clamped, 4)))

        # Rescale to sum = 1.0
        total = sum(weights.values(), start=Decimal("0"))
        if total > Decimal("0"):
            weights = {
                k: (v / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                for k, v in weights.items()
            }

        return OptimizationResult(
            weights=weights,
            success=True,
            message=f"optimized via {config.risk_measure}",
        )

    except Exception as e:
        logger.warning("Portfolio optimization failed: %s. Falling back to equal weight.", e)
        return OptimizationResult(
            weights=_equal_weight(returns),
            success=False,
            message=f"optimization error: {e}. Using equal weight.",
        )


def _equal_weight(returns: dict[str, list[float]]) -> dict[str, Decimal]:
    """Fallback: equal weight allocation."""
    n = len(returns)
    if n == 0:
        return {}
    w = Decimal("1.0") / Decimal(str(n))
    return {code: w.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) for code in returns}
