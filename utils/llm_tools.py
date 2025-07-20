#!/usr/bin/env python3
from collections import defaultdict, deque
from datetime import datetime, timedelta
import os
from re import search
from typing import Any
import uuid

from dependancies import llm_client
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from fastapi import Request
from loguru import logger
from ollama import AsyncClient
from prompts import BTC_SYSTEM_PROMPT
from prompts import BTB_SYSTEM_PROMPT, BTC_SYSTEM_PROMPT, SECURITY_POST_PROMPT
from schemas import CustomerDetails, GenerationRequest, LlmRequestPayload, UserOrders
from transformers.utils import get_json_schema
from utils.cache import add_to_chat_history, get_chat_history
from utils.db.qdrant import standard_retriever
from utils.db.query import get_last_order
from utils.image_processor import read_image
from utils.orders import Order, OrderItem
from utils.payment import Payments
from utils.text_processing import convert_llm_output_to_readable
from utils.whatsapp import send_invoice_whatsapp
# Load environment variables
load_dotenv()

# Adding logging information
logger.add("./logs/llm_app", rotation="10 MB")
llm_model = "qwen3:8b"


class ChatHistory:
    def __init__(self):
        self.message_pairs = deque()
        self.pair_counter = defaultdict(int)
        self.pair_ids = {}

    def append(self, user_timestamp, user_message, llm_response):
        # Create a unique hashable key for the message pair
        pair_key = (tuple(user_message), tuple(llm_response))

        # If this pair already exists, increment its count
        if pair_key in self.pair_ids:
            pair_id = self.pair_ids[pair_key]
            self.pair_counter[pair_id] += 1

            # If count reached 3, remove the oldest occurrence
            if self.pair_counter[pair_id] >= 10:
                self._remove_oldest_occurrence(pair_id)
        else:
            # Create a new unique ID for this pair
            pair_id = str(uuid.uuid4())
            self.pair_ids[pair_key] = pair_id
            self.pair_counter[pair_id] = 1

            # Add to history
            self.message_pairs.append(
                {
                    "user_timestamp": user_timestamp,
                    "user_message": user_message,
                    "llm_response": llm_response,
                    "pair_id": pair_id,
                }
            )

    def _remove_oldest_occurrence(self, pair_id):
        # Find and remove the oldest occurrence of this pair
        for i, msg in enumerate(self.message_pairs):
            if msg["pair_id"] == pair_id:
                del self.message_pairs[i]
                break

        # Reset the counter for this pair
        self.pair_counter[pair_id] = 2  # Set to 2 since we removed one

    def get_history(self):
        return list(self.message_pairs)

SYSTEM_DATE = datetime.now().date()  # Current system time
PAYMENT_DEADLINE = SYSTEM_DATE + timedelta(
    days=14
)  # Assuming the customer is expected to pay within 14 days
# TODO:Add language model or set have the model be multlingual based on a system message setting
# Language code mapping
language_codes = {
    "English": "eng_Latn",
    "Spanish": "spa_Latn",
    "French": "fra_Latn",
    "Kikuyu": "kik_Latn",
    "Luo": "luo_Latn",
    "Somali": "som_Latn",
    "Kirundi": "kir_Cyrl",
    "Yoruba": "yo_Latn",
    "Kamba": "kam_Latn",
    "Swahili": "swh_Latn",
    "Zulu": "zul_Latn",
    "Afrikaans": "afr_Latn",
}
#Tool Functions
def send_invoice(user_order: UserOrders) -> None:
    """
    Using the customer's details and the request to generate an invoice pdf for the order and confirmation.Create it and send it to the user via whatsapp
    Args:
        user_order: List of containing the customer's information such as:
                    qoute_id: str 
                    customer_id: str
                    customer_contact: str
                    garage_id: str
                    name: str
                    location: str
                    items: list[str]
                    quantity: list[float] of each item
                    price: list[float] of the items
                    total: float
                    created_at: datetime
                    payment_status: str
                    payment_date: datetime
    """
    invoice_filename: str=Order(user_order).create_invoice_pdf()
    send_invoice_whatsapp(recipient_number=user_order.customer_contact, invoice_filename=invoice_filename)

def format_quotation(
    quote_id: str,
    cus_id: str,
    garage_id: str,
    name: str,
    location: str,
    items: list[str],
    quantities: list[int],
    prices: list[float],
) -> Order:
    """
    Your only task is to generate a summary of the interaction and the customer's requirements. If any of the values are missing, ask the user kindly

    Args:
          quote_id: Generate a random uniq ID for each quotation generated per interation.
          cus_id: A unique customer id that is given to each user. Similar to IP addresses
          garage_id:A unique garage identifier associated with each user
          name: Name of the customer
          location: Location of the customer for delivery
          items: User order items
          quantities:list of item quantities
          prices: list of item prices
    Returns:
          Order: Validated order object with PDF invoice
    """
    # Validate input lengths
    if not (len(items) == len(quantities) == len(prices)):
        raise ValueError("Items, quantities, and prices must have the same length")

    # Create order items
    order_items = [
        OrderItem(name=item, quantity=qty, price=price)
        for item, qty, price in zip(items, quantities, prices)
    ]

    # Create order
    order: Order = Order(
        quote_id=quote_id,
        cus_id=cus_id,
        garage_id=garage_id,
        name=name,
        location=location,
        items=order_items,
    )

    # Generate invoice
    invoice: Any = order.create_invoice_pdf()
    logger.info(f"Created order {order.quote_id}, invoice at {invoice}")

    return order


