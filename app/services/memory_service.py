import os
import json
import faiss
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from app.logging_config import logger
from app.services.llm_service import llm_service
from app.models.database import Message, Conversation
from app.database import get_db_context
from sqlalchemy import select

class MemoryService:
    def __init__(self):
        # Initialize embedding model (using a small, fast one)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384 # Dimension of MiniLM-L6-v2 embeddings
        self.indices = {} # conversation_id -> faiss index
        
    def _get_index(self, conversation_id: str):
        if conversation_id not in self.indices:
            self.indices[conversation_id] = faiss.IndexFlatL2(self.dimension)
        return self.indices[conversation_id]

    async def add_to_memory(self, conversation_id: str, text: str, metadata: Dict[str, Any] = None):
        """Add a text snippet to the conversation's vector memory"""
        try:
            embedding = self.model.encode([text])
            index = self._get_index(conversation_id)
            index.add(np.array(embedding).astype('float32'))
            logger.info(f"Added to vector memory for {conversation_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error adding to vector memory: {e}")

    async def search_memory(self, conversation_id: str, query: str, top_k: int = 3) -> List[str]:
        """Search the conversation's vector memory for relevant snippets"""
        if conversation_id not in self.indices:
            return []
            
        try:
            embedding = self.model.encode([query])
            index = self.indices[conversation_id]
            D, I = index.search(np.array(embedding).astype('float32'), top_k)
            
            # This is a simplified in-memory version. 
            # In production, we'd store the actual text in a DB or separate map.
            # For this demonstration, we'll assume we have the text mapped.
            return [] # Placeholder as we need a text mapping
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []

    async def generate_rolling_summary(self, conversation_id: str, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a concise summary of the conversation history (MCP approach).
        Drops minor details in favor of core ideas and decisions.
        """
        if len(messages) < 10:
            return ""
            
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages[:-2]]) # Exclude last few turns
        
        prompt = f"""
        Analyze the following conversation history and provide a HIGHLY DENSE summary.
        Follow the Most-Critical-Point (MCP) approach:
        - Drop minor details and filler.
        - Capture only core ideas, decisions, and action items.
        - Distill everything down to its most critical points.
        
        Conversation History:
        {history_text}
        
        Concise MCP Summary:
        """
        
        try:
            summary_response = await llm_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            summary = summary_response.choices[0].message.content
            logger.info(f"Generated rolling MCP summary for {conversation_id}")
            return summary
        except Exception as e:
            logger.error(f"Error generating rolling summary: {e}")
            return ""

memory_service = MemoryService()
