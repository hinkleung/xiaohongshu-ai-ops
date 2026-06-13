from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AIConfigCreate(BaseModel):
    provider: str = Field(..., pattern="^(claude|openai|deepseek)$")
    api_key: str
    api_base: Optional[str] = None
    quick_model: str
    deep_model: str


class AIConfigUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    quick_model: Optional[str] = None
    deep_model: Optional[str] = None
    is_active: Optional[bool] = None


class AIConfigResponse(BaseModel):
    id: int
    provider: str
    api_base: Optional[str] = None
    quick_model: str
    deep_model: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: list[str] = []
    images: list[str] = []
    theme: Optional[str] = None


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[str]] = None
    theme: Optional[str] = None


class PostResponse(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    tags: list[str] = []
    images: list[str] = []
    status: str
    xhs_feed_id: Optional[str] = None
    xhs_note_url: Optional[str] = None
    theme: Optional[str] = None
    ai_provider: Optional[str] = None
    publish_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    theme: str
    images: list[str] = []
    ai_provider: Optional[str] = None   # auto-select active if None


class GenerateEvent(BaseModel):
    node: str
    status: str          # running / done / error
    message: str
    data: Optional[dict] = None
