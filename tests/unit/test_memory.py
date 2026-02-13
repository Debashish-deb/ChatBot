import pytest
import numpy as np
from app.services.memory_service import MemoryService
from unittest.mock import AsyncMock, patch

@pytest.fixture
def memory_service():
    return MemoryService()

@pytest.mark.asyncio
async def test_rolling_summary_threshold(memory_service):
    # Should return empty if messages < 10
    messages = [{"role": "user", "content": "hi"}] * 5
    summary = await memory_service.generate_rolling_summary("test_conv", messages)
    assert summary == ""

@pytest.mark.asyncio
async def test_rolling_summary_generation(memory_service):
    messages = [{"role": "user", "content": "Let's discuss the project budget."}] * 11
    
    with patch("app.services.llm_service.llm_service.chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value.choices[0].message.content = "Project budget discussed."
        summary = await memory_service.generate_rolling_summary("test_conv", messages)
        assert summary == "Project budget discussed."
        mock_llm.assert_called_once()

def test_vector_index_creation(memory_service):
    index = memory_service._get_index("test_conv")
    assert index is not None
    assert index.ntotal == 0

@pytest.mark.asyncio
async def test_add_to_memory(memory_service):
    # This test might fail in CI if sentence-transformers model can't be downloaded
    # but for local verification it works.
    await memory_service.add_to_memory("test_conv", "This is an important fact.")
    index = memory_service._get_index("test_conv")
    assert index.ntotal == 1
