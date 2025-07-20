from typing import Dict, List

import qdrant_client.http.exceptions
from loguru import logger
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient, models
from schemas import ConversationData
# initiate logging
logger.add("./logs/db.log", rotation="1 week")
# Constants
QDRANT_HOST = "http://qdrant:6333"
EMBEDDING_HOST = "http://ollama_embedding:11434"
COLLECTION_NAME = "autoparts_test"
DIMENSION = 768
CHUNK_SIZE = 200


class HybridRetriever:
    def __init__(
        self,
        collection_name: str = COLLECTION_NAME,
        dimension: int = DIMENSION,
        chunk_size: int = CHUNK_SIZE,
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self.chunk_size = chunk_size
        self.client = None
        self.embedding_client = AsyncClient(host=EMBEDDING_HOST)
        self.vector_cache: Dict[str, List[Dict]] = {}

    async def initialize(self):
        """Initialize the Qdrant client connection"""
        try:
            self.client = AsyncQdrantClient(url=QDRANT_HOST, timeout=60.0)
            # Test the connection
            await self.client.get_collections()
            logger.info("Qdrant client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    async def _get_embedding(self, text: str) -> List[float]:
        """Helper method to get embeddings for text"""
        try:
            response = await self.embedding_client.embeddings(
                model="nomic-embed-text", prompt=text
            )
            return response["embedding"]
        except Exception as e:
            logger.debug(f"Embedding error for text: {str(e)}")
            raise

    async def chunk_chat_history(self, conversation_data:ConversationData, collection_name:str)->dict:
        """Embed and store the message pair"""
        user_message_embedding=self._get_embedding(conversation_data.user_message)
        llm_response_embedding=self._get_embedding(conversation_data.llm_response)
        conversation_data.append({"user_message_embedding":user_message_embedding, "llm_response_embedding":llm_response_embedding})
        return conversation_data
        
    async def initialize_knowledge_base(self, knowledge_paths) -> List[Dict]:
        """Process files and create chunks with embeddings"""
        chunks = []
        chunk_id = 0

        for path in knowledge_paths:
            try:
                with open(path, "r", encoding="UTF-8") as file:
                    text = file.read()
                    for i in range(0, len(text), self.chunk_size):
                        chunk_content = text[i : i + self.chunk_size]
                        embedding = await self._get_embedding(chunk_content)

                        chunks.append(
                            {
                                "id": chunk_id,
                                "text": chunk_content,
                                "vector": embedding,
                                "source_file": path,
                            }
                        )
                        chunk_id += 1
            except ValueError as e:
                logger.exception(f"Error processing {path}: {str(e)}")
                continue

        return chunks

    async def setup_qdrant_collection(self, chunks: List[Dict], collection_name:str) -> bool:
        try:
            # Ensure client is initialized
            if self.client is None:
                await self.initialize()

            # Create collection
            collection_params = dict(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE
                ),
            )
            try:
                await self.client.create_collection(**collection_params)
                logger.info(f"Created new collection: {collection_name}")
            except qdrant_client.http.exceptions.UnexpectedResponse as e:
                if "already exists" in str(e):
                    logger.info(f"Collection {self.collection_name} already exists")
                    await self.client.delete_collection(collection_name)
                    await self.client.create_collection(**collection_params)
                else:
                    raise
            points = [
                models.PointStruct(
                    id=chunk["id"],
                    vector=chunk["vector"],
                    payload={
                        "text": chunk["text"],
                        "source_file": chunk["source_file"],
                    },
                )
                for chunk in chunks
            ]
            # Verify client connection
            if not self.client:
                raise ValueError("Qdrant client is not initialized")
            # Upload points
            self.client.upload_points(
                collection_name=collection_name,
                points=points,
                wait=True,  # Wait until the operation is completed
            )

        except ValueError as e:
            logger.debug(f"Failed to setup Qdrant collection: {str(e)}")
            logger.debug(f"Collection: {collection_name}, Chunks: {len(chunks)}")
async def setup_history_collection(self, chunks: List[Dict], collection_name:str) -> bool:
        try:
            # Ensure client is initialized
            if self.client is None:
                await self.initialize()

            # Create collection
            collection_params = dict(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE
                ),
            )
            try:
                await self.client.create_collection(**collection_params)
                logger.info(f"Created new collection: {collection_name}")
            except qdrant_client.http.exceptions.UnexpectedResponse as e:
                if "already exists" in str(e):
                    logger.info(f"Collection {self.collection_name} already exists")
                    await self.client.delete_collection(collection_name)
                    await self.client.create_collection(**collection_params)
                else:
                    raise
            points = [
                models.PointStruct(
                    id=chunk["id"],
                    vector=chunk["vector"],
                    payload={
                        "text": chunk["text"],
                        "source_file": chunk["source_file"],
                    },
                )
                for chunk in chunks
            ]
            # Verify client connection
            if not self.client:
                raise ValueError("Qdrant client is not initialized")
            # Upload points
            self.client.upload_points(
                collection_name=collection_name,
                points=points,
                wait=True,  # Wait until the operation is completed
            )

        except ValueError as e:
            logger.debug(f"Failed to setup Qdrant collection: {str(e)}")
            logger.debug(f"Collection: {collection_name}, Chunks: {len(chunks)}")

    async def vector_search(self, question: str, limit: int = 3) -> List[Dict]:
        """Perform vector similarity search"""
        try:
            # Check cache first
            if question in self.vector_cache:
                return self.vector_cache[question]

            embedded_question = await self._get_embedding(question)

            search_res = await self.client.search(
                collection_name=self.collection_name,
                query_vector=embedded_question,
                limit=limit,
            )

            return search_res

        except ValueError as e:
            logger.debug(f"Search error: {str(e)}")
            raise


standard_retriever = HybridRetriever()
