import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from app.db import Base


class AIConfig(Base):
    __tablename__ = "ai_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)
    api_key = Column(Text, nullable=False)           # Fernet encrypted
    api_base = Column(Text, nullable=True)           # custom endpoint
    quick_model = Column(String(100), nullable=False)
    deep_model = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def model(self) -> str:
        return self.quick_model


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    tags = Column(Text, default="[]")                # JSON array
    images = Column(Text, default="[]")              # JSON array
    status = Column(String(20), nullable=False, default="draft")
    xhs_feed_id = Column(String(100), nullable=True)
    xhs_note_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)  # publish failure reason
    activity_description = Column(Text, nullable=True)  # original activity brief (can be long)
    theme = Column(Text, nullable=True)
    ai_provider = Column(String(50), nullable=True)
    publish_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_tags(self) -> list[str]:
        return json.loads(self.tags or "[]")

    def set_tags(self, tags: list[str]):
        self.tags = json.dumps(tags, ensure_ascii=False)

    def get_images(self) -> list[str]:
        return json.loads(self.images or "[]")

    def set_images(self, images: list[str]):
        self.images = json.dumps(images, ensure_ascii=False)


class GenerationHistory(Base):
    __tablename__ = "generation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    node = Column(String(50), nullable=False)
    input_state = Column(Text, default="{}")         # JSON snapshot
    output_state = Column(Text, default="{}")        # JSON snapshot
    ai_provider = Column(String(50), nullable=True)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
