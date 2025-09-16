# apps/routers/chat.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..models import ChatRequest, ChatResponse
from ..services import llm
import json
router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/completions", response_model=ChatResponse)
async def create_completion(req: ChatRequest):
    try:
        user_msgs = [m.model_dump() for m in req.messages]
        output, citations = await llm.generate(user_msgs, req.temperature)
        return ChatResponse(output=output, citations=citations)
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

@router.post("/stream")
async def stream_chat(req: ChatRequest):
    user_msgs = [m.model_dump() for m in req.messages]

    async def gen():
        try:
            # upstream(OPENAI)에서 429 등 에러면 여기서 잡아서 SSE로 내려줌
            async for chunk in llm.chat_stream(
                [{"role": "system", "content": "You are a helpful assistant."}] + user_msgs,
                temperature=req.temperature
            ):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield "data: [DONE]\n\n"

        except HTTPException as e:
            msg = e.detail if isinstance(e.detail, str) else str(e.detail)
            yield f"data: {json.dumps({'error': msg, 'status': e.status_code})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'status': 500})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

