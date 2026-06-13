import asyncio
import json
import logging
import re
from datetime import datetime
from app.agent.state import AgentState
from app.agent.prompts import (
    THEME_ANALYZER_PROMPT, CONTENT_GENERATOR_PROMPT,
    AI_DETECTOR_PROMPT, HUMANIZER_PROMPT, XHS_OPTIMIZER_PROMPT,
)
from app.models import Post

logger = logging.getLogger("app.agent.nodes")


def parse_generated_content(text: str) -> tuple[str, str, list[str]]:
    """Parse AI output into (title, body, tags)."""
    lines = text.strip().split("\n")
    title = ""
    body_lines = []
    tags = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if not title and not s.startswith("#") and len(s) <= 30:
            title = s
        elif s.startswith("#"):
            for part in s.split("#"):
                tag = part.strip()
                if tag:
                    tags.append(tag)
        else:
            body_lines.append(s)
    return title, "\n".join(body_lines), tags


async def _call_llm(llm, prompt: str, node_name: str) -> str:
    """Call LLM and validate response is non-empty."""
    resp = llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    if not content or not content.strip():
        raise ValueError(f"[{node_name}] LLM returned empty response — check API key / model availability")
    return content.strip()


async def theme_analyzer_node(state: AgentState, quick_llm, db) -> dict:
    """Node 1: Analyze theme -> style, keywords, audience."""
    logger.info("Node 1 theme_analyzer: theme=%r", state.get("theme", "")[:80])
    prompt = THEME_ANALYZER_PROMPT.format(theme=state["theme"])
    content = await _call_llm(quick_llm, prompt, "theme_analyzer")
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    return {"theme_analysis": json.loads(content)}


async def content_generator_node(state: AgentState, quick_llm, db) -> dict:
    """Node 2: Generate initial post draft."""
    logger.info("Node 2 content_generator: generating draft")
    analysis = state.get("theme_analysis", {})
    prompt = CONTENT_GENERATOR_PROMPT.format(
        theme=state["theme"],
        style=analysis.get("style") or "真实分享",
        keywords=", ".join(analysis.get("keywords") or []),
        tone_notes=analysis.get("tone_notes") or "真实车主视角",
    )
    content = await _call_llm(quick_llm, prompt, "content_generator")
    return {"draft_content": content}


async def ai_detector_node(state: AgentState, deep_llm, db) -> dict:
    """Node 3: Detect AI traces in generated content."""
    logger.info("Node 3 ai_detector: scanning for AI traces")
    prompt = AI_DETECTOR_PROMPT.format(content=state["draft_content"])
    content = await _call_llm(deep_llm, prompt, "ai_detector")
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    result = json.loads(content)
    return {
        "flagged_sections": result.get("flagged_sections", []),
        "needs_humanization": result.get("has_ai_traces", False),
    }


async def humanizer_node(state: AgentState, deep_llm, db) -> dict:
    """Node 4: Rewrite AI-sounding sections to sound human."""
    logger.info("Node 4 humanizer: rewriting flagged sections")
    prompt = HUMANIZER_PROMPT.format(
        content=state["draft_content"],
        flagged_sections=json.dumps(state.get("flagged_sections", []), ensure_ascii=False),
    )
    content = await _call_llm(deep_llm, prompt, "humanizer")
    return {"humanized_content": content}


async def xhs_optimizer_node(state: AgentState, deep_llm, db) -> dict:
    """Node 5: Enforce XHS platform rules."""
    logger.info("Node 5 xhs_optimizer: applying platform rules")
    source = state.get("humanized_content") or state["draft_content"]
    title, body, _ = parse_generated_content(source)
    prompt = XHS_OPTIMIZER_PROMPT.format(content=source, title_len=len(title), body_len=len(body))
    content = await _call_llm(deep_llm, prompt, "xhs_optimizer")
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    result = json.loads(content)
    return {
        "final_title": result.get("title") or title or "",
        "final_content": result.get("body") or source,
        "final_tags": result.get("tags") or (parse_generated_content(source)[2]),
        "warnings": result.get("warnings", []),
    }


