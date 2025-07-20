<<<<<<< HEAD
# ericcharagu-autoparts/utils/cache.py
from dependancies import embedding_client
=======
#!/usr/bin/env python3

>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
import redis.asyncio as redis
from loguru import logger
import json
import os

<<<<<<< HEAD
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
=======
VALKEY_HOST = os.getenv("VALKEY_HOST", "valkey_server")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", 6379))
MESSAGE_ID_EXPIRATION_SECONDS = 300
# Create a connection pool
pool = redis.ConnectionPool(
    host=VALKEY_HOST, port=VALKEY_PORT, db=0, decode_responses=True
)


async def get_redis_client():
    """Returns a Redis client from the connection pool."""
    return redis.Redis(connection_pool=pool)


async def is_message_processed(message_id: str) -> bool:
    """
    Checks if a message ID has been processed. Returns True if it's new, False if it's a duplicate.
    Uses a Redis Set to atomically check and set.
    """
    client = await get_redis_client()
    key = "processed_message_ids"
    # SADD returns 1 if the element was added (it's new), 0 if it already existed (it's a duplicate).
    if await client.sadd(key, message_id) == 1:
        await client.expire(key, MESSAGE_ID_EXPIRATION_SECONDS)
        logger.info(f"New message ID received: {message_id}")
        return True  # It's a new message

    logger.warning(f"Duplicate message ID detected and ignored: {message_id}")
    return False  # It's a duplicate


async def get_chat_history(user_number: str, limit: int = 4) -> list:
    """Retrieves the last N messages for a user from Valkey."""
    client = await get_redis_client()
    key = f"chat_history:{user_number}"
    try:
        # LTRIM keeps the list size fixed, preventing it from growing indefinitely
        await client.ltrim(key, 0, limit - 1)
        history_json = await client.lrange(key, 0, limit - 1)
        # Messages are stored as JSON strings, so we parse them back
        history = [json.loads(msg) for msg in history_json]
        history.reverse()  # Reverse to get the chronological order
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
        logger.info(f"Retrieved {len(history)} messages for user {user_number}")
        return history
    except Exception as e:
        logger.error(f"Failed to get chat history for {user_number}: {e}")
        return []

<<<<<<< HEAD
async def add_to_chat_history(client:redis.Redis, user_number: str, user_message: str, llm_response: str):
    """Adds a new user/llm message pair to the user's chat history."""
    key = f"chat_history:{user_number}"
    message_pair = {
        "user_message": user_message, 
        "llm_response": llm_response
=======

async def add_to_chat_history(
    user_number: str,
    user_message_embedded: list[float],
    llm_response_embedded: list[float],
):
    """Adds a new user/llm message pair to the user's chat history."""
    client = await get_redis_client()
    key = f"chat_history:{user_number}"
    message_pair = {
        "user_message_embedded": user_message_embedded,
        "llm_response_embedded": llm_response_embedded,
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
    }
    try:
        # LPUSH adds the new message to the beginning of the list
        await client.lpush(key, json.dumps(message_pair))
        logger.info(f"Added new message to history for user {user_number}")
    except Exception as e:
<<<<<<< HEAD
        logger.error(f"Failed to add to chat history for {user_number}: {e}")
=======
        logger.error(f"Failed to add to chat history for {user_number}: {e}")
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
