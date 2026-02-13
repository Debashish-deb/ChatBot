from typing import List, Dict, Any

# These are external MCP servers we want to connect to
# The orchestrator will try to launch these as sub-processes
MCP_SERVERS = {
    "budget_service": {
        "command": "python",
        "args": ["-m", "app.mcp.tools.budget_tool"], # Launching the budget tool as a standalone MCP server process
    }
    # You can add more external servers here:
    # "database_service": { "command": "uv", "args": ["run", "mcp-server-sqlite", "--db-path", "my.db"] }
}
