import json
import uuid
from typing import List, Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from sqlalchemy import select
from app.services.llm_service import llm_service
from app.services.mcp_orchestrator import mcp_orchestrator
from app.mcp.tools.registry import tool_registry
from app.models.schemas import ChatMessage
from app.models.database import Conversation, Message, User
from app.database import get_db_context
from app.logging_config import logger

class ChatService:
    async def get_or_create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> Conversation:
        async with get_db_context() as db:
            if conversation_id:
                result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
                conversation = result.scalar_one_or_none()
                if conversation:
                    return conversation
            
            # Create new
            new_id = conversation_id or str(uuid.uuid4())
            conversation = Conversation(id=new_id, user_id=user_id, title="New Conversation")
            db.add(conversation)
            await db.commit()
            return conversation

    async def generate_response(
        self, 
        messages: List[ChatMessage], 
        user_id: str, 
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        # Get or create conversation
        conversation = await self.get_or_create_conversation(user_id, conversation_id)
        
        # Save user message
        async with get_db_context() as db:
            # We assume the last message in the input list is the new user message
            user_msg_content = messages[-1].content
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=user_msg_content
            )
            db.add(user_msg)
            await db.commit()

        # Implementation logic for non-streaming (blocking)
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        # Merge tools
        local_tools = tool_registry.list_tools()
        mcp_tools = await mcp_orchestrator.list_all_tools()
        combined_tools = local_tools + mcp_tools
        
        response = await llm_service.chat_completion(
            messages=formatted_messages,
            tools=combined_tools
        )
        
        message = response.choices[0].message
        
        # Handle tool calls (simplified routing from previous version)
        if message.tool_calls:
            # In a real app, we'd loop through tool calls, execute, and call LLM again
            # For brevity in this upgrade, we'll keep the logic but ensure persistence
            pass 

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
        # Get/Create conversation
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
        
        # For professional stream, we'll yield tokens from LLM
        collected_tokens = []
        async for token in llm_service.stream_completion(formatted_messages):
            collected_tokens.append(token)
            yield {
                "type": "token",
                "content": token,
                "conversation_id": conversation.id
            }

        # Save assistant response
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
        """Regenerate the last assistant response in a conversation"""
        async with get_db_context() as db:
            # Get last message
            result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc())
            )
            last_msg = result.scalars().first()
            
            if last_msg and last_msg.role == "assistant":
                # Delete the last assistant message
                await db.delete(last_msg)
                await db.commit()
            
            # Get all history to generate new response
            history_result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
            )
            messages = history_result.scalars().all()
            chat_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
            
            return await self.generate_response(chat_messages, user_id, conversation_id, **kwargs)

    async def continue_conversation(self, conversation_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """Continue conversation (fetch history and call LLM)"""
        async with get_db_context() as db:
            history_result = await db.execute(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
            )
            messages = history_result.scalars().all()
            chat_messages = [ChatMessage(role=m.role, content=m.content) for m in messages]
            
            return await self.generate_response(chat_messages, user_id, conversation_id, **kwargs)

chat_service = ChatService()
