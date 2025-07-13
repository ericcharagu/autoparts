from json import load
from loguru import logger
import os
from dotenv import load_dotenv
from dependancies import llm_client 


#Load the environment
load_dotenv()

image_processing_model="qwen2.5vl:3b"

async def read_image(image_path:str):
    """
    Your only role is to analyse the image provided by the path and read its contents. You are in the automotive industry and thus do no try and always match for strict english semantics. Some of the images may contain product names such as lubricants, brake pads, spark-plugs, product codes such as POW-MASD-232, 283701239112, WUEW8712638,

    Args:
        image_path: file path of the image sent via whatsapp message
    Return:
        response: Inference from uploaded media
    """
    image_processing_prompt: list[dict[str, str]]=[{"role":"user", "content":f"Analyse the image provided{image_path} read whatever is written. Bias heavily towards automotive industry terminologies and products"}]
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