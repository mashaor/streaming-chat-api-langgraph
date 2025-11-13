"""
chat_agent/graph.py

Defines the conversational graph workflow for the longevity chat agent using LangGraph.
This orchestrates the LLM routing, tool execution, persistence, and response streaming.
"""

import json
import time
from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.config import get_stream_writer

from chat_agent.logger import logger
from chat_agent.llm import llm_wrapper
from chat_agent.tools import longevity_clinical_trial_tool, aging_biomarker_tool
from chat_agent.graph_state import ChatAgentState
from chat_agent.models import RouterOutput
from chat_agent.utils import create_compact_chat_history
from chat_agent.db_helper import fetch_chat_history, persist_chat_history


# ============================================================
# LLM Singleton
# ============================================================

llm = llm_wrapper()


# ============================================================
# Node Definitions
# ============================================================

def classify_and_route(state: ChatAgentState) -> ChatAgentState:
    """Classify user query and route to the appropriate node."""
    if state.get("error"):
        logger.info("Node classify_and_route: skipped due to prior error")
        return state

    try:
        logger.info("Node classify_and_route: start")
        user_input = state["user_input"]
        chat_history = state["chat_history"]

        routing_output: RouterOutput = llm.decide_route(user_input, chat_history)
        if routing_output.error:
            state.setdefault("error", []).append(f"Node classify_and_route: {routing_output.error}")
            return state

        state["route"] = routing_output.decision
        state["rejection_message"] = routing_output.rejection_message
        return state

    except Exception as e:
        logger.error(f"Node classify_and_route: exception - {e}")
        state.setdefault("error", []).append(f"Node classify_and_route: {e}")
        return state


def longevity_clinical_trial_node(state: ChatAgentState) -> ChatAgentState:
    """Handles queries requiring the longevity clinical trial tool."""
    if state.get("error"):
        logger.info("Node longevity_clinical_trial_node: skipped due to prior error")
        return state

    try:
        logger.info("Node longevity_clinical_trial_node: start")

        writer = get_stream_writer()
        writer({
            "CurrentStep": "Researching information using longevity_clinical_trial_tool",
            "Response": {}
        })

        user_id = state.get("user_id")
        user_input = state.get("user_input")
        logger.info(f"Node longevity_clinical_trial_node: user_id: {user_id}")

        res = longevity_clinical_trial_tool(user_input, user_id)
        if res.get("status") == "error":
            state.setdefault("error", []).append(f"Node longevity_clinical_trial_node: {res.get('error')}")
        else:
            state["final_answer"] = res.get("response")

        return state

    except Exception as e:
        logger.error("Node longevity_clinical_trial_node: exception - %s", e)
        state.setdefault("error", []).append(f"Node longevity_clinical_trial_node: {e}")
        return state


def aging_biomarker_node(state: ChatAgentState) -> ChatAgentState:
    """Handles queries requiring the aging biomarker tool."""
    if state.get("error"):
        logger.info("Node aging_biomarker_node: skipped due to prior error")
        return state

    try:
        logger.info("Node aging_biomarker_node: start")
        user_id = state.get("user_id")
        user_input = state.get("user_input")

        writer = get_stream_writer()
        writer({
            "CurrentStep": "Researching information using aging_biomarker_tool",
            "Response": {}
        })

        res = aging_biomarker_tool(user_input, user_id)
        if res.get("status") == "error":
            state.setdefault("error", []).append(f"Node aging_biomarker_node: {res.get('error')}")
        else:
            state["final_answer"] = res.get("response")

        return state

    except Exception as e:
        logger.error(f"Node aging_biomarker_node: exception - {e}")
        state.setdefault("error", []).append(f"Node aging_biomarker_node: {e}")
        return state


def general_knowledge_node(state: ChatAgentState) -> ChatAgentState:
    """Handles general knowledge queries through the LLM."""
    if state.get("error"):
        logger.info("Node general_knowledge_node: skipped due to prior error")
        return state

    try:
        logger.info("Node general_knowledge_node: start")
        state["final_answer"] = llm.answer_general(state["user_input"])
        return state
    except Exception as e:
        logger.error(f"Node general_knowledge_node: exception - {e}")
        state.setdefault("error", []).append(f"Node general_knowledge_node: {e}")
        return state


def rejection_handler(state: ChatAgentState) -> ChatAgentState:
    """Handles rejected or invalid queries."""
    if state.get("error"):
        logger.info("Node rejection_handler: skipped due to prior error")
        return state

    try:
        logger.info("Node rejection_handler: start")
        if state.get("rejection_message"):
            state["final_answer"] = state["rejection_message"]
        else:
            state["final_answer"] = (
                "Sorry, I can't help with that request. "
                "Ask me about biomarkers, clinical trials, or longevity research."
            )
        return state
    except Exception as e:
        logger.error(f"Node rejection_handler: exception - {e}")
        state.setdefault("error", []).append(f"Node rejection_handler: {e}")
        return state


