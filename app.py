from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from chat_agent.graph import run_chat_agent
from chat_agent.models import ChatAIRequest
from chat_agent.logger import logger

load_dotenv()

app = FastAPI(title="Longevity Chat Agent")

#example request
# {
#   "user_query": "What are the latest biomarkers related to longevity?",
#   "user_id": "test@company.com",
#   "session_id": "8e89e5a8-9ed9-4ddc-a840-7e8e2999e2ce",
#   "enable_streaming": true
# }

@app.post("/chat_ai/agent")
async def chat_with_ai_agent(request: ChatAIRequest = Body(...)):
    try:
        if not request.user_query or request.user_query.strip() == "":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "USER_QUERY_NOT_PROVIDED",
                        "message": "Please provide a valid user query.",
                    }
                },
            )

        if not request.user_id or request.user_id.strip() == "":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "USER_ID_NOT_PROVIDED",
                        "message": "Please provide a valid user id.",
                    }
                },
            )

        if request.enable_streaming:
            return StreamingResponse(
                run_chat_agent(request.user_query, request.user_id, request.session_id, True),
                status_code=200,
                media_type="text/event-stream",
            )
        else:
            response = run_chat_agent(request.user_query, request.user_id, request.session_id, False)
            if response.get("error"):
                return JSONResponse(status_code=400, content={"error": response.get("error")})
            return JSONResponse(status_code=200, content=response)
    except Exception as e:
        # On error, respond with JSON even if streaming was requested.
        logger.exception("Unhandled exception in /chat_ai/agent")
        return JSONResponse(status_code=500, content={"error": str(e)})
