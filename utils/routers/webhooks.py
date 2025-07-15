# utils/routers/webhooks.py
import os
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
import httpx
import uuid
from schemas import CustomerDetails, GenerationRequest
from utils.cache import is_message_processed
from utils.db.query import get_customer_details
from utils.llm_tools import llm_pipeline
from utils.whatsapp import ACCESS_TOKEN, whatsapp_messenger
from utils.text_processing import convert_llm_output_to_readable
from loguru import logger

# Adding loggers
logger.add("./logs/webhooks.log", rotation="10 MB")
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

# Ensure media directory exists
os.makedirs("media_files", exist_ok=True)

# Load secrets securely from environment variables
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
with open(file="/app/secrets/whatsapp_secrets.txt", mode="r") as f:
    APP_SECRET = f.read().strip()


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify the X-Hub-Signature-256 header matches the payload signature."""
    if not APP_SECRET:
        # If no secret is configured, skip verification (useful for dev)
        return True

    expected_signature = hmac.new(
        key=APP_SECRET.encode("utf-8"), msg=payload, digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)

async def process_message_in_background(request:Request, message_text: str, user_number: str):
    """This function runs in the background to process and respond to messages."""
    logger.info(f"Background task started for user {user_number}.")
    try:
        customer_details = await get_customer_details(user_number)
        mobile_request = GenerationRequest(user_message=message_text)
    
        llm_response = await llm_pipeline(request=request,
            request_payload=mobile_request, source="MOBILE", user_number=user_number, customer_details=customer_details
        )
        content = llm_response.get("message", {}).get("content", "")
        cleaned_response = convert_llm_output_to_readable(content)
        whatsapp_messenger(
            llm_text_output=cleaned_response, recipient_number=user_number
        )
        logger.success(f"Response sent to {user_number}.")
    except Exception as e:
        logger.error(f"Background task failed for {user_number}: {e}", exc_info=True)

async def download_whatsapp_media(media_id: str) -> str | None:
    # 1. Get Media URL
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to get media URL for {media_id}. Status: {response.status_code}, Body: {response.text}")
            return None
        media_url = response.json().get("url")

        # 2. Download Media
        response = await client.get(media_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to download media from {media_url}. Status: {response.status_code}")
            return None

    # 3. Save to a unique file
    file_extension = response.headers.get("content-type", "image/jpeg").split("/")[-1]
    file_name = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join("media_files", file_name)
    with open(file_path, "wb") as f:
        f.write(response.content)
    
    logger.info(f"Media {media_id} downloaded and saved to {file_path}")
    return file_path

    
@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Handles webhook verification for the WhatsApp platform."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_whatsapp_message(request: Request, background_tasks:BackgroundTasks):
    """Handles incoming messages from WhatsApp."""
    # signature = (
    #     request.headers.get("x-hub-signature-256", "").split("sha256=")[-1].strip()
    # )
    # if not verify_signature(await request.body(), signature):
    #     raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = await request.json()
        if not data.get("entry"):
            raise HTTPException(status_code=400, detail="Invalid payload structure")
        value = data["entry"][0]["changes"][0].get("value", {})
        if not value: return PlainTextResponse("OK")

        # Handle message status updates vs. new messages
        if "messages" in value:
            message_obj = value["messages"][0]
            message_id:str = message_obj.get("id")
       # IDEMPOTENCY CHECK
        if not await is_message_processed(client=request.app.state.redis, message_id=message_id):
            return PlainTextResponse("Duplicate message", status_code=200)
        # Simplified message extraction
        message_text:str = ""
        message_id:str= ""
        user_number:str=""
        for entry in data.get("entry", []):
            message_id = entry.get("id", " ")
            for change in entry.get("changes", []):
                contact_info = change.get("value", {}).get("contacts", [])
                if contact_info:
                    user_number = contact_info[0].get("wa_id")
                messages = change.get("value", {}).get("messages", [])
                if messages and messages[0].get("type") == "text":
                    message_text = messages[0].get("text", {}).get("body")
                    break
            if message_text:
                break

        if not message_text:
            logger.info("Webhook received, but no processable text message found.")
            return PlainTextResponse("No text message found", status_code=200)
        
 
        # Queue the processing and response to happen in the background
        background_tasks.add_task(process_message_in_background, request, message_text, user_number)
        
        logger.info(f"Webhook from {user_number} acknowledged and queued for processing.")
        return PlainTextResponse("Message processed", status_code=200)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )
