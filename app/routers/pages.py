from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post, AIConfig

router = APIRouter(tags=["Pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    configs = db.query(AIConfig).all()
    return request.app.state.templates.TemplateResponse("index.html", {
        "request": request, "configs": configs,
    })


@router.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request, db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.updated_at.desc()).all()
    return request.app.state.templates.TemplateResponse("posts.html", {
        "request": request, "posts": posts,
    })


@router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        return HTMLResponse("Post not found", status_code=404)
    return request.app.state.templates.TemplateResponse("post_detail.html", {
        "request": request, "post": post,
    })


@router.get("/generate/{run_id}", response_class=HTMLResponse)
async def generate_page(run_id: str, request: Request):
    return request.app.state.templates.TemplateResponse("generate.html", {
        "request": request, "run_id": run_id,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    configs = db.query(AIConfig).all()
    return request.app.state.templates.TemplateResponse("settings.html", {
        "request": request, "configs": configs,
    })
