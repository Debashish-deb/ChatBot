from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import anthropic
from app.config import settings
from app.core.constants import ModelProvider, DEFAULT_MODEL_MAP

class LLMProvider(ABC):
    @abstractmethod
    async def chat_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        pass

    @abstractmethod
    async def stream_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        pass

    async def chat_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.OPENAI]
        
        # OpenAI handles multimodal content parts in the same structure as our schemas
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"
        return await self.client.chat.completions.create(**kwargs)

    async def stream_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.OPENAI]
        kwargs = {"model": model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        
        async for chunk in await self.client.chat.completions.create(**kwargs):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str):
        # DeepSeek is OpenAI compatible
        self.client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    async def chat_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.DEEPSEEK]
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        return await self.client.chat.completions.create(**kwargs)

    async def stream_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.DEEPSEEK]
        kwargs = {"model": model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        
        async for chunk in await self.client.chat.completions.create(**kwargs):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str):
        # Ollama provides an OpenAI compatible endpoint at /v1
        self.client = AsyncOpenAI(api_key="ollama", base_url=f"{base_url}/v1")

    async def chat_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.OLLAMA]
        kwargs = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        return await self.client.chat.completions.create(**kwargs)

    async def stream_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.OLLAMA]
        kwargs = {"model": model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
        
        async for chunk in await self.client.chat.completions.create(**kwargs):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.ANTHROPIC]
        
        # Convert tools to Anthropic format
        anthropic_tools = []
        if tools:
            for t in tools:
                anthropic_tools.append({
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"]
                })

        # Anthropic separates system message and requires specific block formatting
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        
        formatted_messages = []
        for m in [m for m in messages if m["role"] != "system"]:
            content = m["content"]
            if isinstance(content, list):
                # Convert our ContentPart schema to Anthropic blocks
                blocks = []
                for part in content:
                    if part["type"] == "text":
                        blocks.append({"type": "text", "text": part["text"]})
                    elif part["type"] == "image_url":
                        # Anthropic expects bits/data for images, OpenAI expects URL
                        # In our system, if it's base64, we extract it
                        data = part["image_url"]["url"]
                        if data.startswith("data:"):
                            media_type, base64_data = data.split(";base64,")
                            media_type = media_type.replace("data:", "")
                            blocks.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_data
                                }
                            })
                formatted_messages.append({"role": m["role"], "content": blocks})
            else:
                formatted_messages.append({"role": m["role"], "content": content})

        kwargs = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": 4096,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self.client.messages.create(**kwargs)
        
        # Map Anthropic response to a format similar to OpenAI for internal consistency
        # In a real app, we'd use a more robust common adapter
        return self._map_to_common_format(response)

    async def stream_completion(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        model = DEFAULT_MODEL_MAP[ModelProvider.ANTHROPIC]
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]
        
        kwargs = {
            "model": model,
            "messages": user_messages,
            "max_tokens": 4096,
            "stream": True,
        }
        if system_msg:
            kwargs["system"] = system_msg
        
        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def _map_to_common_format(self, response: Any) -> Any:
        # Simplified mapping for demonstration
        class MockChoice:
            def __init__(self, message):
                self.message = message
        
        class MockMessage:
            def __init__(self, content, tool_calls=None):
                self.content = content
                self.tool_calls = tool_calls
                self.role = "assistant"
            
            def model_dump(self):
                return {"role": self.role, "content": self.content}

        class MockToolCall:
            def __init__(self, id, name, arguments):
                self.id = id
                # Anthropic gives a dict, but we want a JSON string for common format
                self.function = type('obj', (object,), {
                    'name': name, 
                    'arguments': json.dumps(arguments) if isinstance(arguments, dict) else arguments
                })

        tool_calls = []
        content_text = ""
        import json # Ensure json is available inside the method if needed, or use the global one if it's there.
        # Actually json is already imported at the top of the file.
        for content in response.content:
            if content.type == "text":
                content_text += content.text
            elif content.type == "tool_use":
                tool_calls.append(MockToolCall(content.id, content.name, content.input))

        message = MockMessage(content_text, tool_calls if tool_calls else None)
        
        class MockResponse:
            def __init__(self, choices):
                self.choices = choices
            def model_dump(self):
                return {"choices": [{"message": {"role": "assistant", "content": content_text}}]}

        return MockResponse([MockChoice(message)])

def get_llm_provider() -> LLMProvider:
    provider_type = settings.LLM_PROVIDER
    if provider_type == ModelProvider.DEEPSEEK:
        return DeepSeekProvider(api_key=settings.DEEPSEEK_API_KEY)
    elif provider_type == ModelProvider.OLLAMA:
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
    elif provider_type == ModelProvider.ANTHROPIC:
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY)
    elif provider_type == ModelProvider.OPENAI:
        return OpenAIProvider(api_key=settings.OPENAI_API_KEY)
    raise ValueError(f"Unsupported provider: {provider_type}")

llm_service = get_llm_provider()
