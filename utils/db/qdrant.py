# utils/db/qdrant.py

from typing import Dict, List

from loguru import logger
from ollama import AsyncClient
from qdrant_client import AsyncQdrantClient, models

# Constants
QDRANT_HOST = "http://qdrant:6333"
EMBEDDING_HOST = "http://host.docker.internal:11435"
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
            # Increased timeout for robustness during startup
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
            except Exception as e:
                logger.exception(f"Error processing {path}: {str(e)}")
                continue

        return chunks

    async def setup_qdrant_collection(self, chunks: List[Dict]):
        """
        Atomically re-creates the collection and uploads points.
        This is a robust method to ensure a fresh state on each startup.
        """
        try:
            if self.client is None:
                await self.initialize()

            logger.info(
                f"Re-creating collection '{self.collection_name}' to ensure it is fresh."
            )
            await self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE
                ),
                timeout=60,  # Use a longer timeout for this combined operation
            )
            logger.info(f"Collection '{self.collection_name}' re-created successfully.")

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
                batch = points[i : i + batch_size]
                self.client.upload_points(
                    collection_name=self.collection_name,
                    points=batch,
                    wait=True,
                    parallel=6,
                )
                logger.info(f"Uploaded batch {i // batch_size + 1}")

            logger.success(f"Successfully inserted {len(chunks)} chunks into Qdrant")

        except Exception as e:
            logger.critical(f"Failed to setup Qdrant collection: {e}", exc_info=True)
            raise

    async def vector_search(self, question: str, limit: int = 3) -> List[Dict]:
        """Perform vector similarity search"""
        try:
            # Check cache first
            if question in self.vector_cache:
                return self.vector_cache[question]

            embedded_question = await self._get_embedding(question)

            search_res = await self.client.query_points(
                collection_name=self.collection_name,
                query=embedded_question,
                limit=limit,
                # score_threshold=0.7,
            )

            return search_res

        except Exception as e:
            logger.debug(f"Search error: {str(e)}")
            raise

    async def close(self):
        """Clean up resources"""
        if self.client:
            try:
                await self.client.close()
            except Exception as e:
                logger.warning(f"Error closing Qdrant client: {e}")
            finally:
                self.client = None


# Create a single, shared instance of the retriever
standard_retriever = HybridRetriever()
