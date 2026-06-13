from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post, AIConfig

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")
templates.env.cache = None


def _config_to_dict(c: AIConfig) -> dict:
    return {
        "id": c.id, "provider": c.provider, "api_base": c.api_base,
        "quick_model": c.quick_model, "deep_model": c.deep_model,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _post_to_dict(p: Post) -> dict:
    return {
        "id": p.id, "title": p.title, "content": p.content,
        "tags": p.get_tags(), "images": p.get_images(),
        "status": p.status, "xhs_feed_id": p.xhs_feed_id,
        "xhs_note_url": p.xhs_note_url, "theme": p.theme,
        "ai_provider": p.ai_provider,
        "publish_time": p.publish_time.isoformat() if p.publish_time else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    configs = [_config_to_dict(c) for c in db.query(AIConfig).all()]
    return templates.TemplateResponse(request, "index.html", {"configs": configs})


@router.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request, db: Session = Depends(get_db)):
    posts = [_post_to_dict(p) for p in db.query(Post).order_by(Post.updated_at.desc()).all()]
    return templates.TemplateResponse(request, "posts.html", {"posts": posts})


@router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        return HTMLResponse("Post not found", status_code=404)
    return templates.TemplateResponse(request, "post_detail.html", {"post": _post_to_dict(post)})


@router.get("/generate/{run_id}", response_class=HTMLResponse)
async def generate_page(run_id: str, request: Request):
    return templates.TemplateResponse(request, "generate.html", {"run_id": run_id})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    configs = [_config_to_dict(c) for c in db.query(AIConfig).all()]
    return templates.TemplateResponse(request, "settings.html", {"configs": configs})
