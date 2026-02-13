from typing import Dict, Type
from app.mcp.tools.base import BaseMCPTool

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseMCPTool] = {}

    def register(self, tool: BaseMCPTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseMCPTool:
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, Any]:
        # Return tools in standard tool format for LLM
        return [tool.to_mcp_schema() for tool in self._tools.values()]

tool_registry = ToolRegistry()
