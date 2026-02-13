import json
import uuid
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy import select
from jsonschema import validate, ValidationError
from app.services.llm_service import llm_service
from app.services.mcp_orchestrator import mcp_orchestrator
from app.services.intelligence import intelligence_service
from app.mcp.tools.registry import tool_registry
from app.models.schemas import ChatMessage
from app.models.database import Conversation, Message, User, ToolExecution
from app.database import get_db_context
from app.logging_config import logger
import time

class ChatService:
    async def get_or_create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> Conversation:
        async with get_db_context() as db:
            if conversation_id:
                result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
                conversation = result.scalar_one_or_none()
                if conversation:
                    return conversation
            
            new_id = conversation_id or str(uuid.uuid4())
            conversation = Conversation(id=new_id, user_id=user_id, title="New Conversation")
            db.add(conversation)
            await db.commit()
            return conversation

    async def _process_tool_call(
        self, 
        tool_call: Any, 
        conversation_id: str, 
        mcp_tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a single tool call with validation, fuzzy matching, and persistence"""
        original_tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        status = "success"
        error_msg = None
        result_content = None
        server_name = "local"
        
        try:
            # 1. Resolve Tool (with Fuzzy Matching)
            local_tool = tool_registry.get_tool(original_tool_name)
            target_mcp_tool = next((t for t in mcp_tools if t["name"] == original_tool_name), None)
            
            resolved_name = original_tool_name
            if not local_tool and not target_mcp_tool:
                # Try fuzzy match
                available_names = [t["name"] for t in tool_registry.list_tools()] + [t["name"] for t in mcp_tools]
                fuzzy_name = intelligence_service.find_fuzzy_match(original_tool_name, available_names)
                if fuzzy_name:
                    resolved_name = fuzzy_name
                    local_tool = tool_registry.get_tool(resolved_name)
                    target_mcp_tool = next((t for t in mcp_tools if t["name"] == resolved_name), None)
                    logger.info(f"Corrected tool name '{original_tool_name}' to '{resolved_name}'")

            # 2. Get Schema for validation
            schema = None
            if local_tool:
                schema = local_tool.input_schema
            elif target_mcp_tool:
                schema = target_mcp_tool.get("input_schema")
                server_name = target_mcp_tool.get("server_name", "unknown")

            # 3. Strict Schema Validation
            if schema:
                try:
                    validate(instance=tool_args, schema=schema)
                except ValidationError as ve:
                    status = "error"
                    error_msg = f"Schema validation failed: {ve.message}. Please check parameter types and required fields."
                    result_content = {"error": error_msg}
            
            # 4. Execution
            if status == "success":
                try:
                    if local_tool:
                        result_content = await local_tool.execute(**tool_args)
                    elif target_mcp_tool:
                        result_content = await mcp_orchestrator.call_mcp_tool(server_name, resolved_name, tool_args)
                    else:
                        status = "error"
                        error_msg = f"Tool '{original_tool_name}' not found."
                        result_content = {"error": error_msg}
                except Exception as e:
                    status = "error"
                    error_msg = str(e)
                    result_content = {"error": error_msg}

        except Exception as e:
            status = "error"
            error_msg = str(e)
            result_content = {"error": error_msg}
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 5. Persistence
        async with get_db_context() as db:
            execution = ToolExecution(
                id=execution_id,
                conversation_id=conversation_id,
                tool_name=resolved_name,
                server_name=server_name,
                arguments=tool_args,
                result=result_content,
                status=status,
                error_message=error_msg,
                duration_ms=duration_ms,
                completed_at=datetime.utcnow()
            )
            db.add(execution)
            await db.commit()

        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": resolved_name,
            "content": json.dumps(result_content),
            "status": status # Pass status for self-correction logic
        }

    async def generate_response(
        self, 
        messages: List[ChatMessage], 
        user_id: str, 
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        conversation = await self.get_or_create_conversation(user_id, conversation_id)
        
        # Save user message
        async with get_db_context() as db:
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=messages[-1].content
            )
            db.add(user_msg)
            await db.commit()

        # 1. Intent Detection & System Prompt Enhancement
        intent = intelligence_service.detect_intent(messages[-1].content)
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        if intent == "planning":
            formatted_messages.insert(0, {"role": "system", "content": "The user is asking for a plan or strategy. Be comprehensive and structured in your response."})
        elif intent == "coding":
            formatted_messages.insert(0, {"role": "system", "content": "The user is asking for coding help. Provide clean, efficient code with explanations if needed."})

        # Fetch tools
        local_tools = tool_registry.list_tools()
        mcp_tools = await mcp_orchestrator.list_all_tools()
        combined_tools = local_tools + mcp_tools
        
        # Initial call
        response = await llm_service.chat_completion(
            messages=formatted_messages,
            tools=combined_tools
        )
        
        message = response.choices[0].message
        
        # Handle tool calls with SELF-CORRECTION loop
        max_corrections = 2
        for _ in range(max_corrections):
            if not message.tool_calls:
                break
                
            formatted_messages.append(message.model_dump())
            
            # Parallel execution
            tool_tasks = [
                self._process_tool_call(tc, conversation.id, mcp_tools) 
                for tc in message.tool_calls
            ]
            tool_results = await asyncio.gather(*tool_tasks)
            
            # Prepare results for history (remove internal 'status' before sending to LLM)
            has_error = False
            error_details = []
            for res in tool_results:
                status = res.pop("status")
                if status == "error":
                    has_error = True
                    error_details.append(res["content"])
                formatted_messages.append(res)
            
            if has_error:
                # Inject a correction hint
                formatted_messages.append({
                    "role": "system", 
                    "content": f"Some tools failed with errors: {error_details}. Please analyze the errors and refactor your request if possible."
                })
            
            # Call LLM again
            response = await llm_service.chat_completion(messages=formatted_messages, tools=combined_tools)
            message = response.choices[0].message
            
            if not has_error: # If no error, we proceed or exit loop if no more tool calls
                break

        # Save assistant response
        async with get_db_context() as db:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=message.content or "",
                tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None
            )
            db.add(assistant_msg)
            await db.commit()
            
        return response.model_dump()

    async def generate_response_stream(
        self,
        messages: List[ChatMessage],
        user_id: str,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[Dict[str, Any], None]:
        conversation = await self.get_or_create_conversation(user_id, conversation_id)
        
        async with get_db_context() as db:
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=messages[-1].content
            )
            db.add(user_msg)
            await db.commit()

        # Simple intent detection for streaming too
        intent = intelligence_service.detect_intent(messages[-1].content)
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        if intent != "general":
            formatted_messages.insert(0, {"role": "system", "content": f"Intent detected: {intent}. Tailor your response accordingly."})

        collected_tokens = []
        async for token in llm_service.stream_completion(formatted_messages):
            collected_tokens.append(token)
            yield {
                "type": "token",
                "content": token,
                "conversation_id": conversation.id
            }

        async with get_db_context() as db:
            full_content = "".join(collected_tokens)
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_content
            )
            db.add(assistant_msg)
            await db.commit()
            
        yield {
            "type": "done",
            "conversation_id": conversation.id
        }

    async def regenerate_last_response(self, conversation_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        async with get_db_context() as db:
            result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc())
            )
            last_msg = result.scalars().first()
            
            if last_msg and last_msg.role == "assistant":
                await db.delete(last_msg)
                await db.commit()
            
            history_result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
            )
            messages = history_result.scalars().all()
            chat_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
            
            return await self.generate_response(chat_messages, user_id, conversation_id, **kwargs)

    async def continue_conversation(self, conversation_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        async with get_db_context() as db:
            history_result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
            )
            messages = history_result.scalars().all()
            chat_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
            
            return await self.generate_response(chat_messages, user_id, conversation_id, **kwargs)

chat_service = ChatService()
