# utils/db/qdrant.py
from qdrant_client.models import PointStruct
from typing import Any
from loguru import logger
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient, models
from dotenv import load_dotenv
from dependancies import embedding_client
import os
#Load environment
load_dotenv()
# Constants
QDRANT_HOST = "http://qdrant:6333"
embedding_model_name="nomic-embed-text:latest"
COLLECTION_NAME = "autoparts_test"
DIMENSION = 768
CHUNK_SIZE = 50


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
        self.embedding_client = embedding_client
        self.vector_cache: dict[str, list[dict]] = {}

    async def initialize(self):
        """Initialize the Qdrant client connection"""
        try:
            # Increased timeout for robustness during startup
            self.client = AsyncQdrantClient(url=QDRANT_HOST, timeout=60.0)
            # Test the connection
            await self.client.get_collections()
            
            logger.info("Qdrant client initialized successfully")
        except ValueError as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    async def _get_embedding(self, text: str | list[str]) -> list[float]:
        """Helper method to get embeddings for text"""
        try:
            response = await self.embedding_client.embeddings(
                model=embedding_model_name, prompt=text
            )
            return response["embedding"]
        except ValueError as e:
            logger.debug(f"Embedding error for text: {str(e)}")
            raise

    async def initialize_knowledge_base(self, knowledge_paths) -> list[dict[str, int | str | list[float]]]:
        """Process files and create chunks with embeddings"""
        chunks = []
        chunk_id = 0

        for path in knowledge_paths:
            try:
                with open(file=path, mode="r", encoding="UTF-8") as file:
                    text = file.read()
                    for i in range(0, len(text), self.chunk_size):
                        chunk_content: str = text[i : i + self.chunk_size]
                        embedding: list[float] = await self._get_embedding(chunk_content)

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
                logger.ValueError(f"Error processing {path}: {str(e)}")
                continue
        return chunks
    """
    async def setup_chat_qdrant_collection(self, collection_name:str,chat_history:ChatHistory):
        try:
            if self.client is None:
                await self.initialize()

            logger.info(
                f"Re-creating collection '{collection_name}' to ensure it is fresh."
            )
            await self.client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE
                ),
                timeout=60,  # Use a longer timeout for this combined operation
            )
            logger.info(f"Collection '{collection_name}' re-created successfully.")

            embedded_user_message: list[float]=await self._get_embedding(text=chat_history["user_message"])
            embedded_llm_response: list[float]=await self._get_embedding(text=chat_history["llm_response"])
            await self.client.upsert(
    collection_name=collection_name,
    wait=True,
    points=[
        PointStruct(id=id, vector=embedded_user_message, payload={"user_message": user_message}),
        PointStruct(id=id, vector=embedded_llm_response, payload={"llm_response": llm_response}),
       
    ],
)
        
            logger.success(f"Successfully inserted into the chat vector database")

        except ValueError as e:
            logger.critical(f"Failed to setup chat history collection: {e}", exc_info=True)
            raise
    """
    async def setup_qdrant_collection(self, collection_name:str, chunks:list):
        """
        Atomically re-creates the collection and uploads points.
        This is a robust method to ensure a fresh state on each startup.
        """
        try:
            if self.client is None:
                await self.initialize()

            logger.info(
                f"Initialise '{collection_name}' to ensure it is fresh."
            )
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE, on_disk=True
                ),
                timeout=60,  # Use a longer timeout for this combined operation
            )
            logger.info(f"Collection '{collection_name}' created successfully.")

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
            # Upload points in batches
            batch_size = 100
            logger.info(f"Uploading {len(points)} points in batches of {batch_size}...")
            for i in range(0, len(points), batch_size):
                batch: list[Any] = points[i : i + batch_size]
                self.client.upload_points(
                    collection_name=collection_name,
                    points=batch,
                    wait=True,
                    parallel=6,
                )
                logger.info(f"Uploaded batch {i // batch_size + 1}")

            logger.success(f"Successfully inserted {len(chunks)} chunks into Qdrant")

        except ValueError as e:
            logger.critical(f"Failed to setup Qdrant collection: {e}", exc_info=True)
            raise

    async def vector_search(self, question: str, collection_name:str,limit: int = 3) -> list[dict]:
        """Perform vector similarity search"""
        try:
            if self.client is None:
                await self.initialize()  # Ensure client exists

            # Check cache first
            if question in self.vector_cache:
                return self.vector_cache[question]

            embedded_question: list[float] = await self._get_embedding(text=question)

            search_res:list = await self.client.search(
                collection_name=collection_name,
                query_vector=embedded_question,
                limit=limit,
                # score_threshold=0.7,
            )

            return search_res

        except ValueError as e:
            logger.debug(f"Search error: {str(e)}")
            raise

    async def close(self):
        """Clean up resources""" 
        if self.client:
            try:
                await self.client.close()
            except ValueError as e:
                logger.warning(f"Error closing Qdrant client: {e}")
            finally:
                self.client = None


# Create a single, shared instance of the retriever
standard_retriever: HybridRetriever = HybridRetriever()

