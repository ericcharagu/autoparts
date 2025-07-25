from requests.models import Response


import uuid
from pydantic import BaseModel
from datetime import datetime
import requests
import os
from typing import Any


class Payments:
    def __init__(
        self,
        quote_id: str,
        receipt_id: str,
        total: float,
        name: str,
        option: str,
    ) -> None:
        self.quote_id = quote_id
        self.id = receipt_id
        self.name = name
        self.total = total
        self.option = option

    def __str__(self) -> str:
        return f"Receipt Number:{self.id}\nQuoute Number:{self.quote_id}\nName:{self.name}\nAmount:{self.total}"


timestamp = str(datetime.now())
password: str = (
    os.getenv("MPESA_SHORTCODE_PROD", " ")
    + os.getenv("SAFARICOM_PASSKEY_PROD", " ")
    + timestamp
)


def sendmpesaprompt(recipient_number: str, amount: str, invoice_id: str):
    daraja_payload: dict[str, Any] = {
        "BusinessShortCode": os.getenv("MPESA_SHORTCODE_PROD", ""),
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": {amount},
        "PartyA": {recipient_number},
        "PartyB": os.getenv("MPESA_SHORTCODE_PROD"),
        "PhoneNumber": {recipient_number},
        "CallBackURL": os.getenv("MPESA_TEST_URL", "") + "/api/stkpushproductorder",
        "AccountReference": {invoice_id},
        "TransactionDesc": "Product Order Payment",
    }
    url: str = os.getenv("MPESA_TEST_URL", "")
    querystring: dict[str, str] = {"grant_type": "client_credentials"}
    headers: dict[str, str] = {
        "Authorization": "Basic SWZPREdqdkdYM0FjWkFTcTdSa1RWZ2FTSklNY001RGQ6WUp4ZVcxMTZaV0dGNFIzaA=="
    }
    response: Response = requests.request(
        method="POST", url=url, data=daraja_payload, headers=headers, params=querystring
    )
    print(response.text)
