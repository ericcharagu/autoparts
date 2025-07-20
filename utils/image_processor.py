from json import load
from loguru import logger
import os
from dotenv import load_dotenv
from dependancies import llm_client 
from typing import Any


#Load the environment
load_dotenv()

image_processing_model="qwen2.5vl:3b"

async def read_image(media_file_path:str):
    """
    Your only role is to analyse the image provided by the path and read its contents. You are in the automotive industry and thus do no try and always match for strict english semantics. Some of the images may contain product names such as lubricants, brake pads, spark-plugs, product codes such as POW-MASD-232, 283701239112, WUEW8712638,

    Args:
        media_file_path: Image uploaded/sent in by the user
    Return:
        response: Inference from uploaded media
    """
    image_processing_prompt: list[dict[str, str | list[str]]]=[{"role":"user", "content":f" You are in the automotive industry and thus do no try and always match for strict english semantics. Some of the images may contain product names such as lubricants, brake pads, spark-plugs, product codes such as POW-MASD-232, 283701239112, WUEW8712638. Format the output as an enquiry to for the parts in the image. Translate the image into a parts order query detailing each part and the quantity asked for ", "images":[media_file_path]}]
    try:
        response = await llm_client.chat(
                model=image_processing_model,
                messages=image_processing_prompt,
                stream=False,
                options={
                    "temperature": 0.0001,
                })
        return response
    except ValueError as e:
        logger.error(f"Cannot read image due to error {e}")
        raise