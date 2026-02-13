import json
import uuid
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy import select
from jsonschema import validate, ValidationError
from app.services.llm_service import llm_service
from app.services.mcp_orchestrator import mcp_orchestrator
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
        """Process a single tool call with validation, retries, and persistence"""
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        status = "success"
        error_msg = None
        result_content = None
        server_name = "local"
        
        try:
            # 1. Find Tool Definition for validation
            local_tool = tool_registry.get_tool(tool_name)
            target_mcp_tool = next((t for t in mcp_tools if t["name"] == tool_name), None)
            
            schema = None
            if local_tool:
                schema = local_tool.input_schema
            elif target_mcp_tool:
                schema = target_mcp_tool.get("input_schema")
                server_name = target_mcp_tool.get("server_name", "unknown")

            # 2. Strict Schema Validation
            if schema:
                try:
                    validate(instance=tool_args, schema=schema)
                except ValidationError as ve:
                    status = "error"
                    error_msg = f"Schema validation failed: {ve.message}"
                    result_content = {"error": error_msg}
            
            # 3. Execution (with simple retry logic for transient errors)
            if status == "success":
                for attempt in range(2): # 2 attempts
                    try:
                        if local_tool:
                            result_content = await local_tool.execute(**tool_args)
                        elif target_mcp_tool:
                            result_content = await mcp_orchestrator.call_mcp_tool(server_name, tool_name, tool_args)
                        else:
                            status = "error"
                            error_msg = f"Tool {tool_name} not found"
                            result_content = {"error": error_msg}
                        break # Success
                    except Exception as e:
                        if attempt == 0:
                            logger.warning(f"Retrying tool {tool_name} after error: {e}")
                            await asyncio.sleep(1)
                            continue
                        raise # Rethrow on last attempt

        except Exception as e:
            status = "error"
            error_msg = str(e)
            result_content = {"error": error_msg}
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 4. Persistence
        async with get_db_context() as db:
            execution = ToolExecution(
                id=execution_id,
                conversation_id=conversation_id,
                tool_name=tool_name,
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
            "name": tool_name,
            "content": json.dumps(result_content)
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

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        # Fetch tools
        local_tools = tool_registry.list_tools()
        mcp_tools = await mcp_orchestrator.list_all_tools()
        combined_tools = local_tools + mcp_tools
        
        response = await llm_service.chat_completion(
            messages=formatted_messages,
            tools=combined_tools
        )
        
        message = response.choices[0].message
        
        # Handle tool calls in PARALLEL
        if message.tool_calls:
            formatted_messages.append(message.model_dump())
            
            # Execute all tool calls concurrently
            tool_tasks = [
                self._process_tool_call(tc, conversation.id, mcp_tools) 
                for tc in message.tool_calls
            ]
            tool_results = await asyncio.gather(*tool_tasks)
            
            # Add all results to history
            formatted_messages.extend(tool_results)
            
            # Final response after parallel tool execution(s)
            response = await llm_service.chat_completion(messages=formatted_messages)
            message = response.choices[0].message

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

        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
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
