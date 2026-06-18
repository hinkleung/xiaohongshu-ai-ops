from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AIConfigCreate(BaseModel):
    provider: str = Field(..., pattern="^(claude|openai|deepseek)$")
    api_key: str
    api_base: Optional[str] = None
    model: str  # single model used for all agent nodes


class AIConfigUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None


class AIConfigResponse(BaseModel):
    id: int
    provider: str
    api_base: Optional[str] = None
    model: str  # merged field — same value stored in quick_model & deep_model
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
    activity_description: Optional[str] = None


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[str]] = None
    theme: Optional[str] = None
    activity_description: Optional[str] = None


class PostResponse(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    tags: list[str] = []
    images: list[str] = []
    status: str
    xhs_feed_id: Optional[str] = None
    xhs_note_url: Optional[str] = None
    error_message: Optional[str] = None
    activity_description: Optional[str] = None
    theme: Optional[str] = None
    ai_provider: Optional[str] = None
    publish_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    theme: str
    activity_description: Optional[str] = None  # long raw activity brief
    images: list[str] = []
    ai_provider: Optional[str] = None   # auto-select active if None


class GenerateEvent(BaseModel):
    node: str
    status: str          # running / done / error
    message: str
    data: Optional[dict] = None
