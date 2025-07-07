import io
from typing import Any, List

from dotenv import load_dotenv
from loguru import logger
from PIL import Image
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from utils.db.base import AsyncSession, Base

# Define logger path
logger.add("./logs/conversation_db.log", rotation="1 week")
load_dotenv()


class Conversation(Base):
    """Database model for conversation history with separate timestamps"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_message = Column(JSON)
    prompt_timestamp = Column(DateTime(timezone=True))
    llm_response = Column(String)
    llm_response_timestamp = Column(DateTime(timezone=True))
    source = Column(String)

    # Relationship to User
    user = relationship("User", back_populates="conversations")


def compress_image(
    image_data: bytes, max_size: tuple = (256, 256), quality: int = 70
) -> bytes:
    """Compress image to thumbnail size"""
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail(max_size)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Image compression failed: {e}")
        return image_data  # Fallback to original


def process_media_input(media_data: Any) -> dict:
    """Process media input for storage"""
    return {
        "original_data": media_data,
        "thumbnail": (
            compress_image(media_data) if isinstance(media_data, bytes) else None
        ),
        "media_type": "image" if isinstance(media_data, bytes) else "text",
        "is_processed": True,
    }


@logger.catch
async def save_conversation(
    session: AsyncSession, conversation_data: any
) -> Conversation:
    """
    Save complete conversation with pre-parsed timestamps
    Assumes timestamps are already properly formatted datetime objects
    """
    try:
        media_info = process_media_input(conversation_data.user_message)

        conversation = Conversation(
            user_message=media_info["original_data"],
            prompt_timestamp=conversation_data.prompt_timestamp,
            llm_response=conversation_data.llm_response,
            llm_response_timestamp=conversation_data.llm_response_timestamp,
            category=conversation_data.category,
            media_thumbnail=media_info["thumbnail"],
            media_type=media_info["media_type"],
            is_media_processed=media_info["is_processed"],
            source=conversation_data.source,
        )

        session.add(conversation)
        await session.commit()
        logger.success(
            f"Saved conversation {conversation.id} | "
            f"Prompt: {conversation_data.prompt_timestamp} | "
            f"Response: {conversation_data.llm_response_timestamp}"
        )
        return conversation
    except ValueError as e:
        await session.rollback()
        logger.debug(f"Failed to save conversation: {e}")
        raise


def get_recent_conversations(
    session: AsyncSession, limit: int = 10
) -> List[Conversation]:
    """
    Retrieve recent conversations with all timestamps
    """
    try:
        return (
            session.query(Conversation)
            .order_by(Conversation.interaction_timestamp.desc())
            .limit(limit)
            .all()
        )
    except ValueError as e:
        logger.debug(f"Failed to fetch conversations: {e}")
        return []
