import asyncio
import hashlib
import hmac
import re
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel, Field
from utils.llm_tools import init_qdrant_db, llm_pipeline
from utils.whatsapp import whatsapp_messenger

#Company specific data paths. Includes inventory
knowledge_base = ["utils/data/data.csv", "utils/data/tires.csv"]

@asynccontextmanager
async def lifespan(app:FastAPI):
    global process_pool
    logger.info("Starting application")
    process_pool=ProcessPoolExecutor(max_workers=7)
    asyncio.create_task(init_qdrant_db(knowledge_base))
    yield

    #Shutdown process pool
    if process_pool:
        process_pool.shutdown(wait=True)
        logger.info("Shutting down app")

app = FastAPI(title="Autoparts Customer Care Associate", lifespan=lifespan)
# Define logger file path
logger.add("./logs/main_app.log", rotation="1 week")
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add middleware
#app.middleware("http")(auth_middleware)

# load the env
load_dotenv()

# Setting the authentication based on the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Include routers
#app.include_router(auth.router)
# Mount static files
app.mount("/static", StaticFiles(directory="./static"), name="static")


# Configuration
VERIFY_TOKEN = "whatsapp_test"
APP_SECRET = "your_app_secret"  # Used for signature verification

def convert_llm_output_to_readable(llm_output):
    """
    Converts an LLM output with markdown and formatting artifacts into clean, human-readable text.
    """
    text = llm_output.strip()
    # Split the text by <think> tags and take the part after the last <think> tag
    parts = text.split("<think>")
    if len(parts) > 1:
        # Take everything after the last <think> tag
        main_text = parts[-1].split("</think>")[-1].strip()
    else:
        # If no <think> tags are found, use the whole text
        main_text = text.strip()
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", main_text)
    text = re.sub(r"- ", "• ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s*:\s*", ": ", text)
    text = re.sub(r"#{1,6}\s+(.*?)(?:\n|$)", r"\1\n", text)

    paragraphs = text.split("\n\n")
    formatted_paragraphs = []
    for p in paragraphs:
        if p.strip():
            if "• " in p:
                formatted_paragraphs.append(p)
            else:
                formatted_p = re.sub(r"\s+", " ", p)
                formatted_paragraphs.append(formatted_p)

    clean_text = "\n\n".join(formatted_paragraphs)
    return clean_text



# Define request models
class GenerationRequest(BaseModel):
    prompt: str
    prompt_timestamp: datetime = datetime.now(timezone.utc)


class ConversationData(BaseModel):
    user_message: Any
    prompt_timestamp: datetime
    llm_response: str
    llm_response_timestamp: datetime
    source: str
    interaction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

# API endpoint for generating text
@app.post("/generate")
async def generate_text(request: GenerationRequest):
    try:

        # Run the model and store the results
        web_prompt_reply =await llm_pipeline(request=request, source="WEB")
        return convert_llm_output_to_readable(web_prompt_reply)

    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"HTTP error: {str(e)}"},
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=500, content={"error": f"Request error: {str(e)}"}
        )
    except ValueError as e:
        return JSONResponse(
            status_code=500, content={"error": f"Unexpected error: {str(e)}"}
        )


# Simple HTML form for testing the API
templates = Jinja2Templates(directory="templates")


# Create a basic UI for testing
@app.get("/")
async def get_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


# Whatsapp messaging endpoint
@app.get("/webhooks")
async def get_request_info(# GET parameters for webhook verification
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")):

    # WhatsApp webhook verification
    if hub_mode and hub_verify_token:
        if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
            return PlainTextResponse(content=hub_challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")

@app.post("/webhooks")
async def handle_whatsapp(
    request: Request):
    # Verify the signature if needed (commented out like in original)
    """
    signature = request.headers.get("x-hub-signature-256", "").split("sha256=")[-1].strip()
    if not verify_signature(await request.body(), signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    """

    try:
        # Get JSON data from request
        data = await request.json()

        if not data:
            raise HTTPException(status_code=400, detail="Empty payload")

        print("Received data:", data)  # For debugging

        # Extract message information and return as dict
        entries = data.get("entry", [])
        test_message = {
            "prompt": "",
            "prompt_timestamp": datetime.now(timezone.utc),
        }

        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    if message.get("type") == "text":
                        message_info = {
                            # "sender_profile_id": message.get("from"),
                            "prompt": message.get("text").get("body", " "),
                            # "message_id": message.get("id"),
                            "prompt_timestamp": message.get("timestamp"),
                        }
                        test_message.update(message_info)
        mobile_request = GenerationRequest(**test_message)

        llm_mobile_response = await llm_pipeline(request=mobile_request, source="MOBILE")
        # Parse the response to the whatsapp messenger
        def_eng_response = convert_llm_output_to_readable(llm_mobile_response)

        # Translate if needed
        whatsapp_messenger(def_eng_response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify the X-Hub-Signature-256 header matches the payload signature"""
    if not APP_SECRET:
        return True  # Skip verification if no app secret is set

    expected_signature = hmac.new(
        key=APP_SECRET.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Getting user_specific metrics

"""# Main entry point
if __name__ == "__main__":
    print("Starting API server on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)"""
