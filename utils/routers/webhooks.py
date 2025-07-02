# utils/routers/webhooks.py
import os
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from schemas import GenerationRequest
from utils.llm_tools import llm_pipeline
from utils.whatsapp import whatsapp_messenger
from utils.text_processing import convert_llm_output_to_readable

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


@router.post("")
async def handle_whatsapp_message(request: Request):
    """Handles incoming messages from WhatsApp."""
    signature = (
        request.headers.get("x-hub-signature-256", "").split("sha256=")[-1].strip()
    )
    if not verify_signature(await request.body(), signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = await request.json()
        if not data.get("entry"):
            raise HTTPException(status_code=400, detail="Invalid payload structure")

        # Simplified message extraction
        message_text = None
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                messages = change.get("value", {}).get("messages", [])
                if messages and messages[0].get("type") == "text":
                    message_text = messages[0].get("text", {}).get("body")
                    break
            if message_text:
                break

        if not message_text:
            return PlainTextResponse("No text message found", status_code=200)

        # Create request object for the LLM pipeline
        mobile_request = GenerationRequest(prompt=message_text)

        # Get AI response
        llm_response = await llm_pipeline(request=mobile_request, source="MOBILE")
        content = llm_response.get("message", {}).get("content", "")

        # Clean and send response
        cleaned_response = convert_llm_output_to_readable(content)
        whatsapp_messenger(cleaned_response)

        return PlainTextResponse("Message processed", status_code=200)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )
