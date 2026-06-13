import logging
import sys
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db import init_db, get_db
from app.models import Post

# ── Logging setup ──────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%m-%d %H:%M:%S",
    stream=sys.stdout,
)
# Silence noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger("app")

app = FastAPI(title="小红书 AI 运营平台", version="1.0.0")

templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# Routers
from app.routers import posts, configs, xhs, agent, pages
app.include_router(posts.router)
app.include_router(configs.router)
app.include_router(xhs.router)
app.include_router(agent.router)
app.include_router(pages.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every HTTP request with method, path, status, and duration."""
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    dt = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info("%s %s → %s (%.0fms)", request.method, request.url.path, response.status_code, dt)
    return response


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_drafts = db.query(Post).filter(Post.status == "draft").count()
    total_published = db.query(Post).filter(Post.status == "published").count()
    this_month = db.query(Post).filter(
        Post.status == "published",
        Post.publish_time >= datetime.now(timezone.utc).replace(day=1),
    ).count()
    return {"drafts": total_drafts, "published": total_published, "this_month": this_month}


@app.on_event("startup")
def on_startup():
    from app.config import DATABASE_PATH as db_path, XHS_MCP_URL as mcp_url
    logger.info("──── Starting 小红书 AI 运营平台 ────")
    logger.info("DB path: %s", db_path)
    logger.info("MCP URL: %s", mcp_url)
    init_db()
    logger.info("DB initialized, app ready")
