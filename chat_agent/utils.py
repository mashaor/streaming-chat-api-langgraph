"""
chat_agent/utils.py

Utility functions for the Longevity Research Chat Agent.
Includes:
- parse_routing_decision
- create_compact_chat_history
"""

import json
import re
from typing import List, Any
from chat_agent.logger import logger
from chat_agent.models import RouterOutput, ChatHistory


def parse_routing_decision(llm_response: str) -> RouterOutput:
    """
    Parse routing decision from LLM response.

    Args:
        llm_response (str): Raw response from LLM (should be JSON).

    Returns:
        RouterOutput: Object containing decision, reasoning, and optional error message.
    """
    try:
        response_text = llm_response.strip()

        # Handle case where LLM might wrap JSON in markdown
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # Attempt to sanitize trailing commas
            sanitized = re.sub(r',\s*(?=[}\]])', '', response_text)
            data = json.loads(sanitized)

        # Validate using Pydantic
        routing_output = RouterOutput(**data)
        logger.info(f"Routing decision: {routing_output.decision}")
        logger.info(f"Routing reasoning: {routing_output.reasoning}")
        return routing_output

    except Exception as e:
        logger.error(f"parse_routing_decision Error: {str(e)}")
        return RouterOutput(
            decision="rejection_handler",
            reasoning="error parsing routing decision",
            error=f"parse_routing_decision Error: {str(e)}"
        )


def create_compact_chat_history(db_chat_history: List[ChatHistory]) -> str:
    """
    Converts a list of ChatHistory objects into a compact string suitable for LLM input.

    Args:
        db_chat_history (List[ChatHistory]): List of chat history objects from the database.

    Returns:
        str: Compact string representation of chat history with role/content pairs.
    """
    lines: List[str] = []

    for entry in db_chat_history:
        role = entry.role
        message = entry.message

        if role in ("user", "assistant") and message:
            tool_used = entry.tool_used
            if tool_used:
                lines.append(f"{role} (tool_used: {tool_used}): {message}")
            else:
                lines.append(f"{role}: {message}")

    return "\n".join(lines)
