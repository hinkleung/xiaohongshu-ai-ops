import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.db import SessionLocal
from app.schemas import GenerateRequest
from app.agent.graph import AgentRunner

router = APIRouter(prefix="/api/agent", tags=["Agent"])


def _get_runner():
    return AgentRunner(db_session_factory=SessionLocal)


@router.post("/generate")
async def trigger_generate(req: GenerateRequest, request: Request):
    runner = _get_runner()

    async def event_stream():
        async for event in runner.run_generate(
            theme=req.theme, images=req.images, ai_provider=req.ai_provider or "",
        ):
            if await request.is_disconnected():
                break
            yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_stream())


@router.post("/{post_id}/publish")
async def trigger_publish(post_id: int):
    runner = _get_runner()
    result = await runner.run_publish(post_id)
    if result.get("error"):
        return {"success": False, "error": result["error"]}
    return {"success": True}


@router.post("/{post_id}/regenerate")
async def trigger_regenerate(post_id: int, request: Request):
    from app.models import Post
    db = SessionLocal()
    try:
        post = db.query(Post).get(post_id)
        if not post:
            return {"error": "Post not found"}
        runner = _get_runner()

        async def event_stream():
            async for event in runner.run_generate(
                theme=post.theme or "", images=post.get_images(),
                ai_provider=post.ai_provider or "",
            ):
                if await request.is_disconnected():
                    break
                yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}

        return EventSourceResponse(event_stream())
    finally:
        db.close()
