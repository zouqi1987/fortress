"""Portfolio optimization engine — min-variance via scipy.optimize.

Zero I/O. Takes return series + config, returns optimized weights.
Replaces Riskfolio-Lib dependency (broken with numpy>=2.x / cvxpy compat deadlock).
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class OptimizerConfig:
    """Optimization parameters."""

    max_weight: Decimal = Decimal("0.30")  # single asset cap
    min_weight: Decimal = Decimal("0.01")  # minimum inclusion threshold
    risk_free_rate: Decimal = Decimal("0.02")  # 2% (for Sharpe-ratio objective)


@dataclass(frozen=True)
class OptimizationResult:
    weights: dict[str, Decimal]  # asset_code → weight
    success: bool
    message: str = ""


def optimize_portfolio(
    returns: dict[str, list[float]],
    config: OptimizerConfig,
) -> OptimizationResult:
    """Min-variance portfolio optimization via scipy SLSQP.

    Args:
        returns: Asset code → list of historical returns (floats).
        config: Optimization parameters (weight constraints).

    Returns:
        OptimizationResult with optimized weights (sum ≈ 1.0).
    """
    if not returns:
        return OptimizationResult(weights={}, success=True, message="no assets to optimize")

    codes = list(returns.keys())

    if len(codes) == 1:
        weight = min(config.max_weight, Decimal("1.0"))
        return OptimizationResult(
            weights={codes[0]: weight},
            success=True,
            message=f"single asset — {float(weight):.0%} (max_weight={float(config.max_weight):.0%})",
        )

    try:
        import numpy as np
        from scipy.optimize import minimize
    except ImportError as e:
        return OptimizationResult(
            weights=_equal_weight(codes),
            success=False,
            message=f"[IMPORT_ERROR] scipy not available: {e}",
        )

    try:
        n = len(codes)
        min_len = min(len(r) for r in returns.values())
        if min_len < 2:
            return OptimizationResult(
                weights=_equal_weight(codes),
                success=False,
                message="insufficient data (< 2 observations)",
            )

        # Build aligned return matrix
        ret_matrix = np.array([returns[c][:min_len] for c in codes])

        # Covariance matrix
        cov = np.cov(ret_matrix)

        # Bounds: ensure max_weight is achievable (n * max >= 1.0)
        min_w = float(config.min_weight)
        max_w = max(float(config.max_weight), 1.0 / n + 0.01)
        bounds = [(min_w, max_w)] * n

        # Constraints: sum(weights) == 1
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Initial guess: equal weight
        w0 = np.ones(n) / n

        # Minimize portfolio variance: w^T Σ w
        result = minimize(
            fun=lambda w: w @ cov @ w,
            x0=w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-12},
        )

        if not result.success:
            return OptimizationResult(
                weights=_equal_weight(codes),
                success=False,
                message=f"optimizer did not converge: {result.message}",
            )

        raw = result.x
        # Normalize
        raw = np.maximum(raw, 0)
        total = raw.sum()
        if total > 0:
            raw = raw / total

        # Use same effective max_weight as bounds (n * max_weight must >= 1.0)
        effective_max = Decimal(str(max_w))
        weights: dict[str, Decimal] = {}
        for code, w in zip(codes, raw):
            val = Decimal(str(w))
            clamped = max(config.min_weight, min(effective_max, val))
            weights[code] = clamped.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # Final rescale
        total_w = sum(weights.values(), start=Decimal("0"))
        if total_w > Decimal("0"):
            weights = {
                k: (v / total_w).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                for k, v in weights.items()
            }

        return OptimizationResult(
            weights=weights,
            success=True,
            message="min-variance optimized via SLSQP",
        )

    except Exception as e:
        return OptimizationResult(
            weights=_equal_weight(codes),
            success=False,
            message=f"optimization error: {e}",
        )


def _equal_weight(codes: list[str]) -> dict[str, Decimal]:
    """Fallback: equal weight allocation."""
    n = len(codes)
    if n == 0:
        return {}
    w = Decimal("1.0") / Decimal(str(n))
    return {c: w.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) for c in codes}