def get_chat_history(state: ChatAgentState) -> ChatAgentState:
    """Retrieves user session chat history and formats it compactly for the LLM."""
    if state.get("error"):
        logger.info("Node get_chat_history: skipped due to prior error")
        return state

    try:
        logger.info("Node get_chat_history: start")
        user_id = state.get("user_id", "")
        session_id = state.get("session_id", "")

        if not user_id:
            msg = "Node get_chat_history: user_id missing"
            logger.error(msg)
            state.setdefault("error", []).append(msg)
            return state

        result = fetch_chat_history(user_id=user_id, session_id=session_id)
        if result.get("status") == "success":
            chat_history_raw = result.get("chat_history", [])
            if chat_history_raw:
                chat_history_compact = create_compact_chat_history(chat_history_raw)
                state["chat_history"] = chat_history_compact
            else:
                logger.info("Node get_chat_history: no chat history found")
                state["chat_history"] = ""
        else:
            msg = result.get("message", "unknown error")
            logger.error(f"Node get_chat_history: failed - {msg}")
            state.setdefault("error", []).append(f"Node get_chat_history: {msg}")

        return state

    except Exception as e:
        logger.error(f"Node get_chat_history: exception - {e}")
        state.setdefault("error", []).append(f"Node get_chat_history: {e}")
        return state


def save_chat_history(state: ChatAgentState) -> ChatAgentState:
    """Persists both user and assistant messages."""
    if state.get("error"):
        logger.info("Node save_chat_history: skipped due to prior error")
        return state

    try:
        logger.info("Node save_chat_history: start")
        user_id = state.get("user_id", "")
        user_msg = state.get("user_input", "")
        assistant_msg = state.get("final_answer", "")
        route_used = state.get("route", None)
        session_id = state.get("session_id", None)

        if not user_id:
            msg = "Node save_chat_history: user_id is missing"
            logger.error(msg)
            state.setdefault("error", []).append(msg)
            return state

        # Save user message
        try:
            if user_id and user_msg:
                session_id = persist_chat_history(
                    user_id=user_id,
                    data=user_msg,
                    role="user",
                    session_id=session_id,
                    tool_name=None,
                )
        except Exception as e:
            logger.error(f"Node save_chat_history: failed to save user message - {e}")

        # Save assistant message
        try:
            if user_id and assistant_msg:
                session_id = persist_chat_history(
                    user_id=user_id,
                    data=assistant_msg,
                    role="assistant",
                    session_id=session_id,
                    tool_name=route_used,
                )
        except Exception as e:
            logger.error(f"Node save_chat_history: failed to save assistant message - {e}")

        state["session_id"] = session_id
        return state

    except Exception as e:
        logger.error(f"Node save_chat_history: exception - {e}")
        state.setdefault("error", []).append(f"Node save_chat_history: {e}")
        return state


def stream_final_response(state: ChatAgentState) -> ChatAgentState:
    """Streams the final answer to the client."""
    try:
        logger.info("Node stream_final_response: start")
        writer = get_stream_writer()
        writer({
            "CurrentStep": "Done",
            "Response": {
                "answer": state.get("final_answer", ""),
                "session_id": state.get("session_id", ""),
                "error": state.get("error", []),
            },
        })
        return state
    except Exception as e:
        logger.error(f"Node stream_final_response: exception - {e}")
        state.setdefault("error", []).append(f"Node stream_final_response: {e}")
        return state


# ============================================================
# Graph Assembly
# ============================================================

def build_graph():
    """Constructs and compiles the LangGraph workflow."""
    g = StateGraph(ChatAgentState)

    g.add_node("get_chat_history", get_chat_history)
    g.add_node("classify_and_route", classify_and_route)
    g.add_node("longevity_clinical_trial_node", longevity_clinical_trial_node)
    g.add_node("aging_biomarker_node", aging_biomarker_node)
    g.add_node("general_knowledge_node", general_knowledge_node)
    g.add_node("rejection_handler", rejection_handler)
    g.add_node("save_chat_history", save_chat_history)
    g.add_node("stream_final_response", stream_final_response)

    # Entry point
    g.set_entry_point("get_chat_history")

    # Edges
    g.add_edge("get_chat_history", "classify_and_route")
    g.add_conditional_edges(
        "classify_and_route",
        lambda s: s.get("route", "general_knowledge"),
        {
            "longevity_clinical_trial_tool": "longevity_clinical_trial_node",
            "aging_biomarker_tool": "aging_biomarker_node",
            "general_knowledge": "general_knowledge_node",
            "rejection_handler": "rejection_handler",
        },
    )
    g.add_edge("general_knowledge_node", "save_chat_history")
    g.add_edge("longevity_clinical_trial_node", "save_chat_history")
    g.add_edge("aging_biomarker_node", "save_chat_history")
    g.add_edge("rejection_handler", "save_chat_history")

    # Streaming conditional edge
    g.add_conditional_edges(
        "save_chat_history",
        lambda s: s.get("enable_streaming", False),
        {True: "stream_final_response", False: END},
    )

    return g.compile()


# ============================================================
# Entrypoint
# ============================================================

def run_chat_agent(
    user_input: str,
    user_id: str,
    session_id: Optional[str] = None,
    enable_streaming: bool = False,
) -> dict:
    """Run the chat agent end-to-end."""
    state: ChatAgentState = {
        "user_input": user_input,
        "user_id": user_id,
        "session_id": session_id,
        "enable_streaming": enable_streaming,
    }

    graph = build_graph()

    # Streaming mode
    if enable_streaming:
        logger.info("Node run_chat_agent: streaming mode")

        def _event_stream():
            for chunk in graph.stream(state, stream_mode="custom"):
                yield f"data: {json.dumps(chunk)}\n\n"

        return _event_stream()

    # Non-streaming mode
    else:
        logger.info("Node run_chat_agent: normal mode")
        out = graph.invoke(state)
        return {
            "answer": out.get("final_answer", ""),
            "session_id": out.get("session_id", ""),
            "error": out.get("error", []),
        }
