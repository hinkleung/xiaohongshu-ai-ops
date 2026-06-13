import json
import logging
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.db import SessionLocal
from app.schemas import GenerateRequest
from app.agent.graph import AgentRunner

logger = logging.getLogger("app.agent")
router = APIRouter(prefix="/api/agent", tags=["Agent"])


def _get_runner():
    return AgentRunner(db_session_factory=SessionLocal)


@router.post("/generate")
async def trigger_generate(req: GenerateRequest, request: Request):
    logger.info("Agent generate started — theme=%r provider=%r", req.theme, req.ai_provider)
    runner = _get_runner()

    async def event_stream():
        async for event in runner.run_generate(
            theme=req.theme, images=req.images, ai_provider=req.ai_provider or "",
        ):
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break
            if event.get("status") == "error":
                logger.error("Agent node %s failed: %s", event.get("node"), event.get("message"))
            yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}
        logger.info("Agent generate stream ended")

    return EventSourceResponse(event_stream())


@router.post("/{post_id}/publish")
async def trigger_publish(post_id: int):
    logger.info("Publish requested for post %s", post_id)
    runner = _get_runner()
    result = await runner.run_publish(post_id)
    if result.get("error"):
        logger.error("Publish post %s failed: %s", post_id, result["error"])
        return {"success": False, "error": result["error"]}
    logger.info("Post %s published successfully", post_id)
    return {"success": True}


@router.post("/{post_id}/regenerate")
async def trigger_regenerate(post_id: int, request: Request):
    logger.info("Regenerate requested for post %s", post_id)
    from app.models import Post
    db = SessionLocal()
    try:
        post = db.query(Post).get(post_id)
        if not post:
            logger.warning("Regenerate: post %s not found", post_id)
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
