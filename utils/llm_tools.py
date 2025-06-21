#!/usr/bin/env python3

from datetime import datetime, timedelta, timezone
from typing import Any, List

from dotenv import load_dotenv
from duckduckgo_search import DDGS
from loguru import logger
from ollama import AsyncClient
from pydantic import BaseModel
from transformers.utils import get_json_schema

from utils.db import HybridRetriever
from utils.orders import Orders
from utils.payment import Payments

# Load environment variables
load_dotenv()

# Initialize logger file and its path
logger.add("./logs/llm_app.log", rotation="500 MB")

# The client based on the container's address
ollama_client = AsyncClient(host="http://host.docker.internal:11434")
llm_model="qwen3:0.6b"
# Initialize the HybridRetriever
standard_retriever = HybridRetriever()

async def init_qdrant_db(knowledge_base:Any):
    # Get the chunked and embedded data from the model
    chunks = await standard_retriever.initialize_knowledge_base(knowledge_base)

    # Load the chunks into the collection
    await standard_retriever.setup_qdrant_collection(chunks)

SYSTEM_DATE = datetime.now().date()  # Current system time
PAYMENT_DEADLINE = SYSTEM_DATE + timedelta(
    days=14
)  # Assuming the customer is expected to pay within 14 days
#TODO:Add language model or set have the model be multlingual based on a system message setting
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
# System message
SYSTEM_PROMPT = """
Role: You are an enthusiastic customer care assistant for Autoparts, Kenya's leading wholesale car parts supplier helping customers save money on quality auto parts.

Key Responsibilities:
1. Order Processing:
   - Collect complete order details
   - Calculate wholesale prices with bulk discounts
   - Highlight customer savings at every step

2. Customer Service:
   - Provide accurate product information
   - Explain cost benefits of wholesale purchases
   - Answer shipping and warranty questions

Required Customer Information:
- Full Name:
- Delivery Location (County/Street):
- Contact Number:
- Vehicle Make/Model (if applicable):

Order Processing Format:
[Item Name] | [Quantity] | [Unit Price] | [Line Total]
[Potential Savings Note]

Pricing Rules:
1. All prices in Ksh (Kenya Shillings)
2. 5% discount on orders over Ksh 50,000
3. 10% discount for repeat customers
4. VAT included at 16%

Sample Response:
"Thank you for choosing [Company Name]! You're saving Ksh 3,450 on this order compared to retail prices. Let me process your:
1. Toyota Hilux brake pads (2 sets @ Ksh 4,500) = Ksh 9,000
   - Save Ksh 600 vs. retail!
2...."

Special Instructions:
- Always calculate/show savings compared to retail
- Confirm delivery timelines (Nairobi: 24hrs, Counties: 2-3 days)
- Include warranty information
- End with upsell opportunity

Current Context: {context}
Customer Inquiry: {input}

[Begin by warmly greeting customer and requesting any missing information]    Display all order details in tabular format.
    Order Items\tQuantity\tUnit Price (Ksh.)\t Amount(Ksh.)
Always add the total under the total as a rowl: Total : ksh. xxxxx.x as a float
    Use a maximum of nine sentences and be concise.
    Answer:"""


# Tool functions - imported from utils in the actual code
def format_quotation(
    quote_id: str,
    cus_id: str,
    garage_id: str,
    name: str,
    location: str,
    items: List[str],
    quantity: List[int],
    price: List[float],
    total: float,
    created_at: datetime,
    payment_status: str,
    payment_date: datetime,
):
    """
    Your only task is to generate a summary of the interaction and the customer's requirements. If any of the values are missing, ask the user kindly

    Args:
        quote_id: Generate a random uniq ID for each quotation generated per interation.
        cus_id: A unique customer id that is given to each user. Similar to IP addresses
        garage_id:A unique garage identifier associated with each user
        name: Name of the customer
        location: Location of the customer for delivery
        items: User order items
        quantity: Number of individual products
        total: Total price of goods. Sum of the total products of the quantity and the price in each quotation
        price: The price of each product
        created_at: Current date of the interaction/system
        payment_status: Describes the current stage of the order fulfilment. Options are [processing, pending,shipped, delivered]
        payment_date: Date omn which the customer paid the invoice. By default they are given 14 days from the {created_at} date"""

    new_order = Orders(
        quote_id,
        cus_id,
        garage_id,
        name,
        location,
        items,
        quantity,
        price,
        total,
        created_at=SYSTEM_DATE,
        payment_status="pending",
        payment_date=SYSTEM_DATE + timedelta(days=14),
    )

    logger.info(f"The new order details are {new_order}")
    return new_order


def payment_methods(
    receipt_id: str, quote_id: str, total: float, name: str, option: str
) -> Any:
    """
    Your only task is to help the user handle payment and payment relevant information.
    Args:
        receipt_id:Generate a random unique ID for each payment request prompted
        quote_id: Quote associated with each order
        name: Name of the customer
        total: Total price of goods. Sum of the total products of the quantity and the price in each quotation.
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

#Tool 3: Ibternet search after low embedding similarity resukts
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

tools = [get_json_schema(format_quotation), get_json_schema(payment_methods), get_json_schema(low_similarity)]

# Define request models
class GenerationRequest(BaseModel):
    prompt: str
    prompt_timestamp: datetime = datetime.now(timezone.utc)



# Optimized LLM pipeline
async def llm_pipeline(request:GenerationRequest, source:str, top_k=3) -> Any:

    try:
        # Load the context as the questions generated fron the OCR
        vector_search_results = await standard_retriever.vector_search(request.prompt)
        logger.info(f"result from the db search is {vector_search_results}")

        # Add current user input(Refined version)
        system_message = [
            {"role":"system", "content":SYSTEM_PROMPT},{
            "role": "user",
            "content": f"Use {vector_search_results} to answer {request.prompt} as per your instructions. "
        }]
        if source == "WEB":
            response = await ollama_client.chat(
                model=llm_model,
                stream=False,
                messages=system_message,
                tools=tools,
                options={
                    "tokenize": False,
                    "add_generation_prompt": True,
                    "temperature": 0.6,
                    "top_p": 0.95,
                    "top_k": 20,
                    "min_p": 0,
                    "max_tokens": 1000,
                    "enable_thinking": False,
                },
            )
        else:
            response = await ollama_client.chat(
                model=llm_model,
                messages=system_message,
                tools=tools,
                stream=False,
                options={
                    "temperature": 0.5,
                    "tokenize": False,
                    "add_generation_prompt": True,
                    "max_token": 100,  # For smaller screens and less complications
                    "top_p": 0.95,
                    "top_k": 20,
                    "min_p": 0,
                    "enable_thinking": False,
                },
            )
        llm_response_timestamp = datetime.now(timezone.utc)
        # Extract the response content
        if "message" in response and "content" in response["message"]:
            content = response["message"]["content"]
            conversation_data_dict = {
                "user_message": request.prompt,
                "prompt_timestamp": request.prompt_timestamp,
                "llm_response": content,
                "llm_response_timestamp": llm_response_timestamp,
                "source": source,
            } #for loggingg purposes



        return response
    except ValueError as e:
        print(f"Error generating repsonse with llm  {str(e)}")


# Optimized chatbot response function
