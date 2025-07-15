#!/usr/bin/env python3

from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime, timezone


class RequestVerification(BaseModel):
    """Verification schema."""

    hub_mode: str
    hub_verify_token: str
    hub_challenge: str
    hub_signature: str


class GenerationRequest(BaseModel):
    """Schema for the LLM generation."""

    user_message: str
    message_timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ConversationData(BaseModel):
    """Logging interaction."""

    user_message: str
    user_number: str
    message_timestamp: datetime
    llm_response: str
    llm_response_timestamp: datetime
    interaction_timestamp: datetime = Field(default_factory=lambda: datetime.now())
class CustomerDetails(BaseModel):
    id:int
    name:str
    phone_number:str  
    location:str 
    account_type:str
class UserOrders(BaseModel):
    """LLM generated order object from interaction."""

    qoute_id: str
    custome_id: str
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
