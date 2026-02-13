import difflib
from typing import List, Dict, Any, Optional
from app.logging_config import logger

class IntelligenceService:
    def __init__(self):
        self.intent_keywords = {
            "planning": ["plan", "how to", "steps", "strategy", "roadmap", "design"],
            "execution": ["do", "run", "execute", "create", "make", "build"],
            "research": ["find", "search", "lookup", "who", "what is", "tell me about"],
            "coding": ["code", "python", "javascript", "script", "function", "class", "bug", "fix"]
        }

    def detect_intent(self, user_input: str) -> str:
        """Simple keyword-based intent detection"""
        user_input = user_input.lower()
        scores = {intent: 0 for intent in self.intent_keywords}
        
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in user_input:
                    scores[intent] += 1
        
        # Default to general chat if no clear intent
        max_intent = max(scores, key=scores.get)
        if scores[max_intent] == 0:
            return "general"
        return max_intent

    def find_fuzzy_match(self, tool_name: str, available_tools: List[str], threshold: float = 0.7) -> Optional[str]:
        """Find a close match for a tool name if it's misspelled"""
        matches = difflib.get_close_matches(tool_name, available_tools, n=1, cutoff=threshold)
        if matches:
            logger.info(f"Fuzzy matched tool '{tool_name}' to '{matches[0]}'")
            return matches[0]
        return None

intelligence_service = IntelligenceService()
