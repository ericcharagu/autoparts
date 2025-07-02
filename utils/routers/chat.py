# utils/routers/chat.py
import httpx
from fastapi import APIRouter, HTTPException, Request # <-- Import Request
from fastapi.responses import JSONResponse
from loguru import logger

from schemas import GenerationRequest
from utils.llm_tools import llm_pipeline
from utils.text_processing import convert_llm_output_to_readable

router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)

@router.post("/generate")
async def generate_text(request: Request, gen_request: GenerationRequest):
    """
    Endpoint for generating text from a prompt, used by the web UI.
    This is a protected endpoint, accessible only by authenticated users.
    """
    try:
        llm_reply = await llm_pipeline(request=gen_request, source="WEB")

        content = llm_reply.get("message", {}).get("content", "")

        cleaned_reply = convert_llm_output_to_readable(content)
        logger.info(f"Cleaned AI Response: {cleaned_reply}")

        return {"response": cleaned_reply}

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during generation: {str(e)}")
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": f"HTTP error: {str(e)}"},
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return JSONResponse(
            status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"}
        )
