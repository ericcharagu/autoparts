#!/usr/bin/env python3
from collections import defaultdict, deque
from datetime import datetime, timedelta
import os
from re import search
from typing import Any
import uuid

from dependancies import llm_client
from dotenv import load_dotenv
from fastapi import Request
from loguru import logger
from ollama import AsyncClient
from schemas import CustomerDetails, GenerationRequest, LlmRequestPayload, UserOrders
from transformers.utils import get_json_schema
from utils.cache import add_to_chat_history, get_chat_history
from utils.db.graph_retriever import graph_retriever
from utils.db.qdrant import COLLECTION_NAME, standard_retriever
from utils.db.query import get_last_order
from utils.llm.image_processor import read_image
from utils.llm.prompt import BTB_SYSTEM_PROMPT, BTC_SYSTEM_PROMPT, SECURITY_POST_PROMPT
from utils.llm.text_processing import convert_llm_output_to_readable
from utils.llm.tools import (
    format_quotation,
    low_similarity,
    payment_methods,
    send_invoice,
)

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


internet_search_results: list[dict[str, str]] = [{}]
tools: list[Any] = [
    get_json_schema(format_quotation),
    get_json_schema(payment_methods),
    get_json_schema(send_invoice),
    get_json_schema(low_similarity),
    get_json_schema(read_image)
]
available_functions={
            "format_quotation": format_quotation,
            "payment_methods": payment_methods,
            "send_invoice": send_invoice,
            "low_similarity": low_similarity,
            "read_image":read_image
        }
chat_history = ChatHistory()


# Optimized LLM pipeline
async def tool_checker(user_message:str) -> None:
    """ 
    Runs the tool call
    """
    messages=[{"role":"user", "content":user_message}]
    response = await llm_client.chat(
        model=llm_model,
        messages=messages,
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
    return response

async def llm_pipeline(request: Request, llm_request_payload: LlmRequestPayload) -> Any:
    image_search_results: list = []
    vector_search_results: list = []
    graph_search_results: list[Any] = []
    image_inference_query: str = ""
    try:
        # Redis client
        redis_client = request.app.state.redis

        if llm_request_payload.media_file_path:
            image_inference = await read_image(
                media_file_path=llm_request_payload.media_file_path
            )
            image_inference_query = image_inference.get("message", {}).get(
                "content", ""
            )
            image_search_results.append(
                await standard_retriever.vector_search(
                    question=image_inference_query, collection_name="lane_data_collection"
                )
            )
        # Load the context
        elif llm_request_payload.user_message:
            graph_search_results, graph_search_summary = (
                await graph_retriever.search_parts_by_name(
                    llm_request_payload.user_message
                )
            )
            vector_search_results.append(
                await standard_retriever.vector_search(
                    question=llm_request_payload.user_message,
                    collection_name=COLLECTION_NAME,
                )
            )
        # Load the chat history db
        chat_history: list[Any] = await get_chat_history(
            client=redis_client, user_number=llm_request_payload.user_number
        )
        last_order: list[dict[str, Any]] = await get_last_order(
            user_phone_number=llm_request_payload.user_number
        )


        final_user_content: str = (
            f"Given this context: {vector_search_results}."
            f"Structured data from the the knowledge graph{graph_search_results}\n"
            f"Given the results from a search from the images {image_search_results}\n"
            f"Given the internet search results {internet_search_results}\n"
            f"And this chat history: {chat_history}.\n"
            f"Last user order if available {last_order}\n"
            f"And these customer details: {llm_request_payload.customer_details}.\n"
            f"Answer the user's query: {llm_request_payload.user_message}\n"
            f"Answer the image query {image_inference_query}\n"
            f"Answer the caption attached to the media {llm_request_payload.image_caption}\n"
            #f"{SECURITY_POST_PROMPT}" # Append security rules to every prompt
        )
        llm_request_payload.messages.append({"role":"user", "content":final_user_content})
        response = await llm_client.chat(
            model=llm_model,
            messages=llm_request_payload.messages,
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
        return response
    except Exception as e:
        logger.debug(f"Error generating repsonse with llm  {str(e)}", exc_info=True)
        return {
            "message": {
                "content": "I'm sorry, I encountered a system error and could not process your request. Please try again later."
            }
        }


# Optimized chatbot response for tool calling

