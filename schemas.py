#!/usr/bin/env python3

from selectors import SelectSelector
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime, timezone
from enum import Enum

class RequestVerification(BaseModel):
    """Verification schema."""

    hub_mode: str
    hub_verify_token: str
    hub_challenge: str
    hub_signature: str


class GenerationRequest(BaseModel):
    """Schema for the LLM generation."""

    prompt: str
    prompt_timestamp: datetime = Field(default_factory=lambda: datetime.now())

class AccountTypes(str, Enum):
    SELLER="seller"
    GARAGE_OWNER ="garage_owner"
    GARAGE_MANAGER ="garage_manager"
    GARAGE_STAFF ="garage_staff"
    NON_REGISTERED_RETAIL="non_registered_retail"
    REGISTERED_RETAIL="registered_retail"
class CustomerDetails(BaseModel):
    id:int
    name:str
    phone_number:str  
    location:str 
    account_type:AccountTypes
class UserOrders(BaseModel):
    """LLM generated order object from interaction."""

    qoute_id: str
    customer_id: str
    customer_contact: str
    garage_id: str
    name: str
    location: str
    items: list[str]
    quantity: list[float]
    price: list[float]
    total: float
    created_at: datetime
    payment_status: str
    payment_date: datetime

class LlmRequestPayload(BaseModel):
    user_message:str 
    user_number:str
    messages:list[Any]
    customer_details:list[dict[str, str|int|bool|datetime]]
    media_file_path:str 
    image_caption:str

