"""MCP tool: report export — save HTML report to self-contained .html file.

Produces a print-friendly file that renders in browser and prints
to A4 PDF (Ctrl+P / Cmd+P).  Zero new dependencies.
"""
from pathlib import Path


_PRINT_CSS = """
@media print {
  body {
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
    margin: 2cm; color: #2c3e50; line-height: 1.6;
  }
  .report { max-width: 100%; }
  h2 {
    color: #1a5276; border-bottom: 2px solid #1a5276;
    padding-bottom: 6px;
  }
  h3 { color: #2c3e50; margin-top: 1.5em; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; }
  th, td { border: 1px solid #333; padding: 8px 12px; text-align: left; }
  th { background: #f0f0f0; }
  ul { padding-left: 1.2em; }
  li { margin: 4px 0; }
  @page { size: A4; margin: 2cm; }
}
"""


def export_report(report_html: str, output_path: str, title: str = "投资分析报告") -> dict:
    """Save the HTML report as a self-contained .html file.

    Args:
        report_html: HTML content from get_advice or an Agent tool.
        output_path: Where to save (absolute or relative to CWD).
        title: Page title shown in the browser tab and print header.

    Returns:
        dict with file_path, size_bytes, and message.
    """
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    document = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
    max-width: 900px; margin: 0 auto; padding: 2em;
    color: #2c3e50; line-height: 1.6;
  }}
  h2 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 6px; }}
  h3 {{ color: #2c3e50; margin-top: 1.5em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  p {{ margin: 0.5em 0; }}
  ul {{ padding-left: 1.2em; }}
  li {{ margin: 4px 0; }}
{_PRINT_CSS}
</style>
</head>
<body>
{report_html}
</body>
</html>"""

    path.write_text(document, encoding="utf-8")
    size = path.stat().st_size

    return {
        "file_path": str(path),
        "size_bytes": size,
        "message": f"报告已保存到 {path}（{size} bytes）。用浏览器打开后 Ctrl+P 即可打印为 PDF。",
    }
