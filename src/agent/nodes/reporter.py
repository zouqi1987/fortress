"""Reporter node — renders the final HTML report via Jinja2 template.

Pure function: (state) → state_update dict.
Active on all paths.  Uses src/report/context.py for data formatting
and src/report/templates/report.html for layout.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.agent.state import ConversationState
from src.report.context import build_context

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "report" / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def reporter_node(state: ConversationState) -> dict:
    """Generate the final HTML report from all collected analysis results.

    Uses Jinja2 templates (base.html + report.html) with pre-formatted context.
    """
    ctx = build_context(state)
    template = _env.get_template("report.html")
    report_html = template.render(**ctx)
    return {"report_html": report_html}
