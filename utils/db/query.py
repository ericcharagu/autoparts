#!/usr/bin/env python3
import asyncio
from utils.db.base import execute_query


async def get_customer_details(user_phone_number: str) -> list:
    """Get all traffic records for a specific date - optimized query"""
    query = """
    SELECT
        location,
        name
    FROM customers
    WHERE phone_number = :user_phone_number
    """
    return await execute_query(query, {"user_phone_number": user_phone_number})
