"""Debate signal extraction engine — pure computation, zero LLM.

Extracts structured bull/bear signals from market data and holdings.
The host LLM (Claude Code) receives these signals and generates natural language debate.
Skill = domain compute engine. Host LLM = natural language wrapper.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Signal:
    """A single debate signal — computed from market data, not LLM-generated."""

    name: str          # "PE分位", "波动率", "资金流向"
    value: str         # "28%", "32%", "+3.2亿"
    interpretation: str  # human-readable interpretation
    direction: str     # "bull" | "bear"


@dataclass(frozen=True)
class DebateSignals:
    """Structured debate signals for the host LLM to wrap in natural language."""

    bull_signals: list[Signal] = field(default_factory=list)
    bear_signals: list[Signal] = field(default_factory=list)
    conclusion_framework: str = ""


def extract_signals(
    market_data: dict[str, list],
    holdings: list[dict],
) -> DebateSignals:
    """Extract structured debate signals from raw data.

    Pure function — zero I/O, zero LLM calls, zero API keys.
    The host LLM receives these signals and crafts the natural language narrative.

    Args:
        market_data: fund_code → list of data dicts (NAV, PE, volatility, etc.)
        holdings: list of current position dicts

    Returns:
        DebateSignals with bull/bear signals and conclusion framework.
    """
    bull: list[Signal] = []
    bear: list[Signal] = []
    fund_count = len(market_data)
    holding_count = len(holdings)

    # ── Data quality signals ─────────────────────────────────────────
    if fund_count > 0:
        bull.append(Signal(
            name="数据覆盖",
            value=f"{fund_count}只基金",
            interpretation=f"已覆盖 {fund_count} 只关注基金的基本面数据",
            direction="bull",
        ))

    # ── Volatility assessment ────────────────────────────────────────
    volatilities = []
    for code, records in market_data.items():
        for r in records:
            if isinstance(r, dict) and "volatility" in r:
                volatilities.append(float(r["volatility"]))

    if volatilities:
        avg_vol = sum(volatilities) / len(volatilities)
        if avg_vol > 30:
            bear.append(Signal(
                name="波动率",
                value=f"{avg_vol:.0f}%",
                interpretation=f"当前平均波动率 {avg_vol:.0f}%，高于正常区间，短期风险上升",
                direction="bear",
            ))
        else:
            bull.append(Signal(
                name="波动率",
                value=f"{avg_vol:.0f}%",
                interpretation=f"当前平均波动率 {avg_vol:.0f}%，处于可控范围",
                direction="bull",
            ))

    # ── PE/valuation assessment ──────────────────────────────────────
    pe_values = []
    for code, records in market_data.items():
        for r in records:
            if isinstance(r, dict) and "pe" in r:
                pe_values.append(float(r["pe"]))

    if pe_values:
        avg_pe = sum(pe_values) / len(pe_values)
        if avg_pe < 15:
            bull.append(Signal(
                name="估值水平",
                value=f"PE {avg_pe:.1f}",
                interpretation=f"平均 PE {avg_pe:.1f}，处于历史偏低区间，估值有支撑",
                direction="bull",
            ))
        elif avg_pe > 30:
            bear.append(Signal(
                name="估值水平",
                value=f"PE {avg_pe:.1f}",
                interpretation=f"平均 PE {avg_pe:.1f}，处于历史偏高区间，需警惕估值回调",
                direction="bear",
            ))

    # ── Diversification signal ───────────────────────────────────────
    if holding_count < 3:
        bear.append(Signal(
            name="分散度",
            value=f"{holding_count}只持仓",
            interpretation=f"仅 {holding_count} 只持仓，集中度偏高，建议分散至 5-8 只",
            direction="bear",
        ))
    elif holding_count <= 8:
        bull.append(Signal(
            name="分散度",
            value=f"{holding_count}只持仓",
            interpretation=f"{holding_count} 只持仓，分散度合理",
            direction="bull",
        ))
    elif holding_count > 12:
        bear.append(Signal(
            name="分散度",
            value=f"{holding_count}只持仓",
            interpretation=f"{holding_count} 只持仓，过度分散可能稀释收益",
            direction="bear",
        ))

    # ── External context framework ───────────────────────────────────
    bull_count = len(bull)
    bear_count = len(bear)

    if bull_count > bear_count:
        bias = "偏多"
        detail = f"多方信号 {bull_count} 条 > 空方信号 {bear_count} 条"
    elif bear_count > bull_count:
        bias = "偏空"
        detail = f"空方信号 {bear_count} 条 > 多方信号 {bull_count} 条"
    else:
        bias = "中性"
        detail = f"多方信号 {bull_count} 条 == 空方信号 {bear_count} 条"

    conclusion = (
        f"综合判断: {bias}（{detail}）。"
        "建议关注以下因素: ① 基金季报披露的持仓变化 ② 管理费率是否有调整 ③ 市场整体估值分位。"
        "\n\n免责声明: 以上为量化信号分析，不构成投资建议。"
    )

    return DebateSignals(
        bull_signals=bull,
        bear_signals=bear,
        conclusion_framework=conclusion,
    )
