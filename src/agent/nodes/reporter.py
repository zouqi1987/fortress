"""Reporter node — formats the final HTML report.

Pure function: (state) → state_update dict.
Active on all paths. Produces a self-contained HTML report fragment.
"""
from src.agent.state import ConversationState


def reporter_node(state: ConversationState) -> dict:
    """Generate the final HTML report from all collected analysis results.

    Handles all three paths gracefully — sections appear only if data exists.
    """
    sections: list[str] = []

    # Header
    path_names = {"A": "底仓配置", "B": "机会捕捉", "C": "持仓诊断"}
    path_name = path_names.get(state.get("path", ""), "分析")
    sections.append(f'<div class="report">')
    sections.append(f'<h2>📊 投资分析报告 — {path_name}</h2>')

    # 1. 持仓概览
    portfolio = state.get("portfolio")
    if portfolio:
        sections.append("<h3>📋 当前持仓</h3>")
        sections.append("<table>")
        sections.append("<tr><th>资产类别</th><th>金额</th></tr>")
        for k, v in portfolio.items():
            sections.append(f"<tr><td>{k}</td><td>{v}</td></tr>")
        sections.append("</table>")

    # 2. 风险测评
    risk = state.get("risk_profile")
    if risk:
        sections.append("<h3>⚖️ 风险测评</h3>")
        sections.append(f"<p>风险等级: <strong>{risk.level.value}</strong></p>")
        sections.append(f"<p>总分: {risk.total_score}/100</p>")

    # 3. 多空辩论 (path B)
    debate = state.get("debate_result")
    if debate:
        sections.append(debate)

    # 4. 配置建议
    plan = state.get("allocation_plan")
    if plan:
        sections.append("<h3>🏗️ 配置方案</h3>")
        sections.append(f"<p>权益: {plan.equity_pct}% | 债券: {plan.bond_pct}% | 现金: {plan.cash_pct}%</p>")
        sections.append("<ul>")
        for bucket in plan.buckets:
            sections.append(f"<li>{bucket.name}: {bucket.amount} 元</li>")
        sections.append("</ul>")

    # 5. 审计结果
    audits = state.get("audit_results")
    if audits:
        sections.append("<h3>🔍 单品审计</h3>")
        sections.append("<ul>")
        for a in audits:
            icon = "✅" if a.passed else "⚠️"
            sections.append(f"<li>{icon} {a.fund_code}: {', '.join(a.reasons) if a.reasons else '通过'}</li>")
        sections.append("</ul>")

    # 6. 压力测试
    stress = state.get("stress_result")
    if stress:
        sections.append("<h3>🌪️ 压力测试</h3>")
        sections.append(f"<p>情景: {stress.scenario_name}</p>")
        sections.append(f"<p>预估损失: {stress.total_loss} ({stress.loss_pct})</p>")

    # 7. 健康评分
    health = state.get("health_check")
    if health:
        sections.append("<h3>💚 组合健康度</h3>")
        sections.append(f"<p>综合评分: {health.overall_score}/100 (等级 {health.grade})</p>")

    # Errors
    errors = state.get("errors", [])
    if errors:
        sections.append("<h3>⚠️ 注意事项</h3>")
        sections.append("<ul>")
        for e in errors:
            sections.append(f"<li>{e}</li>")
        sections.append("</ul>")

    # Footer
    sections.append("<p><em>免责声明: 本报告不构成投资建议，投资有风险，入市需谨慎。</em></p>")
    sections.append("</div>")

    return {"report_html": "\n".join(sections)}
