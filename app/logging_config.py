import logging
import sys
from typing import Any, Dict

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific levels for some libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("mcp").setLevel(logging.DEBUG)

logger = logging.getLogger("chatbot")
