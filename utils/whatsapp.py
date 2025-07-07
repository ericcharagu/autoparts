import requests
from typing import Any
from loguru import logger
import os
from datetime import datetime

# Logger file path
logger.add("./logs/whatsapp.log", rotation="1 week")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
ACCESS_TOKEN = "EAARQrAKzcHUBPHUtSTLnz9WOnXXUeOzenyln7vnh2OBQvuhV0ZB3N63gxtGWO3P7fBD76XZBUP792KAZAAddU8wxWMKgwNkUkDzZAgypkoCGxVYiVOGye3KtNGBZA4ujITmQ8QLKlZCBGJtUhZAdP77LqDiFiaZADstgo3gxC2UI49hY3XrFYIOG2WRIh5XuNq5d3OAI9PBcS50kiPiaWXf97mPpnwQ3QMIZAU7T3A9gEFZCwZD"
# RECIPIENT_NUMBER = "447709769066"
RECIPIENT_NUMBER = "+254736391323"
current_time = datetime.now()


# TODO:Remove the hardcoded recipient number and replace with function provided info
@logger.catch
def whatsapp_messenger(llm_text_output: Any, recipient_number: str):
    """Send llm response via whatspp."""
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
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

    except requests.exceptions.RequestException as e:
        logger.error(f"Error making request: {e}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")


def send_invoice_whatsapp(invoice_file_path: str, recipient_number: str):
    """Send llm response via whatspp."""
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"{recipient_number}",  # for prod
        # "to": f"{RECIPIENT_NUMBER}",  # for testing
        "type": "document",
        "document": {
            "caption": f"Invoice_{datetime.date(datetime.now())}",
            "file": f"{invoice_file_path}",
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
