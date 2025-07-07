# main.py
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from middleware.auth_middleware import auth_middleware
from utils.db.qdrant import standard_retriever
from utils.routers import auth, chat, pages, webhooks

# Load environment variables from .env file
load_dotenv()

# Define knowledge base files
knowledge_base = ["utils/data/data.csv", "utils/data/tires.csv"]


# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.info("Starting application...")

    # Initialize a process pool executor
    app.state.process_pool = ProcessPoolExecutor(max_workers=7)
    try:
        # Await the task directly
        await standard_retriever.initialize()
        chunks = await standard_retriever.initialize_knowledge_base(knowledge_base)
        await standard_retriever.setup_qdrant_collection(chunks)

    except Exception as e:
        logger.critical(f"Failed to initialize Qdrant DB: {e}")
        raise

    yield {"retriever": standard_retriever}
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
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- API Routers ---
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(chat.router)
app.include_router(webhooks.router)


# --- Health Check Endpoint ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint to confirm the API is running."""
    return {"status": "healthy"}
