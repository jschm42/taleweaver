import os
import json
import datetime
import logging

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "llm_debug.jsonl")

logger = logging.getLogger(__name__)

def log_llm_interaction(
    model: str, 
    provider: str, 
    system_prompt: str, 
    user_prompt: str, 
    response_content: str,
    raw_response: dict = None
):
    """
    Logs an LLM interaction to a local JSONL file for debugging.
    """
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
        
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": model,
        "provider": provider,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response_content,
        "raw_response": raw_response
    }
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to LLM debug log: {e}")