def payment_methods(
    receipt_id: str, quote_id: str, total: float, name: str, option: str
) -> Any:
    """
    Your only task is to help the user handle payment and payment relevant information.
    Args:
        receipt_id:Generate a random unique ID for each payment request prompted
        quote_id: Quote associated with each order
        name: Name of the customer
        total: Sum of the total products of the quantity and the price in each quotation.
        name: Name of the customer
        option: prompt the user for a payment method:
            - Mpesa :Paybill: 111000, Account Number: quote_id,  Amount: order total
            - Airtel :Paybill: 222000, Account Number: quote_id, Amount:total
            - Tkash :Paybill:333000, Account Number: quote_id, Amount:total
            -Bank Card :Request user for the following bank card details:
                1. Name on the card
                2. Account Number
                3. Expiry Date
                4. CVV (on the back of the card)
            and request for {quote_id}, Amount:{Total} to be paid
    """

    new_payment: Payments = Payments(quote_id, receipt_id, total, name, option)
    logger.info(f"the new payment object is {new_payment}")
    return new_payment


# Tool 3: Internet search after low embedding similarity results
internet_search_results:list[dict[str, str]]=[{}]
def low_similarity(user_message: str) -> list[dict[str, str]]:
    """
    Your only role is to carry out internet searches using the DuckDuckGo search python tool below specifically when the user wants to compare products or brands and if the query is outside the current scope. Be careful and do not process any harmful or vulgar searches and requests. Give information on the part type, uses, car types it can be used for
        Args:
            user_message:User query that is outside the contained LLM data and CSV data provided.

    """
    try:
        internet_search_results.append(DDGS().text(user_message, max_results=3))
        return internet_search_results
    except ValueError as e:
        logger.error(f"Error during web search: {str(e)}")
        raise
# Convert the tools to json format before parsing to model

tools: list[Any] = [
    get_json_schema(format_quotation),
    get_json_schema(payment_methods),
    get_json_schema(send_invoice),
    get_json_schema(low_similarity),
]

chat_history = ChatHistory()

# Optimized LLM pipeline
async def llm_pipeline(request:Request,llm_request_payload:LlmRequestPayload) -> Any:
    image_search_results:list=[]
    vector_search_results:list=[]
    image_inference_query:str=""
    try:
        #Redis client
        redis_client=request.app.state.redis
      
        if llm_request_payload.media_file_path:
            image_inference=await read_image(media_file_path=llm_request_payload.media_file_path)
            image_inference_query=image_inference.get("message", {}).get("content", "")
            image_search_results.append(await standard_retriever.vector_search(question=image_inference_query, collection_name="autoparts_test"))
        # Load the context
        elif llm_request_payload.user_message:
            vector_search_results.append(await standard_retriever.vector_search(question=llm_request_payload.user_message, collection_name="autoparts_test"))
        #Load the chat history db
        chat_history: list[Any] = await get_chat_history(client=redis_client, user_number=llm_request_payload.user_number)
        #chat_search_results:list[dict[Any, Any]] = await standard_retriever.vector_search(question=request.user_message, collection_name="history_vector_db")
        last_order: list[dict[str, Any]]=await get_last_order(user_phone_number=llm_request_payload.user_number)

        final_user_content: str = (
            f"Given this context: {vector_search_results}."
            f"Given the results from a search from the images {image_search_results}"
            f"Given the internet search results {internet_search_results}"
            f"And this chat history: {chat_history}. "
            f"Last user order if available {last_order}"
            f"And these customer details: {llm_request_payload.customer_details}. "
            f"Answer the user's query: '{llm_request_payload.user_message} or {image_inference_query} or {llm_request_payload.image_caption}'.\n\n"
            #f"{SECURITY_POST_PROMPT}" # Append security rules to every prompt
        )
        logger.info(final_user_content)
        system_message: list[dict[str, str]]= [
            {"role": "system", "content": BTB_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": final_user_content,
            },
        ]

        response = await llm_client.chat(
            model=llm_model,
            messages=system_message,
            tools=tools,
            stream=False,
            options={
                "temperature": 0.1,
                # "max_tokens": 100,  # For smaller screens and less complications
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0,
                "repeat_penalty": 1,
            },
        )
        # Extract the response content
        if "message" in response and "content" in response["message"]:
            content = response["message"]["content"]
            cleaned_response= convert_llm_output_to_readable(content)
            # Convert the responses to vectors for semantic search
            await add_to_chat_history(client=redis_client,user_number=llm_request_payload.user_number, user_message=llm_request_payload.user_message, llm_response=cleaned_response)
        return response
    except ValueError as e:
        print(f"Error generating repsonse with llm  {str(e)}")


# Optimized chatbot response function
