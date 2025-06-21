import requests
from typing import Any
from loguru import logger

# Logger file path
logger.add("./logs/whatsapp.log", rotation="700 MB")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID = "605403165986839"
ACCESS_TOKEN = "EAARQrAKzcHUBOxBopuhU8tkQvH9ytBBeW3ykHmiextnYeVpZCZA3u4v3WPSTMLtLrnkKMh656YGmZAGCHxn9QgyrpMEuwncSgKoStEuWZB76q1FZAKNDaGgQr7j8OFZBdFfmbwxQcZByXCYbrbZB5lDt4l2etZBiu6NdxeDKZBEuWZBb47lUcOLSH6lfgeI0TdaXQO2RSlib7SOm07ZCNCZAPZBZA2pJ2zB75F6RUfq"
# RECIPIENT_NUMBER = "447709769066"
RECIPIENT_NUMBER = "+254736391323"


@logger.catch
def whatsapp_messenger(llm_text_output: Any):
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
        "to": f"{RECIPIENT_NUMBER}",
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


# used for testing
# whatsapp_messenger("This is the test for lantern")
