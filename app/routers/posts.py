from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post
from app.schemas import PostCreate, PostUpdate, PostResponse

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
    return [_post_to_response(p) for p in q.all()]


@router.post("", response_model=PostResponse, status_code=201)
def create_post(data: PostCreate, db: Session = Depends(get_db)):
    post = Post(title=data.title, content=data.content, theme=data.theme, status="draft")
    post.set_tags(data.tags)
    post.set_images(data.images)
    db.add(post)
    db.commit()
    db.refresh(post)
    return _post_to_response(post)


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
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
    return _post_to_response(post)


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    db.delete(post)
    db.commit()
