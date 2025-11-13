"""
chat_agent/db_helper.py

Utility functions and data models for managing chat history persistence and retrieval.
This module abstracts database interactions (e.g., storage backend).
"""

import os
import uuid
import datetime
from typing import Optional, Literal, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from chat_agent.logger import logger
from chat_agent.models import Route

# ============================================================
# Environment setup
# ============================================================

load_dotenv()
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", 10))

# ============================================================
# Data Model
# ============================================================


class ChatHistory(BaseModel):
    """
    Represents a single message in the chat history stored in Cosmos DB (or any backend).
    """

    id: str = Field(..., description="Unique message identifier")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Main session identifier for the conversation")
    role: Literal["user", "assistant"] = Field(..., description="Type of message: user or assistant")
    tool_used: Optional[Route] = Field(default=None, description="Tool used to generate this message (if applicable)")
    message: str = Field(..., description="The actual message content")
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        description="Timestamp when the message was created (ISO 8601 format)",
    )


# ============================================================
# Persistence Functions
# ============================================================


def persist_chat_history(
    user_id: str,
    data: str,
    role: Literal["user", "assistant"],
    session_id: Optional[str] = None,
    tool_name: Optional[Route] = None,
) -> Optional[str]:
    """
    Persists a chat message into the database. Creates a new session ID if one is not provided.
    Returns the session_id used for this message.
    """
    try:
        logger.info("persist_chat_history: start")

        current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        message_id = str(uuid.uuid4())

        # Create session ID if this is the start of a new conversation
        if not session_id:
            session_id = str(uuid.uuid4())

        message = ChatHistory(
            id=message_id,
            user_id=user_id,
            session_id=session_id,
            role=role,
            tool_used=tool_name if role == "assistant" else None,
            message=data,
            created_at=current_time,
        )

        # TODO: Insert message into actual database
        logger.info(f"Chat history saved for session_id={session_id} role={role}")

        return session_id

    except Exception as e:
        logger.error(f"persist_chat_history: failed to insert chat history - {e}", exc_info=True)
        raise


# ============================================================
# Retrieval Functions
# ============================================================


def fetch_chat_history(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = CHAT_HISTORY_LIMIT,
) -> dict[str, Any]:
    """
    Retrieve chat history for a given user and session.
    Returns an empty list if session_id is not provided.

    Args:
        user_id: The user whose chat history to fetch
        session_id: Optional conversation session ID
        limit: Maximum number of messages to retrieve
    """
    try:
        logger.info(f"fetch_chat_history: start (user_id={user_id}, session_id={session_id})")

        if not session_id:
            logger.info("fetch_chat_history: no session_id provided — returning empty history")
            return {"status": "success", "chat_history": [], "count": 0}

        # TODO: Replace this with a database query
        chat_messages: list[dict[str, Any]] = []

        logger.info(f"fetch_chat_history: retrieved {len(chat_messages)} messages")
        return {
            "status": "success",
            "chat_history": chat_messages,
            "count": len(chat_messages),
        }

    except Exception as e:
        logger.error(f"fetch_chat_history: error retrieving chat history - {e}", exc_info=True)
        return {
            "status": "error",
            "chat_history": [],
            "message": str(e),
        }
