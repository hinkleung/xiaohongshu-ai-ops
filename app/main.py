from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from app.db import init_db, get_db
from app.models import Post

app = FastAPI(title="小红书 AI 运营平台", version="1.0.0")

templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# Routers
from app.routers import posts, configs, xhs, agent, pages
app.include_router(posts.router)
app.include_router(configs.router)
app.include_router(xhs.router)
app.include_router(agent.router)
app.include_router(pages.router)


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_drafts = db.query(Post).filter(Post.status == "draft").count()
    total_published = db.query(Post).filter(Post.status == "published").count()
    this_month = db.query(Post).filter(
        Post.status == "published",
        Post.publish_time >= datetime.utcnow().replace(day=1),
    ).count()
    return {"drafts": total_drafts, "published": total_published, "this_month": this_month}


@app.on_event("startup")
def on_startup():
    init_db()
