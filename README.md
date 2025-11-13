# Streamin API Chat Agent using Langgraph

Project showing how to build a production-style chat agent that:

- Routes user requests to specialized tools (topic-specific functions)
- Streams intermediate steps to the UI
- Stores and recalls chat history
- Handles rejections and guardrails
- Provides both normal and streaming response modes

## Table of contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [The Core Idea: Route-to-Tools](#the-core-idea-route-to-tools)
- [End-to-End Flow](#end-to-end-flow)
- [Why chat history matters for routing](#why-chat-history-matters-for-routing)
- [Graph Architecture (`chat_agent/graph.py`)](#graph-architecture-chat_agentgraphpy)
- [Routing: From Prompt to RouterOutput](#routing-from-prompt-to-routeroutput)
- [Why deterministic routing vs. generic tool-calling](#why-deterministic-routing-vs-generic-tool-calling)
- [Tools: Domain Logic (`chat_agent/tools.py`)](#tools-domain-logic-chat_agenttoolspy)
- [Streaming UI Hooks](#streaming-ui-hooks)
- [Persistence (`chat_agent/db_helper.py`)](#persistence-chat_agentdb_helperpy)
- [Error Handling and Robustness](#error-handling-and-robustness)
- [Running the Agent](#running-the-agent)
- [Adapting the Classifier Prompt](#adapting-the-classifier-prompt)
- [Extending the Agent](#extending-the-agent)
- [Troubleshooting](#troubleshooting)
- [Design Principles](#design-principles)
- [License](#license)

## Quick Start

- Python 3.11+

Install dependencies (create a virtualenv if you prefer):

```bash
pip install -r requirements.txt
```

Run the FastAPI app (from the project root):

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 7272
```

Call the agent (example):

```python
from chat_agent.graph import run_chat_agent

result = run_chat_agent(
    user_input="What are the latest biomarkers related to longevity?",
    user_id="demo-user-123",
    session_id=None,
    enable_streaming=False,
)

print(result)
```

## Project Structure

- `chat_agent/app.py` — Simple entrypoint/server glue (if applicable) to run and demonstrate the agent.
- `chat_agent/graph.py` — Builds the LangGraph workflow of the agent (nodes, edges, routing). Exposes `run_chat_agent` for normal or streaming execution.
- `chat_agent/graph_state.py` — Defines the `ChatAgentState` type shared across nodes.
- `chat_agent/llm.py` — Thin wrapper for your LLM provider with methods used by the agent (e.g., classification, general answers).
- `chat_agent/models.py` — Pydantic models for structured inputs/outputs (e.g., `RouterOutput`, `ChatHistory`).
- `chat_agent/prompts.py` — Prompt templates and in-README examples of the routing decisions the model should produce.
- `chat_agent/tools.py` — Domain tool functions invoked by the agent (e.g., `longevity_clinical_trial_tool`, `aging_biomarker_tool`).
- `chat_agent/utils.py` — Utilities such as parsing/sanitizing LLM JSON outputs and compacting chat history.
- `chat_agent/db_helper.py` — Minimal persistence helpers to fetch/save chat messages for a user session.
- `chat_agent/logger.py` — Logger configuration used throughout the project.

## The Core Idea: Route-to-Tools

Many chat experiences need to decide whether a query should be handled by:

- A general knowledge response (LLM answer)
- A specialized tool (domain function)
- A rejection flow (guardrails)

This project demonstrates a single-pass classification step that yields a structured routing decision the rest of the system follows.

## End-to-End Flow

1. User sends `user_input` along with a `user_id` (and optional `session_id`).
2. The agent fetches chat history for additional context.
3. The LLM classifies the request into a route using a compact prompt and returns structured JSON.
4. The graph dispatches to one of:
   - `longevity_clinical_trial_node` → calls `longevity_clinical_trial_tool`
   - `aging_biomarker_node` → calls `aging_biomarker_tool`
   - `general_knowledge_node` → calls `llm.answer_general`
   - `rejection_handler` → returns a safe, predefined message
5. The final answer is saved to the chat history, and optionally streamed to the client.

### Why chat history matters for routing

Routing is context-sensitive. The classifier sees a compacted version of prior turns so it can:

- Resolve pronouns and references in follow-ups (e.g., "What about those trials?" → clinical trials tool).
- Maintain user intent and constraints gathered earlier (e.g., location, preferences).
- Avoid misrouting when a short user message depends on prior context.

`get_chat_history` retrieves prior messages and `create_compact_chat_history` reduces them to an LLM-friendly string. This gives the router enough context without overloading the prompt.

## Graph Architecture (`chat_agent/graph.py`)

The agent is implemented as a LangGraph StateGraph:

- Nodes are pure Python functions that accept and return a `ChatAgentState` dict.
- The graph wires nodes together with edges and conditional edges.
- Two execution modes:
  - Normal: compute and return a final state dict.
  - Streaming: yield step-by-step updates for a responsive UI.

Key nodes:

- `get_chat_history`
  - Loads prior messages from persistence via `db_helper.fetch_chat_history`.
  - Converts to a compact history string via `utils.create_compact_chat_history` for LLM consumption.

- `classify_and_route`
  - Calls `llm.decide_route(user_input, chat_history)`.
  - Expects a JSON object matching `RouterOutput`.
  - On success, sets `state["route"]` which drives the subsequent conditional edge.

- `longevity_clinical_trial_node`
  - Streams a status update via `get_stream_writer()`.
  - Calls tool `longevity_clinical_trial_tool(user_input, user_id)`.
  - Sets `final_answer` or records an error.

- `aging_biomarker_node`
  - Same pattern as above, but calls `aging_biomarker_tool`.

- `general_knowledge_node`
  - Calls `llm.answer_general(user_input)` without tools.

- `rejection_handler`
  - Uses `state["rejection_message"]` from classification if present.

- `save_chat_history`
  - Persists both the user’s question and the assistant’s final response.

- `stream_final_response`
  - Only used when `enable_streaming=True` to stream the final payload.

## Routing: From Prompt to RouterOutput

- The LLM returns JSON similar to the examples in `prompts.py`:

```json
{
  "decision": "aging_biomarker_tool",
  "reasoning": "Requesting specific information about biomarkers linked to aging and longevity"
}
```

- The string may come wrapped in Markdown fences or contain minor formatting issues. `utils.parse_routing_decision` strips fences and sanitizes JSON.
- To be robust against minor formatting mistakes (like trailing commas), the code sanitizes the JSON and retries parsing.
- Parsed data is validated against the Pydantic model `RouterOutput`.

`RouterOutput` carries:

- `decision`: which path to take.
- `reasoning`: model’s rationale (useful for logging and debugging).
- `rejection_message`: optional, used by `rejection_handler`.
- `error`: optional, if parsing/validation failed.

## Why deterministic routing vs. generic tool-calling

Many frameworks provide generic tool-calling (e.g., auto tool selection based solely on a function list). This is a deterministic, single-step classifier that emits a strict decision used to pick a node. Benefits:

- Predictability and debuggability — one explicit routing decision with rationale makes runs easy to inspect and log.
- Strong guardrails — you can reject requests up front (e.g., creative writing) before any tool is invoked.
- Better latency and cost control — exactly one routing call and one action path, instead of multi-turn tool-chaining.
- Stable interfaces and testing — nodes and tools have deterministic inputs/outputs that are unit-testable.
- Prompt simplicity — the classifier prompt is short and focused on labels you control.

When to consider generic tool-calling:

- If your problem is inherently open-ended with many interchangeable tools and you’re comfortable with the model deciding dynamically.
- If rapid prototyping matters more than deterministic production behavior.

In many chat applications where reliability, compliance, and observability are priorities, deterministic routing is the safer and more maintainable default.

## Tools: Domain Logic (`chat_agent/tools.py`)

- Tools simulate external APIs or complex logic.
- Each tool:
  - Accepts `user_input` and `user_id`.
  - Returns a dict: `{ "status": "ok" | "error", "response" | "error": ... }`.
  - Tools sleep briefly (to mimic I/O), log progress, and return a stubbed response string.

Tip: Keep tool interfaces simple and deterministic. They’re easy to test and mock.

## Streaming UI Hooks

Nodes emit progress via `get_stream_writer()`:

```python
writer = get_stream_writer()
writer({
    "CurrentStep": "Researching information using aging_biomarker_tool",
    "Response": {}
})
```

Your server or frontend can subscribe to these events to show live updates.

### Why streaming matters

Some tools (API calls, retrieval, long computations) take seconds to complete. Streaming:

- Provides immediate feedback that work is in progress (better UX, reduced abandonment).
- Allows progressive disclosure of intermediate steps or partial results.
- Makes debugging and observability easier during development.

This project shows how nodes can push updates via `get_stream_writer()` and how `run_chat_agent(..., enable_streaming=True)` yields a stream suitable for SSE.

## Persistence (`chat_agent/db_helper.py`)

- `fetch_chat_history(user_id, session_id)` returns a structured list of prior messages.
- `persist_chat_history(...)` stores user and assistant messages.
- `create_compact_chat_history` converts the list into a compact text history that’s LLM-friendly.

This approach avoids prompting the LLM with large raw objects and gives you precise control over context.

## Error Handling and Robustness

- Node-level `try/except` captures and records errors in `state["error"]`.
- Routing JSON is sanitized to handle common issues like trailing commas.
- Name collisions between node and tool names are avoided by using distinct node names (`*_node`).
- Final response always includes an error list so clients can inspect failures.

## Running the Agent

Programmatic usage:

```python
from chat_agent.graph import run_chat_agent

out = run_chat_agent(
    user_input="What does telomere shortening mean in aging?",
    user_id="u-42",
    session_id=None,
    enable_streaming=False,
)

print(out)
# Example result:
# {
#   "answer": "...",
#   "session_id": "...",
#   "error": []
# }
```

Streaming usage (server-sent events style):

```python
from chat_agent.graph import run_chat_agent

stream = run_chat_agent(
    user_input="Find me clinical trials for NAD+ boosters in aging research",
    user_id="u-42",
    session_id=None,
    enable_streaming=True,
)

for chunk in stream:
    print(chunk)  # yields incremental JSON lines like: data: {"CurrentStep": ..., "Response": {...}}
```

## Adapting the Classifier Prompt

- `prompts.py` contains inlined examples of the desired routing outputs.
- Teach the LLM with few-shot examples that map user phrasing → route labels.
- Keep labels stable and wire them to graph nodes via `build_graph()`.

If you add a new route, update:

1. `prompts.py` with examples
2. `models.RouterOutput` (if needed)
3. `graph.build_graph()` conditional edges
4. A new node and tool function (or reuse `general_knowledge_node`)

## Extending the Agent

- Add a new tool:
  1. Implement `chat_agent/tools.py` function `my_new_tool(user_input, user_id)`.
  2. Create a node `my_new_tool_node(state)` that calls it and sets `final_answer`.
  3. Update `build_graph()` to register the node and wire conditional edges.
  4. Provide few-shot examples in `prompts.py` so the classifier can route to it.

- Swap LLMs or providers:
  - Edit `chat_agent/llm.py` to point to your provider and model.
  - Keep the `decide_route` and `answer_general` method signatures stable.

- Change storage:
  - Replace `db_helper` methods with your database of choice (Postgres, Redis, etc.) as long as signatures stay the same.

## Troubleshooting

- Routing JSON parse error
  - Symptom: `parse_routing_decision Error: Expecting property name...`
  - Fix: Already mitigated with a sanitizer in `utils.parse_routing_decision` for trailing commas and code fences.

- Node calls wrong function or recursion error
  - Ensure node names differ from tool function names (`*_node` pattern).
  - If importing tools directly, verify you’re calling the tool, not the node.

- No chat history available
  - The agent continues with an empty history; verify your `user_id` and `session_id`.

- Nothing streams in streaming mode
  - Confirm `enable_streaming=True` and that your server forwards `graph.stream(...)` chunks to the client.

## Design Principles

- Clear separation of concerns between routing (LLM), orchestration (graph), domain logic (tools), and I/O (db/logger/streaming).
- Strong typing with Pydantic models for structured LLM I/O.
- Small, composable nodes that are easy to test.
- Deterministic tools with explicit inputs/outputs.
- Minimal but resilient JSON parsing utilities to tame LLM outputs.

## License

MIT (or your chosen license).
