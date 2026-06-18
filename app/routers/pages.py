from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post, AIConfig

router = APIRouter(tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")
templates.env.cache = None
# Free Jinja2's {{ }} for Vue — Jinja2 uses << >> for variables instead
templates.env.variable_start_string = "<<"
templates.env.variable_end_string = ">>"


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    configs = [{"id": c.id, "provider": c.provider, "is_active": c.is_active} for c in db.query(AIConfig).all()]
    return templates.TemplateResponse(request, "index.html", {"request": request, "configs": configs})


@router.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request, db: Session = Depends(get_db)):
    posts = []
    for p in db.query(Post).order_by(Post.updated_at.desc()).all():
        posts.append({
            "id": p.id, "title": p.title, "content": p.content,
            "tags": p.get_tags(), "images": p.get_images(),
            "status": p.status, "xhs_feed_id": p.xhs_feed_id,
            "xhs_note_url": p.xhs_note_url, "error_message": p.error_message,
            "activity_description": p.activity_description,
            "theme": p.theme, "ai_provider": p.ai_provider,
            "publish_time": p.publish_time.isoformat() if p.publish_time else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return templates.TemplateResponse(request, "posts.html", {"request": request, "posts": posts})


@router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    post_dict = None
    if post:
        post_dict = {
            "id": post.id, "title": post.title, "content": post.content,
            "tags": post.get_tags(), "images": post.get_images(),
            "status": post.status, "xhs_feed_id": post.xhs_feed_id,
            "xhs_note_url": post.xhs_note_url, "error_message": post.error_message,
            "activity_description": post.activity_description,
            "theme": post.theme, "ai_provider": post.ai_provider,
            "publish_time": post.publish_time.isoformat() if post.publish_time else None,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        }
    return templates.TemplateResponse(request, "post_detail.html", {"request": request, "post": post_dict})


@router.get("/generate/{run_id}", response_class=HTMLResponse)
async def generate_page(run_id: str, request: Request):
    return templates.TemplateResponse(request, "generate.html", {"request": request})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    configs = [{"id": c.id, "provider": c.provider, "is_active": c.is_active,
                "model": c.model, "api_base": c.api_base}
               for c in db.query(AIConfig).order_by(AIConfig.created_at.asc()).all()]
    return templates.TemplateResponse(request, "settings.html", {"request": request, "configs": configs})
