import requests
from typing import Any
from loguru import logger
import os
from datetime import datetime

# Logger file path
logger.add("./logs/whatsapp.log", rotation="1 week")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID: int = int(os.getenv("PHONE_NUMBER_ID", 0))
ACCESS_TOKEN="EAARQrAKzcHUBPPVZAIxg7gMEwS3xZB8IvPV1YsnS7nrvYZCsWTG3y9mqyU7eOo6AWh4OCqvkU1hNGtW2Lk43ggv9ZACe8iBZAZCPsArTWi4A3CBhtEUiVY43xOEfTkQC6HF33F84ZA3mSKBqTZCqFdJaDQqpXhbz29mtmdERpQh4WNf6n9ZBZAa7ma1xQKXwb5UGZBJyvfXFfFKwMmV1cu3ydEABmxaQNBw7dSiUgV1NwHUAyIZD"
current_time = datetime.now()

@logger.catch
def whatsapp_messenger(llm_text_output: Any, recipient_number: str):
    """Send llm response via whatspp."""
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload: dict[str, str | dict[str, Any]] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"{recipient_number}",  # for prod
        # "to": f"{RECIPIENT_NUMBER}",  # for testing
        "type": "text",
        "text": {
            "body": llm_text_output,
        },
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises exception for HTTP errors
        logger.info(response)
        
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error making request: {e}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")

def send_invoice_whatsapp( recipient_number: str|int, invoice_filename:str):
    """Send llm response via whatspp."""
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload: dict[str, str | dict[str, str]] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"{recipient_number}",  # for prod
        # "to": f"{RECIPIENT_NUMBER}",  # for testing
        "type": "document",
        "document": {
            "caption": f"Invoice_{datetime.date(datetime.now())}",
            "filename": f"{invoice_filename}",
        },
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises exception for HTTP errors

    except requests.exceptions.RequestException as e:
        logger.error(f"Error making request: {e}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")


# used for testing
# whatsapp_messenger("This is the test for lantern")
