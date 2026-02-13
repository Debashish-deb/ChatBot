import json
from typing import List, Dict, Any
from app.services.llm_service import llm_service
from app.services.mcp_orchestrator import mcp_orchestrator
from app.mcp.tools.registry import tool_registry
from app.models.schemas import ChatMessage
from app.logging_config import logger

class ChatService:
    async def generate_response(self, messages: List[ChatMessage]) -> Dict[str, Any]:
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        # 1. Fetch local tools
        local_tools = tool_registry.list_tools()
        
        # 2. Fetch remote MCP tools
        try:
            mcp_tools = await mcp_orchestrator.list_all_tools()
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            mcp_tools = []

        # 3. Combine tools for the LLM
        # Note: We need to ensure LLM tool definitions are consistent
        # For remote MCP tools, we've already added 'server_name' to the metadata
        combined_tools = local_tools + mcp_tools
        
        response = await llm_service.chat_completion(
            messages=formatted_messages,
            tools=combined_tools
        )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            formatted_messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Routing logic
                # First, check local registry
                local_tool = tool_registry.get_tool(tool_name)
                if local_tool:
                    logger.info(f"Executing LOCAL tool: {tool_name}")
                    result = await local_tool.execute(**tool_args)
                else:
                    # Second, search in MCP tools to find the server_name
                    # In a high-traffic app, we'd cache this mapping
                    target_mcp_tool = next((t for t in mcp_tools if t["name"] == tool_name), None)
                    if target_mcp_tool and "server_name" in target_mcp_tool:
                        server_name = target_mcp_tool["server_name"]
                        logger.info(f"Executing REMOTE MCP tool: {tool_name} on server: {server_name}")
                        result = await mcp_orchestrator.call_mcp_tool(server_name, tool_name, tool_args)
                    else:
                        result = {"error": f"Tool {tool_name} not found in local or remote registries."}
                
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result)
                })
            
            # Final response after tool execution(s)
            final_response = await llm_service.chat_completion(messages=formatted_messages)
            return final_response.model_dump()
            
        return response.model_dump()

chat_service = ChatService()
