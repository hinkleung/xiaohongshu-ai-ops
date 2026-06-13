import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post
from app.schemas import PostCreate, PostUpdate, PostResponse

logger = logging.getLogger("app.posts")
router = APIRouter(prefix="/api/posts", tags=["Posts"])


def _post_to_response(p: Post) -> PostResponse:
    return PostResponse(
        id=p.id, title=p.title, content=p.content,
        tags=p.get_tags(), images=p.get_images(),
        status=p.status, xhs_feed_id=p.xhs_feed_id,
        xhs_note_url=p.xhs_note_url, theme=p.theme,
        ai_provider=p.ai_provider, publish_time=p.publish_time,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@router.get("", response_model=list[PostResponse])
def list_posts(status: str = Query(None), theme: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Post).order_by(Post.updated_at.desc())
    if status:
        q = q.filter(Post.status == status)
    if theme:
        q = q.filter(Post.theme.contains(theme))
    result = [_post_to_response(p) for p in q.all()]
    logger.debug("List posts status=%r theme=%r → %d results", status, theme, len(result))
    return result


@router.post("", response_model=PostResponse, status_code=201)
def create_post(data: PostCreate, db: Session = Depends(get_db)):
    post = Post(title=data.title, content=data.content, theme=data.theme, status="draft")
    post.set_tags(data.tags)
    post.set_images(data.images)
    db.add(post)
    db.commit()
    db.refresh(post)
    logger.info("Post %d created theme=%r", post.id, post.theme)
    return _post_to_response(post)


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        logger.warning("Post %d not found", post_id)
        raise HTTPException(404, "Post not found")
    return _post_to_response(post)


@router.put("/{post_id}", response_model=PostResponse)
def update_post(post_id: int, data: PostUpdate, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    for field in ("title", "content", "theme"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(post, field, val)
    if data.tags is not None:
        post.set_tags(data.tags)
    if data.images is not None:
        post.set_images(data.images)
    db.commit()
    db.refresh(post)
    logger.info("Post %d updated", post_id)
    return _post_to_response(post)


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    db.delete(post)
    db.commit()
    logger.info("Post %d deleted", post_id)


@router.post("/sync-publishing")
async def sync_publishing_status(db: Session = Depends(get_db)):
    """Cross-check all 'publishing' posts against MCP feed list.
    Called passively when the user opens the posts list page."""
    publishing = db.query(Post).filter(Post.status == "publishing").all()
    if not publishing:
        return {"updated": 0}

    from app.services.xhs_client import XHSClient
    from app.config import XHS_MCP_URL
    from datetime import datetime as dt, timezone

    updated = 0
    try:
        async with XHSClient(base_url=XHS_MCP_URL) as client:
            raw = await client.get_my_profile()
            profile = raw.get("data", raw) if isinstance(raw, dict) else {}
            feeds = profile.get("feeds") or []
            feed_titles = {}
            for f in feeds:
                card = (f.get("noteCard") or {}) if isinstance(f, dict) else {}
                t = card.get("displayTitle", "")
                if t:
                    feed_titles[t] = f.get("id")

            for post in publishing:
                feed_id = feed_titles.get(post.title or "")
                if feed_id:
                    post.status = "published"
                    post.xhs_feed_id = feed_id
                    post.xhs_note_url = f"https://www.xiaohongshu.com/explore/{feed_id}"
                    post.publish_time = dt.now(timezone.utc)
                    logger.info("Passive sync: post %d '%s' → published, feed_id=%s", post.id, post.title, feed_id)
                    updated += 1
                else:
                    logger.debug("Passive sync: post %d '%s' still not found in MCP feed list", post.id, post.title)

        if updated:
            db.commit()
    except Exception as e:
        logger.warning("Passive sync failed (MCP unreachable?): %s", e)

    return {"updated": updated}
