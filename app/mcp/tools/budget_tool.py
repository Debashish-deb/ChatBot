from app.mcp.tools.base import BaseMCPTool
from app.mcp.tools.registry import tool_registry
from typing import Dict, Any

class BudgetTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "get_budget_status"

    @property
    def description(self) -> str:
        return "Get the current budget status for a specific category (e.g., travel, food, software)."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The budget category to check."
                }
            },
            "required": ["category"]
        }

    async def execute(self, category: str) -> Dict[str, Any]:
        budgets = {
            "travel": {"amount": 2000.0, "spent": 1450.0, "remaining": 550.0},
            "food": {"amount": 500.0, "spent": 320.0, "remaining": 180.0},
            "software": {"amount": 1000.0, "spent": 450.0, "remaining": 550.0}
        }
        status = budgets.get(category.lower())
        if not status:
            return {"error": f"Category {category} not found."}
        return {"category": category, "status": status}

# Register the tool
tool_registry.register(BudgetTool())
