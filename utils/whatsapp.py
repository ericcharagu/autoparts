import requests
from typing import Any
from loguru import logger
import os
from datetime import datetime

# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
ACCESS_TOKEN = "EAARQrAKzcHUBPGjjWJLxuEmZBG17MBwR071qOqAEIdUDW48H4iFPmw1mUn3rZBUlyT6J7OJZCqmqTmXrWZAQLjkJj02XZCGY9zBKmZBjhD3ZCvYEVkcUI4KWyEI0YM17o8loZBRwZAcEnZBSKIeEgcX7467mXpwf7ZBshtAwFpy4lLMjw6y7msCDsGGZCPjg4iLEHRKlnlvp5CsBKzJbsczLIDeVXm56qgfjfaL1UU7gqT0CCrLP"
# RECIPIENT_NUMBER = "447709769066"
# RECIPIENT_NUMBER = "+254736391323"
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
        "to": f"{recipient_number:}",  # for prod
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
        "to": f"{recipient_number:}",  # for prod
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
