from app.mcp.tools.registry import tool_registry
from app.mcp.tools.search import SearchTool, ReverseImageSearchTool
from app.mcp.tools.media_tools import PDFReadTool, OCRTool

def register_local_tools():
    tool_registry.register(SearchTool())
    tool_registry.register(ReverseImageSearchTool())
    tool_registry.register(PDFReadTool())
    tool_registry.register(OCRTool())

register_local_tools()
