import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.chat_service import ChatService
from app.models.schemas import ChatMessage

@pytest.fixture
def chat_service():
    return ChatService()

@pytest.mark.asyncio
async def test_generate_response_basic(chat_service):
    user_id = "test_user"
    messages = [ChatMessage(role="user", content="Hello")]

    with patch("app.services.llm_service.llm_service.chat_completion", new_callable=AsyncMock) as mock_llm:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hi there!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model_dump.return_value = {"choices": [{"message": {"role": "assistant", "content": "Hi there!"}}]}
        mock_llm.return_value = mock_response

        response = await chat_service.generate_response(messages, user_id)
        assert response["choices"][0]["message"]["content"] == "Hi there!"

@pytest.mark.asyncio
async def test_chat_flow_with_self_correction(chat_service):
    user_id = "test_user"
    messages = [ChatMessage(role="user", content="Search for AI news")]

    with patch("app.services.llm_service.llm_service.chat_completion", new_callable=AsyncMock) as mock_llm:
        # 1. First response: Tool call that fails validation
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "web_search"
        mock_tool_call.function.arguments = json.dumps({"query": 123}) # Wrong type (int instead of str)
        mock_tool_call.model_dump.return_value = {"id": "call_123", "function": {"name": "web_search", "arguments": '{"query": 123}'}, "type": "function"}

        mock_resp1 = MagicMock()
        mock_resp1.choices[0].message.content = None
        mock_resp1.choices[0].message.tool_calls = [mock_tool_call]
        mock_resp1.choices[0].message.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": [mock_tool_call.model_dump()]}

        # 2. Second response: LLM corrects itself
        mock_resp2 = MagicMock()
        mock_resp2.choices[0].message.content = "Here are the AI news results..."
        mock_resp2.choices[0].message.tool_calls = None
        mock_resp2.model_dump.return_value = {"choices": [{"message": {"role": "assistant", "content": "Here are the AI news results..."}}]}

        mock_llm.side_effect = [mock_resp1, mock_resp2]

        # Mock the tool call execution (schema validation fail)
        with patch("app.services.chat_service.validate") as mock_validate:
            from jsonschema import ValidationError
            mock_validate.side_effect = ValidationError("query must be string")

            response = await chat_service.generate_response(messages, user_id)
            
            # Verify that LLM was called twice (initial + correction)
            assert mock_llm.call_count == 2
            assert response["choices"][0]["message"]["content"] == "Here are the AI news results..."
