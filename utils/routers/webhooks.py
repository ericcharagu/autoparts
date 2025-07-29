# utils/routers/webhooks.py
import hashlib
from datetime import datetime, timezone
import hmac
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse
import httpx
import uuid
from schemas import CustomerDetails, GenerationRequest, LlmRequestPayload
from utils.cache import add_to_chat_history, is_message_processed
from utils.db.query import get_customer_details
from utils.llm.llm_base import available_functions, llm_model, llm_pipeline, tool_checker, tools
from utils.llm.prompt import BTB_SYSTEM_PROMPT
from utils.whatsapp import ACCESS_TOKEN, whatsapp_messenger
from utils.llm.text_processing import convert_llm_output_to_readable
from loguru import logger
from ollama import chat
# Add logging path
logger.add("./logs/webhooks.log", rotation="1 week")
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


async def download_whatsapp_media(media_id: str) -> str:
    # 1. Get Media URL
    url: str = f"https://graph.facebook.com/v22.0/{media_id}"
    headers: dict[str, str] = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        media_url_response = await client.get(url, headers=headers)
        if media_url_response.status_code != 200:
            logger.error(
                f"Failed to get media URL for {media_id}. Status: {media_url_response.status_code}, Body: {media_url_response.text}"
            )

        media_url: str = media_url_response.json().get("url")

        # 2. Download Media
        response = await client.get(media_url, headers=headers)
        if response.status_code != 200:
            logger.error(
                f"Failed to download media from {media_url}. Status: {response.status_code}"
            )

    # 3. Save to a unique file
    file_extension = response.headers.get("content-type", "image/jpeg").split("/")[-1]
    file_name: str = f"{uuid.uuid4()}.{file_extension}"
    file_path: str = os.path.join("media_files", file_name)
    with open(file=file_path, mode="wb") as f:
        f.write(response.content)

    logger.info(f"Media {media_id} downloaded and saved to {file_path}")
    return file_path

async def process_message_in_background(
    request: Request,
    user_message: str,
    user_number: str,
    media_id: str,
    image_caption: str,
):
    """This function runs in the background to process and respond to messages."""
    logger.info(f"Background task started for user {user_number}.")
    media_file_path: str = ""
    final_response_content:str=""
      # Redis client
    redis_client = request.app.state.redis
    try:
        customer_details: list[Any] = await get_customer_details(user_number)
        if media_id:
            media_file_path: str = await download_whatsapp_media(media_id=media_id)
        # Prepare the data for llm to ingest
        messages: list[dict[str, str]] = [
            {"role": "system", "content": BTB_SYSTEM_PROMPT},     
        ]

        # Get final response from model with function outputs
        tool_call_payload = LlmRequestPayload(
            user_message=user_message,
            user_number="",
            messages=messages,
            customer_details=[],
            media_file_path=media_file_path,
            image_caption=image_caption,
        )
        llm_response=chat(llm_model,messages=[{"role":"user", "content":user_message or media_file_path}], tools=tools )
        #llm_response =await tool_checker(user_message=user_message)

        logger.info(llm_response)
        if not llm_response or "message" not in llm_response:
            logger.error(f"Received invalid or None response from LLM pipeline for user {user_number}.")
            # Send a generic error message
            whatsapp_messenger(
                llm_text_output="I'm sorry, I'm having trouble processing your request right now. Please try again in a moment.",
                recipient_number=user_number
            )
            return

        if llm_response.message.tool_calls:
            for tool in llm_response.message.tool_calls:
                # Ensure the function is available, and then call it
                if function_to_call := available_functions.get(tool.function.name):
                    logger.info(f"Calling function: {tool.function.name}")
                    logger.info(f"Arguments:'{tool.function.arguments}")        
                    # Get the actual function object
                    output = function_to_call(**tool.function.arguments)
                    logger.info(f"Function output:{output}")
                else:
                    logger.info(f"Function {tool.function.name}not found")

            if llm_response.message.tool_calls:
                messages.append(llm_response.message)
                messages.append({'role': 'tool', 'content': str(output), 'tool_name': tool.function.name})

            llm_pipeline_payload = LlmRequestPayload(
            user_message=user_message,
            user_number=user_number,
            messages=messages,
            customer_details=customer_details,
            media_file_path=media_file_path,
            image_caption=image_caption,
        )
            final_response =await llm_pipeline(request=request, llm_request_payload=llm_pipeline_payload)
            logger.info('Final response:', final_response.message.content)
            if not final_response.message.content:
                logger.warning(f"LLM returned empty content for user {user_number}. Sending fallback.")
                final_response_content = "I'm not sure how to respond to that. Could you please rephrase your request."
            else:
                final_response_content=final_response.message.content 
        cleaned_response = convert_llm_output_to_readable(final_response_content)
        whatsapp_messenger(
            llm_text_output=cleaned_response, recipient_number=user_number
        )
        await add_to_chat_history(
            client=redis_client,
            user_number=user_number,
            user_message=user_message,
            llm_response=cleaned_response,
        )
    
    except Exception as e:
        logger.error(f"Background task failed for {user_number}: {e}", exc_info=True)


@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Handles webhook verification for the WhatsApp platform."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
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
        if not value:
            return PlainTextResponse("OK")

        user_message: str = ""
        media_id: str = ""
        user_number: str = ""
        image_caption: str = ""
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                contact_info = change.get("value", {}).get("contacts", [])
                if contact_info:
                    user_number = contact_info[0].get("wa_id")
                messages = change.get("value", {}).get("messages", [])
                if messages and messages[0].get("type") == "text":
                    user_message = messages[0].get("text", {}).get("body")
                    break
                if messages and messages[0].get("type") == "image":
                    media_id: str = messages[0].get("image", {}).get("id")
                    image_caption: str = messages[0].get("image", {}).get("caption", "")
                    break
            if user_message or media_id:
                break

        if not (user_message or media_id):
            logger.info("Webhook received, but no processable text message found.")
            return PlainTextResponse("No text message found", status_code=200)

        # Queue the processing and response to happen in the background
        background_tasks.add_task(
            process_message_in_background,
            request,
            user_message,
            user_number,
            media_id,
            image_caption,
        )

        logger.info(
            f"Webhook from {user_number} acknowledged and queued for processing."
        )
        return PlainTextResponse("Message processed", status_code=200)

    except ValueError as e:
        logger.error(f"Error processing request {e}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )
