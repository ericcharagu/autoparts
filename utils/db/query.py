#!/usr/bin/env python3
from utils.db.base import execute_query

async def get_customer_details(user_number: str) -> list:
    """Get all customer details for personalised LLM responses"""
    query = """
    SELECT * FROM customers WHERE phone_number = :user_number;
    """
    return await execute_query(query, {"user_number": user_number})
