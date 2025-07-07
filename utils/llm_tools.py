#!/usr/bin/env python3
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, List

from dotenv import load_dotenv
from duckduckgo_search import DDGS
from loguru import logger
from ollama import AsyncClient
from schemas import CustomerDetails, GenerationRequest
from transformers.utils import get_json_schema

from utils.db.qdrant import standard_retriever
from utils.orders import Order, OrderItem
from utils.payment import Payments
from utils.prompt import BTC_SYSTEM_PROMPT
from utils.whatsapp import send_invoice_whatsapp

# Load environment variables
load_dotenv()

# Initialize logger file and its path
logger.add("./logs/llm_app.log", rotation="1 week")

# The client based on the container's address
ollama_client = AsyncClient(host="http://host.docker.internal:11434")
llm_model = "qwen3:0.6b"


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


def create_order(request: GenerationRequest, customer_details: list) -> str:
    """
    Using the customer's details and the request to generate an invoice pdf for the order and confirmation.Create it and send it to the user via whatsapp
    Args:
        - request: Users's request from a whatsapp message.
        - customer_details: List of containing the customer's information such as:
                - phone_number: user's registered whatsapp number to the service
                - dropoff_location: default drop-off location of the user
                - business_id: unique identifier of the garage or business type the user is registered with.
                - customer_name: user's registered name or default in whatsapp headers
                - customer_id: user's unique id

    """
    order_details = CustomerDetails(**customer_details)
    customer_invoice = Order(order_details).create_invoice_pdf()

    send_invoice_whatsapp(customer_invoice, customer_details[0]["phone_number"])


# Tool functions - imported from utils in the actual code
def format_quotation(
    quote_id: str,
    cus_id: str,
    garage_id: str,
    name: str,
    location: str,
    items: List[str],
    quantities: List[int],
    prices: List[float],
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
          quantities:List of item quantities
          prices: List of item prices
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
    order = Order(
        quote_id=quote_id,
        cus_id=cus_id,
        garage_id=garage_id,
        name=name,
        location=location,
        items=order_items,
    )

    # Generate invoice
    invoice_path = order.create_invoice_pdf()
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

    new_payment = Payments(quote_id, receipt_id, total, name, option)
    logger.info(f"the new payment object is {new_payment}")
    return new_payment


def internet_search(request: GenerationRequest):
    """
    Your only role is to carry out internet searches using the DuckDuckGo search python tool below specifically when the user wants to compare products or brants. Give information on the part type, uses, car types it can be used for
        Args:
        request: whatsapp request object that contains the  prompt and the timestamp of the time the message was sent
    Retu:rrns:
        a list of the vector db results

    """

    search_results = DDGS().text(request.prompt, max_results=3)
    return search_results


# Convert the tools to json format before parsing to model

tools = [
    get_json_schema(payment_methods),
    get_json_schema(create_order),
    # get_json_schema(internet_search),
]


# Optimized LLM pipeline
async def llm_pipeline(
    request: GenerationRequest,
    source: str,
    user_number: str,
    customer_details: list,
    top_k=3,
) -> Any:
    try:
        # Load the context as the questions generated fron the OCR
        vector_search_results = await standard_retriever.vector_search(request.prompt)
        # logger.info(f"result from the db search is {vector_search_results}")
        # Add current user input(Refined version)
        system_message = [
            {"role": "system", "content": BTC_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Use {vector_search_results} and {customer_details} to answer {request.prompt} as per your instructions,",
            },
        ]
        response = await ollama_client.chat(
            model=llm_model,
            messages=system_message,
            tools=tools,
            stream=False,
            options={
                "temperature": 0.2,
                "max_tokens": 100,  # For smaller screens and less complications
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0,
            },
        )
        llm_response_timestamp = datetime.now()
        # Extract the response content
        if "message" in response and "content" in response["message"]:
            content = response["message"]["content"]

            conversation_data_dict = {
                "user_id": user_number,
                "user_message": request.prompt,
                "prompt_timestamp": request.prompt_timestamp,
                "llm_response": content,
                "llm_response_timestamp": llm_response_timestamp,
                "source": source,
            }  # for logging purposes
            # await single_insert_query(
            #     db_table=Conversation, query_values=conversation_data_dict
            # )
            # Convert the responses to vectors for semantic search
        return response
    except ValueError as e:
        print(f"Error generating repsonse with llm  {str(e)}")


# Optimized chatbot response function
