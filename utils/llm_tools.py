#!/usr/bin/env python3

import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any
from fastapi import Request
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from loguru import logger
from ollama import AsyncClient
from prompts import BTC_SYSTEM_PROMPT
from transformers.utils import get_json_schema
import os
from schemas import CustomerDetails, GenerationRequest
from utils.db.qdrant import standard_retriever
from utils.db.query import get_last_order
from utils.image_processor import read_image
from utils.orders import Order, OrderItem
from utils.payment import Payments
from dependancies import llm_client
from utils.cache import get_chat_history, add_to_chat_history
from prompts import BTC_SYSTEM_PROMPT, BTB_SYSTEM_PROMPT, SECURITY_POST_PROMPT
from utils.text_processing import convert_llm_output_to_readable
from utils.whatsapp import send_invoice_whatsapp
# Load environment variables
load_dotenv()

# Adding logging information
logger.add("./logs/llm_app", rotation="10 MB")
# llm_model = "qwen3:0.6b"
# llm_model = "qwen2.5:1.5b"
llm_model = "qwen3:8b"


# Initialize the HybridRetriever
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


async def init_qdrant_db(knowledge_base: Any):
    # Get the chunked and embedded data from the model
    chunks: list[dict[str, int | str | list[float]]] = await standard_retriever.initialize_knowledge_base(knowledge_base)

    # Load the chunks into the collection
    await standard_retriever.setup_qdrant_collection(chunks)


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

def create_order(customer_details: list[dict[str , int|str]]) -> None:
    """
    Using the customer's details and the request to generate an invoice pdf for the order and confirmation.Create it and send it to the user via whatsapp
    Args:
        - request: Users's request from a whatsapp message.
        - customer_details: List of containing the customer's information such as:
                - phone_number: user's registered whatsapp number to the service
                - location: default drop-off location of the user
                - business_id: unique identifier of the garage or business type the user is registered with.
                - customer_name: user's registered name or default in whatsapp headers
                - customer_id: user's unique id

    """
    order_details = CustomerDetails(customer_details)
    customer_invoice = Order(order_details).create_invoice_pdf()

    send_invoice_whatsapp(invoice_file_path=customer_invoice, recipient_number=customer_details[0]["phone_number"])

# Tool functions - imported from utils in the actual code
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
    invoice_path: str = order.create_invoice_pdf()
    logger.info(f"Created order {order.quote_id}, invoice at {invoice_path}")

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


# Tool 3: Ibternet search after low embedding similarity resukts
def low_similarity(user_input: str):
    """
    If the vector db search results yields search results of less than 70% for a 3 items. Sieve through the input to identify the item and quantity requried. After:
    1. Ask the user for the make or brand or any other details.
    2. Inform the user of the closest matches
    3. Based on those, search the internt for the similarities between the products asked for and the products found and give them in tabular or prose form

    Args:
        user_input: Enquiry from the user on the car part

    Returns:
        web results from using the Duckduck Go Search python tool
    """
    try:
        search_results = DDGS().text(user_input, max_results=3)
        return search_results
    except ValueError as e:
        logger.error(f"Error during web search: {str(e)}")
        return []

# Convert the tools to json format before parsing to model

tools = [
    get_json_schema(format_quotation),
    get_json_schema(payment_methods),
    get_json_schema(read_image),
]

chat_history = ChatHistory()

# Optimized LLM pipeline
async def llm_pipeline(request:Request,
    request_payload: GenerationRequest, source: str, user_number:str, customer_details:list[dict]
) -> Any:
    try:
        #Redis client
        redis_client=request.app.state.redis
        # Load the context
        vector_search_results: list[dict[Any, Any]] = await standard_retriever.vector_search(question=request_payload.user_message, collection_name="autoparts_test")
        logger.info(f"Vector Search results:{vector_search_results}")
        
        #Load the chat history db
        chat_history: list[Any] = await get_chat_history(client=redis_client, user_number=user_number)
        #chat_search_results:list[dict[Any, Any]] = await standard_retriever.vector_search(question=request.user_message, collection_name="history_vector_db")
        last_order: list[dict[str, Any]]=await get_last_order(user_phone_number=user_number)

        final_user_content: str = (
            f"Given this context: {vector_search_results}. "
            f"And this chat history: {chat_history}. "
            f"Last user order if available {last_order}"
            f"And these customer details: {customer_details}. "
            f"Answer the user's query: '{request_payload.user_message}'.\n\n"
            #f"{SECURITY_POST_PROMPT}" # Append security rules to every prompt
        )
        logger.info(f"Customer details:{customer_details}")
        logger.info(final_user_content)
        system_message: list[dict[str, str]]= [
            {"role": "system", "content": BTB_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": final_user_content,
            },
        ]
        if source == "WEB":
            response = await llm_client.chat(
                model=llm_model,
                stream=False,
                messages=system_message,
                tools=tools,
                options={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "top_k": 20,
                    "min_p": 0,
                    # "max_tokens": 1000,
                    "repeat_penalty": 1,
                },
            )
        else:
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
        llm_response_timestamp = datetime.now()
        # Extract the response content
        if "message" in response and "content" in response["message"]:
            content = response["message"]["content"]
            cleaned_response= convert_llm_output_to_readable(content)

            conversation_data_dict: dict[str, Any | datetime | str] = {
                "user_message": request_payload.user_message,
                "prompt_timestamp": request_payload.message_timestamp,
                "llm_response": cleaned_response,
                "llm_response_timestamp": llm_response_timestamp,
                "source": source,
            }  # for logging purposes
            
            # Convert the responses to vectors for semantic search
            await add_to_chat_history(client=redis_client,user_number=user_number, user_message=request_payload.user_message, llm_response=cleaned_response)
        return response
    except ValueError as e:
        print(f"Error generating repsonse with llm  {str(e)}")


# Optimized chatbot response function