async def save_draft_node(state: AgentState, llm, db) -> dict:
    """Node 6: Persist draft to SQLite."""
    logger.info("Node 6 save_draft: persisting to DB")

    # Fallback chain: final → humanized → draft — prevent empty saves
    final_content = state.get("final_content") or state.get("humanized_content") or state.get("draft_content", "")
    final_title = state.get("final_title") or ""
    final_tags = state.get("final_tags") or []

    # If content is still raw (optimizer produced nothing useful), parse it ourselves
    if not final_title or not final_tags:
        parsed_title, _, parsed_tags = parse_generated_content(final_content)
        if not final_title:
            final_title = parsed_title or state.get("theme", "")[:20]
        if not final_tags:
            final_tags = parsed_tags

    logger.info("save_draft: title=%r content_len=%d tags=%d", final_title[:40], len(final_content), len(final_tags))

    post = Post(
        title=final_title,
        content=final_content,
        status="draft",
        theme=state["theme"],
        ai_provider=state["ai_provider"],
    )
    post.set_tags(final_tags)
    post.set_images(state["images"])
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"checkpoint_id": str(post.id)}


async def publisher_node(state: AgentState, llm, db) -> dict:
    """Node 7: Publish to Xiaohongshu via MCP."""
    logger.info("Node 7 publisher: publishing to XHS")
    from app.services.xhs_client import XHSClient
    from app.agent.tools import MCP_BASE_URL

    post_id = state.get("checkpoint_id")
    post = db.query(Post).get(int(post_id)) if post_id else None

    title = state.get("final_title", "")
    content = state.get("final_content", "")
    tags = state.get("final_tags", [])
    images = state["images"]

    # Xiaohongshu requires at least 1 image — hard MCP constraint (min=1)
    if not images:
        error_msg = "小红书发布至少需要 1 张图片，请先在文章编辑页面上传图片"
        logger.warning("Publish blocked: no images for post %s", post_id)
        if post:
            post.status = "failed"
            db.commit()
        return {"error": error_msg}

    async with XHSClient(base_url=MCP_BASE_URL) as client:
        try:
            await client.publish_content(
                title=title, content=content, images=images, tags=tags,
            )
            # MCP returned HTTP 200, but browser automation may have
            # failed silently — verify the note actually appears in the feed
            # with staggered intervals: 10s → 30s → 60s (total ~1m40s).
            feed_id = None
            note_url = None
            delays = [10, 30, 60]
            for attempt, delay in enumerate(delays):
                await asyncio.sleep(delay)
                try:
                    raw = await client.get_my_profile()
                    profile = raw.get("data", raw) if isinstance(raw, dict) else {}
                    feeds = profile.get("feeds") or []
                    for f in feeds:
                        card = (f.get("noteCard") or {}) if isinstance(f, dict) else {}
                        if card.get("displayTitle") == title:
                            feed_id = f.get("id")
                            if feed_id:
                                note_url = f"https://www.xiaohongshu.com/explore/{feed_id}"
                            break
                    if feed_id:
                        logger.info("Publish verified on attempt %d: feed_id=%s", attempt + 1, feed_id)
                        break
                except Exception:
                    logger.warning("Feed verification attempt %d/%d failed", attempt + 1, len(delays))

            if not feed_id:
                logger.error("Publish verification failed: note '%s' not found in feed after %d attempts", title, len(delays))
                if post:
                    post.status = "failed"
                    db.commit()
                return {"error": "发布验证失败：在笔记列表中未找到已发布的笔记（已等待 %d 秒），可能被小红书拦截或账号异常" % sum(delays)}

            if post:
                post.status = "published"
                post.xhs_feed_id = feed_id
                post.xhs_note_url = note_url or ""
                post.publish_time = datetime.utcnow()
                db.commit()
            return {"error": None}

        except Exception as e:
            # Try to extract MCP error details from the response
            err_msg = str(e)
            if hasattr(e, 'response'):
                try:
                    body = e.response.json()
                    err_msg = body.get("details") or body.get("error") or err_msg
                except Exception:
                    pass
            logger.error("MCP publish threw exception: %s", err_msg)
            if post:
                post.status = "failed"
                db.commit()
            return {"error": f"发布失败：{err_msg}"}
