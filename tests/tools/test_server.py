"""Tests for MCP server — FastMCP tool registration and invocation."""
import pytest


class TestMCPServer:
    def test_server_creation(self):
        from src.tools.server import server
        assert server is not None
        assert server.name == "fortress"

    def test_all_six_tools_registered(self):
        from src.tools.server import server
        from mcp.server.fastmcp.tools.tool_manager import ToolManager

        tools = server._tool_manager.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "assess_risk",
            "get_allocation",
            "get_advice",
            "audit_single_fund",
            "run_scenario",
            "lookup_fund",
        }
        assert expected.issubset(tool_names), f"Missing: {expected - tool_names}"

    @pytest.mark.parametrize("tool_name", [
        "assess_risk",
        "get_allocation",
        "get_advice",
        "audit_single_fund",
        "run_scenario",
        "lookup_fund",
    ])
    def test_each_tool_has_description(self, tool_name):
        from src.tools.server import server

        tools = server._tool_manager.list_tools()
        tool = next(t for t in tools if t.name == tool_name)
        assert tool.description, f"{tool_name} missing description"
        assert len(tool.description) > 10, f"{tool_name} description too short"

    @pytest.mark.parametrize("tool_name", [
        "assess_risk",
        "get_allocation",
        "get_advice",
        "audit_single_fund",
        "run_scenario",
        "lookup_fund",
    ])
    def test_each_tool_has_parameters(self, tool_name):
        from src.tools.server import server

        tools = server._tool_manager.list_tools()
        tool = next(t for t in tools if t.name == tool_name)
        assert tool.parameters is not None, f"{tool_name} missing parameters"
        assert "properties" in tool.parameters, f"{tool_name} schema missing properties"
