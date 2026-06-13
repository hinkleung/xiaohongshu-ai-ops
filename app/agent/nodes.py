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


async def theme_analyzer_node(state: AgentState, quick_llm, db) -> dict:
    """Node 1: Analyze theme -> style, keywords, audience."""
    logger.info("Node 1 theme_analyzer: theme=%r", state.get("theme", "")[:80])
    prompt = THEME_ANALYZER_PROMPT.format(theme=state["theme"])
    resp = quick_llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content)
    return {"theme_analysis": json.loads(content)}


async def content_generator_node(state: AgentState, quick_llm, db) -> dict:
    """Node 2: Generate initial post draft."""
    logger.info("Node 2 content_generator: generating draft")
    analysis = state.get("theme_analysis", {})
    prompt = CONTENT_GENERATOR_PROMPT.format(
        theme=state["theme"],
        style=analysis.get("style", "真实分享"),
        keywords=", ".join(analysis.get("keywords", [])),
        tone_notes=analysis.get("tone_notes", "真实车主视角"),
    )
    resp = quick_llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    return {"draft_content": content}


async def ai_detector_node(state: AgentState, deep_llm, db) -> dict:
    """Node 3: Detect AI traces in generated content."""
    logger.info("Node 3 ai_detector: scanning for AI traces")
    prompt = AI_DETECTOR_PROMPT.format(content=state["draft_content"])
    resp = deep_llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
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
    resp = deep_llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    return {"humanized_content": content}


async def xhs_optimizer_node(state: AgentState, deep_llm, db) -> dict:
    """Node 5: Enforce XHS platform rules."""
    logger.info("Node 5 xhs_optimizer: applying platform rules")
    source = state.get("humanized_content") or state["draft_content"]
    title, body, _ = parse_generated_content(source)
    prompt = XHS_OPTIMIZER_PROMPT.format(content=source, title_len=len(title), body_len=len(body))
    resp = deep_llm.invoke(prompt)
    content = resp.content if hasattr(resp, 'content') else str(resp)
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content)
    result = json.loads(content)
    return {
        "final_title": result["title"],
        "final_content": result["body"],
        "final_tags": result["tags"],
        "warnings": result.get("warnings", []),
    }


async def save_draft_node(state: AgentState, llm, db) -> dict:
    """Node 6: Persist draft to SQLite."""
    logger.info("Node 6 save_draft: persisting to DB")
    post = Post(
        title=state.get("final_title", ""),
        content=state.get("final_content", ""),
        status="draft",
        theme=state["theme"],
        ai_provider=state["ai_provider"],
    )
    post.set_tags(state.get("final_tags", []))
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

    async with XHSClient(base_url=MCP_BASE_URL) as client:
        try:
            result = await client.publish_content(
                title=title, content=content, images=images, tags=tags,
            )
            if post:
                post.status = "published"
                post.xhs_feed_id = result.get("feed_id", "")
                post.xhs_note_url = result.get("note_url", "")
                post.publish_time = datetime.utcnow()
                db.commit()
            return {"error": None}
        except Exception as e:
            if post:
                post.status = "failed"
                db.commit()
            return {"error": str(e)}
