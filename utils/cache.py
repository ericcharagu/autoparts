# ericcharagu-autoparts/utils/cache.py
from dependancies import embedding_client
import redis.asyncio as redis
from loguru import logger
import json
import os

from utils.db.qdrant import embedding_model_name

MESSAGE_ID_EXPIRATION_SECONDS = 300
async def is_message_processed(client: redis.Redis, message_id: str) -> bool:
    key = f"processed_wamid:{message_id}"
    # It will only succeed (return True) if the key does not already exist.
    was_set = await client.set(key, 1, ex=MESSAGE_ID_EXPIRATION_SECONDS, nx=True)
    if was_set:
        logger.info(f"New message ID acquired for processing: {message_id}")
        return True
    
    logger.warning(f"Duplicate message ID detected and ignored: {message_id}")
    return False

async def get_chat_history(client:redis.Redis, user_number: str, limit: int = 5) -> list:
    """Retrieves the last N messages for a user from Valkey."""
    key = f"chat_history:{user_number}"
    try:
        # LTRIM keeps the list size fixed, preventing it from growing indefinitely
        await client.ltrim(key, 0, limit - 1) 
        history_json = await client.lrange(key, 0, limit - 1)
        # Messages are stored as JSON strings, so we parse them back
        history = [json.loads(msg) for msg in history_json]
        history.reverse() # Reverse to get the chronological order
        logger.info(f"Retrieved {len(history)} messages for user {user_number}")
        return history
    except Exception as e:
        logger.error(f"Failed to get chat history for {user_number}: {e}")
        return []

async def add_to_chat_history(client:redis.Redis, user_number: str, user_message: str, llm_response: str):
    """Adds a new user/llm message pair to the user's chat history."""
    key = f"chat_history:{user_number}"
    message_pair = {
        "user_message": user_message, 
        "llm_response": llm_response
    }
    try:
        # LPUSH adds the new message to the beginning of the list
        await client.lpush(key, json.dumps(message_pair))
        logger.info(f"Added new message to history for user {user_number}")
    except Exception as e:
        logger.error(f"Failed to add to chat history for {user_number}: {e}")
