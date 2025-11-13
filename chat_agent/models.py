from pydantic import BaseModel, Field
from typing import Literal, Optional, List

Route = Literal["aging_biomarker_tool", "longevity_clinical_trial_tool", "general_knowledge", "rejection_handler"]

class RouterOutput(BaseModel):
    """Simplified structured output from the routing node."""
    decision: Route = Field(..., description="The routing decision for the user's query")
    reasoning: str = Field(..., description="Brief explanation of why this route was chosen")
    rejection_message: Optional[str] = Field(None, description="User friendly message to be displayed if the question violates guardrails")
    error: Optional[str] = Field(None, description="Error message if the routing decision failed")

class ChatAIRequest(BaseModel):
    user_query: str
    user_id: str
    submission_id: Optional[str] = ""
    quote_ids: Optional[List[str]] = []
    session_id: Optional[str] = ""
    enable_streaming: Optional[bool] = False

class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    tool_name: Optional[Route] = None
    content: str

class ChatHistory(BaseModel):
    history: List[HistoryItem]
