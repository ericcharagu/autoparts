from typing import Dict, List

import qdrant_client.http.exceptions
from loguru import logger
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient, models
from utils.vector_db.qdrant import standard_retriever

# initiate logging
logger.add("./logs/history_vector.log", rotation="1 week")