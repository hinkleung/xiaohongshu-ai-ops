import json
import logging
import asyncio
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.db import SessionLocal
from app.models import Post
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
            activity_description=req.activity_description or "",
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
    """Start async publish — sets status to 'publishing', returns immediately."""
    logger.info("Publish requested for post %s", post_id)
    db = SessionLocal()
    try:
        post = db.query(Post).get(post_id)
        if not post:
            return {"success": False, "error": "Post not found"}
        if post.status == "publishing":
            logger.info("Re-publish requested while publishing — allowing retry")
        post.status = "publishing"
        db.commit()
    finally:
        db.close()

    # Fire-and-forget background publish
    asyncio.create_task(_background_publish(post_id))

    return {"success": True, "message": "发布任务已提交", "status": "publishing"}


async def _background_publish(post_id: int):
    """Background task: run publish via MCP, then update post status."""
    logger.info("Background publish started for post %s", post_id)
    runner = _get_runner()
    result = await runner.run_publish(post_id)

    db = SessionLocal()
    try:
        post = db.query(Post).get(post_id)
        if not post:
            logger.warning("Background publish: post %s vanished", post_id)
            return
        if result.get("error"):
            post.status = "failed"
            post.error_message = result["error"]
            logger.error("Background publish post %s failed: %s", post_id, result["error"])
        else:
            post.status = "published"
            logger.info("Background publish post %s succeeded", post_id)
        db.commit()
    finally:
        db.close()


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
                activity_description=post.activity_description or "",
            ):
                if await request.is_disconnected():
                    break
                yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}

        return EventSourceResponse(event_stream())
    finally:
        db.close()
