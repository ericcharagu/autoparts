# main.py
<<<<<<< HEAD
from typing import Any, AsyncGenerator, Generator


import asyncio
=======
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from gc import collect

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from ollama import AsyncClient
import os 
import redis.asyncio as redis
from middleware.auth_middleware import auth_middleware
<<<<<<< HEAD
from utils.llm_tools import chat_history
from utils.routers import auth,webhooks, pages
from utils.db.qdrant import HybridRetriever
=======
from utils.db.qdrant import standard_retriever
from utils.routers import auth, chat, pages, webhooks

>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
# Load environment variables from .env file
load_dotenv()

# Define knowledge base files
<<<<<<< HEAD
#knowledge_base: list[str] = ["utils/data/data.csv", "utils/data/tires.csv", "utils/data/Hiview_tyres.txt", "utils/data/Hiview_car_care.txt", "utils/data/green_lubes.txt"]
knowledge_base:list[str]=["utils/data/data.csv", "utils/data/tires.csv"]
retriever: HybridRetriever = HybridRetriever()
=======
knowledge_base = ["utils/data/data.csv", "utils/data/tires.csv"]

>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9

VALKEY_HOST=os.getenv("VALKEY_HOST")
VALKEY_PORT=int(os.getenv("VALKEY_PORT", 6379))
# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Starting application...")

    # Initialize a process pool executor
    app.state.process_pool = ProcessPoolExecutor(max_workers=7)
        # --- Initialize Clients ---
    app.state.llm_client = AsyncClient(host=os.getenv("OLLAMA_HOST"))
   # app.state.embedding_client = AsyncClient(host=os.getenv("OLLAMA_EMBEDDING_HOST"))
    app.state.embedding_client=AsyncClient("http://ollama_embedding:11434")
    # Initialize Valkey/Redis client
    redis_pool = redis.ConnectionPool(host=VALKEY_HOST, port=VALKEY_PORT, db=0, decode_responses=True)
    app.state.redis = redis.Redis(connection_pool=redis_pool)
    
    try:
<<<<<<< HEAD
        # Await the knowledge vector_database init and setup
        await retriever.initialize()
        chunks: list[dict[str, int | str | list[float]]] = await retriever.initialize_knowledge_base(knowledge_base)
        await retriever.setup_qdrant_collection(collection_name="autoparts_test", chunks=chunks)

        yield {"retriever": retriever}
    except Exception as e:
        logger.critical(f"Failed to initialize Qdrant DB: {e}")
        raise
    # Initialize the vector database in the background
    #asyncio.create_task(init_qdrant_db(knowledge_base))
=======
        # Await the task directly
        await standard_retriever.initialize()
        chunks = await standard_retriever.initialize_knowledge_base(knowledge_base)
        await standard_retriever.setup_qdrant_collection(chunks)

    except Exception as e:
        logger.critical(f"Failed to initialize Qdrant DB: {e}")
        raise

    yield {"retriever": standard_retriever}
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
    # --- Shutdown logic ---
    if app.state.process_pool:
        app.state.process_pool.shutdown(wait=True)
    logger.info("...Application shutdown complete.")


# --- FastAPI App Initialization ---
app = FastAPI(
    title="Lane Customer Care Associate",
    description="An AI-powered assistant for Lane inquiries and orders.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add logger for the main application
logger.add("./logs/main_app.log", rotation="1 week", level="INFO")

# --- Middleware Configuration ---
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # TODO: Restrict this in production to internal domains and whatsapp hooks only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom authentication middleware
app.middleware("http")(auth_middleware)

# --- Static Files ---
app.mount("/static", StaticFiles(directory="templates"), name="static")

# --- API Routers ---
#app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(webhooks.router)


# --- Health Check Endpoint ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint to confirm the API is running."""
    return {"status": "healthy"}
