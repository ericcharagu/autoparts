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

    prompt: str
    prompt_timestamp: datetime = Field(default_factory=lambda: datetime.now())

class ConversationData(BaseModel):
    """Logging interaction."""

    user_message: Any
    user_number: str
    message_timestamp: datetime
    llm_response: str
    llm_response_timestamp: datetime
    #interaction_timestamp: datetime = Field(default_factory=lambda: datetime.now())


class UserOrders(BaseModel):
    """LLM generated order object from interaction."""

    qoute_id: str
    custome_id: str
    customer_contact: str
    garage_id: str
    name: str
    location: str
    items: list
    quantity: list
    price: list
    total: float
    created_at: Any
    payment_status: str
    payment_date: Any


class CustomerDetails(BaseModel):
    """Customer data types requiered for order and payment completion"""

    customer_id: str
    customer_number: str
    business_id: str
    customer_name: str
    dropoff_location: str
    phone_number: str


class Business(BaseModel):
    """Business type data structure"""

    garage_id: str
    garage_name: str
    location: str
    contact_number: str
