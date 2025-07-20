#!/usr/bin/env python3
from utils.db.base import execute_query
from typing import Any
async def get_customer_details(user_number: str) -> list:
    """Get all customer details for personalised LLM responses"""
    query = """
    SELECT * FROM customers WHERE phone_number = :user_number;
    """
    return await execute_query(query, {"user_number": user_number})

<<<<<<< HEAD
async def get_last_order(user_phone_number: str) -> list[dict[str, Any]]:
    """
    Get the most recent order details for a customer, including all line items,
    based on their phone number. Returns a list containing a single dictionary
    for the last order, or an empty list if no orders are found.
    """
    query = """
    SELECT
        o.quote_id,
        o.total_amount,
        o.payment_status,
        o.created_at AS order_date,
        c.name AS customer_name,
        c.location,
        -- Aggregate all items of the order into a single JSON array
        JSON_AGG(
            JSON_BUILD_OBJECT(
                'item_name', oi.item_name,
                'product_code', oi.product_code,
                'quantity', oi.quantity,
                'unit_price', oi.unit_price
            )
        ) AS items
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    JOIN order_items oi ON o.id = oi.order_id
    WHERE c.phone_number = :user_phone_number
    -- Group by all non-aggregated columns to get a single row per order
    GROUP BY o.id, c.id
    -- Order by date to find the most recent one
    ORDER BY o.created_at DESC
    LIMIT 1;
    """
    return await execute_query(query, {"user_phone_number": user_phone_number})
=======
async def get_customer_details(user_number: str) -> list:
    """Get all customer details for personalised LLM responses"""
    query = """
    SELECT * FROM customers WHERE phone_number = :user_number;
    """
    return await execute_query(query, {"user_number": user_number})
>>>>>>> dbe6686fa09af48efe4d8525cb2a790caa1e73f9
