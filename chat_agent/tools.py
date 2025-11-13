"""
chat_agent/tools.py

Stub implementations for tools used by the Longevity Research Chat Agent.
Includes:
- longevity_clinical_trial_tool
- aging_biomarker_tool
"""

from typing import Any, Dict
import time
from chat_agent.logger import logger


def longevity_clinical_trial_tool(user_input: str, user_id: str) -> Dict[str, Any]:
    """
    Stub function for retrieving information from Longevity Clinical Trial Tracker.

    Args:
        user_input (str): The user's query.
        user_id (str): The unique identifier of the user.

    Returns:
        dict: Response dictionary containing status and response data.
    """
    try:
        logger.info("longevity_clinical_trial_tool: start")
        time.sleep(5)  # Simulate processing delay
        return {
            "status": "ok",
            "response": "Detailed response from longevity_clinical_trial_tool"
        }
    except Exception as e:
        logger.error(f"longevity_clinical_trial_tool: exception - {e}")
        return {"status": "error", "error": str(e)}


def aging_biomarker_tool(user_input: str, user_id: str) -> Dict[str, Any]:
    """
    Stub function for retrieving information from the Aging Biomarker Database.

    Args:
        user_input (str): The user's query.
        user_id (str): The unique identifier of the user.

    Returns:
        dict: Response dictionary containing status and response data.
    """
    try:
        logger.info("aging_biomarker_tool: start")
        time.sleep(5)  # Simulate processing delay
        return {
            "status": "ok",
            "response": "Detailed response from aging_biomarker_tool"
        }
    except Exception as e:
        logger.error(f"aging_biomarker_tool: exception - {e}")
        return {"status": "error", "error": str(e)}
