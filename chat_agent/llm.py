"""
chat_agent/llm.py

Wrapper around Azure OpenAI chat models for LLM interactions.
Provides routing decisions and general question answering.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from chat_agent.prompts import ROUTING_PROMPT, ROUTING_SYSTEM_PROMPT, GENERAL_KNOWLEDGE_SYSTEM_PROMPT
from chat_agent.utils import parse_routing_decision
from chat_agent.logger import logger
from chat_agent.models import RouterOutput

# ============================================================
# Environment setup
# ============================================================

load_dotenv()

# ============================================================
# LLM Base Class
# ============================================================

class LLMSingletonBase(ChatOpenAI):
    """
    Base wrapper for Azure OpenAI LLM with environment configuration.
    """

    def __init__(self, **kwargs):
        default_kwargs = {
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
        super().__init__(**(default_kwargs | kwargs))


# ============================================================
# LLM Wrapper with Application Logic
# ============================================================

class llm_wrapper(LLMSingletonBase):
    """
    Singleton wrapper for LLM used in the chat agent.
    Adds methods for routing decisions and general knowledge answers.
    """

    def __init__(self, **kwargs):
        default_kwargs = {
            "model": os.getenv("OPENAI_MODEL"),
            "temperature": 0,
        }
        super().__init__(**(default_kwargs | kwargs))

    # -----------------------------
    # Routing Decisions
    # -----------------------------
    def decide_route(self, user_input: str, chat_history: str = "") -> RouterOutput:
        """
        Decide which tool or path the conversation should follow based on the user's input.

        Args:
            user_input: The question or request from the user
            chat_history: Compact representation of prior conversation

        Returns:
            str: Parsed routing decision
        """
        logger.info("LLM: Deciding route: start")
        
        # Prepare structured routing prompt
        routing_prompt_text = ROUTING_PROMPT.format(
            user_question=user_input,
            chat_history=chat_history,
        )

        messages = [
            {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
            {"role": "user", "content": routing_prompt_text},
        ]

        resp = self.invoke(messages)

        content = (getattr(resp, "content", str(resp)) or "").strip()
        logger.info(f"LLM: Deciding route: {content}")

        # Parse decision using shared utility (already hardened)
        parsed = parse_routing_decision(content)
        return parsed

    # -----------------------------
    # General Knowledge Answering
    # -----------------------------
    def answer_general(self, user_input: str) -> str:
        """
        Provide a general answer to a user's question without invoking any specialized tools.

        Args:
            user_input: The question or request from the user

        Returns:
            str: LLM-generated response
        """
        logger.info("LLM: Answering general: start")

        messages = [
            {"role": "system", "content": GENERAL_KNOWLEDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]

        resp = self.invoke(messages)
        return (getattr(resp, "content", str(resp)) or "").strip()
