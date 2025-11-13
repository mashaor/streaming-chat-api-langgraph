from typing import TypedDict, Any, Optional
from chat_agent.models import Route

class ChatAgentState(TypedDict, total=False):
    # input
    user_id: Optional[str]
    user_input: str
    session_id: Optional[str]
    
    # output
    route: Optional[Route]
    rejection_message: Optional[str]
    final_answer: Optional[str]
    error: Optional[list[str]]
    chat_history: Optional[dict[str, Any]]
    enable_streaming: Optional[bool]
