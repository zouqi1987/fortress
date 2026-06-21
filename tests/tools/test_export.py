"""Unit tests for report export — verify HTML wrapping and file output."""
from pathlib import Path
from tempfile import mkdtemp

from src.tools.export import export_report


class TestExportReport:
    def test_saves_html_file(self):
        tmp = Path(mkdtemp())
        output = tmp / "test_report.html"
        try:
            result = export_report("<h2>测试报告</h2>", str(output))
            assert output.exists()
            assert output.stat().st_size > 0
            assert result["file_path"] == str(output)
            assert result["size_bytes"] == output.stat().st_size
        finally:
            output.unlink(missing_ok=True)
            tmp.rmdir()

    def test_message_includes_path_and_pdf_instructions(self):
        tmp = Path(mkdtemp())
        output = tmp / "test_report.html"
        try:
            result = export_report("<h2>测试报告</h2>", str(output))
            assert str(output) in result["message"]
            assert "打印为 PDF" in result["message"]
            assert result["size_bytes"] > 0
        finally:
            output.unlink(missing_ok=True)
            tmp.rmdir()

    def test_creates_parent_directories(self):
        import shutil
        tmp = Path(mkdtemp())
        nested = tmp / "a" / "b" / "report.html"
        try:
            result = export_report("<h2>测试</h2>", str(nested))
            assert nested.exists()
        finally:
            shutil.rmtree(tmp)

    def test_includes_print_css(self):
        tmp = Path(mkdtemp())
        output = tmp / "test_report.html"
        try:
            export_report("<h2>测试报告</h2>", str(output))
            content = output.read_text(encoding="utf-8")
            assert "@media print" in content
            assert "@page" in content
            assert "size: A4" in content
        finally:
            output.unlink(missing_ok=True)
            tmp.rmdir()

    def test_includes_custom_title(self):
        tmp = Path(mkdtemp())
        output = tmp / "test_report.html"
        try:
            export_report("<h2>测试</h2>", str(output), title="自定义标题")
            content = output.read_text(encoding="utf-8")
            assert "<title>自定义标题</title>" in content
        finally:
            output.unlink(missing_ok=True)
            tmp.rmdir()
