# utils/routers/webhooks.py
import hashlib
import hmac
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from loguru import logger
from schemas import GenerationRequest
from utils.cache import is_message_processed
from utils.db.query import get_customer_details
from utils.llm_tools import llm_pipeline
from utils.text_processing import convert_llm_output_to_readable
from utils.whatsapp import whatsapp_messenger

# Add logging path
logger.add("./logs/webhooks.log", rotation="1 week")
router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

# Load secrets securely from environment variables
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
with open("/app/secrets/whatsapp_secrets.txt", "r") as f:
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


async def process_message_in_background(request:GenerationRequest):
    """This function runs in the background to process and respond to messages."""
    logger.info(f"Background task started for user {user_number}.")
    try:
        customer_details = await get_customer_details(request.user_number)
        mobile_request = GenerationRequest(prompt=message_text)
        llm_response = await llm_pipeline(
            request=request.prompt,
            source="MOBILE",
            customer_details=request.customer_details
            user_number=request.user_number,
        )
        content = llm_response.get("message", {}).get("content", "")
        cleaned_response = convert_llm_output_to_readable(content)
        whatsapp_messenger(
            llm_text_output=cleaned_response, recipient_number=user_number
        )
        logger.success(f"Response sent to {user_number}.")
    except Exception as e:
        logger.error(f"Background task failed for {user_number}: {e}", exc_info=True)


@router.post("")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """
    Handles incoming messages and other events from WhatsApp, ensures idempotency,
    and processes new messages in a background task.
    """
    # ... (Signature verification)

    try:
        data = await request.json()
        if not data.get("entry"):
            return PlainTextResponse("Empty payload", status_code=200)

        # Initialize variables to None
        message_text, user_number, message_id = None, None, None

        changes = data["entry"][0].get("changes", [])
        if not changes:
            return PlainTextResponse("No changes in payload", status_code=200)

        value = changes[0].get("value", {})

        # Check if it's a message payload before trying to access message data
        if "messages" in value and "contacts" in value:
            message = value["messages"][0]
            if message.get("type") == "text":
                message_text = message.get("text", {}).get("body")
                user_number = value["contacts"][0].get("wa_id")
                message_id = message.get("id")
        elif "statuses" in value:
            # This is a status update (e.g., 'sent', 'delivered', 'read'). Log it and ignore.
            status_data = value["statuses"][0]
            log_msg_id = status_data.get("id")
            log_status = status_data.get("status")
            logger.info(
                f"Received status update for message {log_msg_id}: {log_status}"
            )
            return PlainTextResponse("Status update received", status_code=200)
        else:
            # Another type of event we are not handling
            logger.info(f"Received an unhandled webhook event type. Value: {value}")
            return PlainTextResponse("Unhandled event type", status_code=200)

        # Now, proceed only if we have a message ID
        if not message_id:
            logger.info("Webhook did not contain a new user message to process.")
            return PlainTextResponse("No new message to process", status_code=200)

        # IDEMPOTENCY CHECK
        if not await is_message_processed(message_id):
            return PlainTextResponse("Duplicate message", status_code=200)

        # Queue the background task
        background_tasks.add_task(
            process_message_in_background, mrequest
        )

        logger.info(
            f"Webhook from {user_number} (wamid: {message_id}) acknowledged and queued."
        )
        return PlainTextResponse("Message queued for processing", status_code=200)

    except Exception as e:
        logger.error(f"Error in main webhook handler: {e}", exc_info=True)
        # Always return 200 to Meta to prevent retries for our own processing errors
        return PlainTextResponse("Error processing request", status_code=200)
