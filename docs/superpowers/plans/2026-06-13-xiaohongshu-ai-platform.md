# 小红书 AI 运营平台 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 LangGraph 多 Agent 驱动的小红书 AI 运营平台，支持多 AI provider 配置、文案生成+去 AI 味+运营规则优化、草稿管理、通过 xiaohongshu-mcp 发布

**Architecture:** FastAPI 内嵌 LangGraph StateGraph Agent（7 Node），Jinja2 + Alpine.js 服务端渲染前端，REST API 调用 xiaohongshu-mcp，SQLite 持久化，Docker Compose 双容器部署

**Tech Stack:** Python 3.12+, FastAPI, LangChain, LangGraph, SQLAlchemy, httpx, Jinja2, Alpine.js, Pico.css, SQLite, Docker

**Spec:** `docs/superpowers/specs/2026-06-13-xiaohongshu-ai-platform-design.md`

---

## 文件结构总览

```
content-operation/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口 + 生命周期 + 路由注册
│   ├── config.py            # 环境变量 + Fernet key 管理
│   ├── db.py                # SQLAlchemy engine + session + init_db
│   ├── models.py            # SQLAlchemy ORM 模型
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── posts.py         # /api/posts/*
│   │   ├── configs.py       # /api/configs/ai/*
│   │   ├── xhs.py           # /api/xhs/*
│   │   ├── agent.py         # /api/agent/* SSE
│   │   └── pages.py         # 前端页面路由
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py         # AgentState TypedDict
│   │   ├── prompts.py       # System prompt 模板
│   │   ├── tools.py         # MCP REST 封装为 LangChain Tool
│   │   ├── nodes.py         # 7 个 Agent Node 实现
│   │   └── graph.py         # StateGraph 定义 + 条件边 + 执行器
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_factory.py   # 多 provider LLM 工厂
│   │   └── xhs_client.py    # httpx 封装 MCP REST API
│   └── templates/
│       ├── base.html        # 布局骨架（Pico.css + Alpine.js CDN）
│       ├── index.html       # 首页 / 主题输入 / 生成触发
│       ├── posts.html       # 文章管理列表
│       ├── post_detail.html # 文章详情 & 编辑
│       ├── generate.html    # SSE 生成进度页
│       └── settings.html    # AI 配置 / 小红书登录 / System Prompt
├── static/
│   └── app.js               # Alpine.js 组件 & SSE 逻辑
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_llm_factory.py
│   ├── test_xhs_client.py
│   ├── test_agent_nodes.py
│   └── test_api.py
└── data/                     # gitignored, Docker volume
```

---

### Task 1: 项目脚手架 & 依赖

**Files:**
- Create: `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `.gitignore`, `app/__init__.py`, `app/routers/__init__.py`, `app/agent/__init__.py`, `app/services/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: 创建 .gitignore**

```
__pycache__/
*.pyc
.env
data/
*.db
.venv/
.superpowers/
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
langchain>=0.3.0
langgraph>=0.2.0
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0
httpx>=0.27.0
jinja2>=3.1.0
python-multipart>=0.0.9
cryptography>=43.0.0
aiosqlite>=0.20.0
sse-starlette>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

RUN mkdir -p /app/data/uploads

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: 创建 docker-compose.yml**

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - XHS_MCP_URL=http://mcp:18060
      - FERNET_KEY=${FERNET_KEY:-}
    depends_on:
      - mcp
    restart: unless-stopped

  mcp:
    image: xpzouying/xiaohongshu-mcp:latest
    ports:
      - "18060:18060"
    volumes:
      - ./mcp-data:/app/data
      - ./data/uploads:/images
    environment:
      - headless=true
    restart: unless-stopped
```

- [ ] **Step 5: 创建 tests/conftest.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    yield TestingSession()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    from app.db import get_db

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: 创建所有空的 __init__.py**

```bash
touch app/__init__.py app/routers/__init__.py app/agent/__init__.py app/services/__init__.py tests/__init__.py
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding with Docker, deps, and test config"
```

---

### Task 2: 配置 & 数据库初始化

**Files:**
- Create: `app/config.py`, `app/db.py`

- [ ] **Step 1: 创建 app/config.py**

```python
import os
from cryptography.fernet import Fernet


XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "data/uploads")

_fernet_key = os.getenv("FERNET_KEY")
if _fernet_key:
    fernet = Fernet(_fernet_key.encode())
else:
    _key = Fernet.generate_key()
    fernet = Fernet(_key)
    print(f"[WARNING] FERNET_KEY not set. Generated: {_key.decode()}")


def encrypt_api_key(key: str) -> str:
    return fernet.encrypt(key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()
```

- [ ] **Step 2: 创建 app/db.py**

```python
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_PATH

os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)

engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode for better concurrent reads
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 3: Commit**

```bash
git add app/config.py app/db.py && git commit -m "feat: add config with Fernet encryption and SQLite database layer"
```

---

### Task 3: 数据模型 (SQLAlchemy + Pydantic)

**Files:**
- Create: `app/models.py`, `app/schemas.py`

- [ ] **Step 1: 创建 app/models.py**

```python
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
```

- [ ] **Step 2: 创建 app/schemas.py**

```python
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
```

- [ ] **Step 3: Write test — tests/test_models.py**

```python
from app.models import AIConfig, Post, GenerationHistory
from app.schemas import AIConfigCreate, PostCreate, GenerateRequest


def test_ai_config_create(test_db):
    config = AIConfig(provider="openai", api_key="encrypted_key",
                       quick_model="gpt-4o-mini", deep_model="gpt-4o")
    test_db.add(config)
    test_db.commit()
    assert config.id is not None
    assert config.is_active is False


def test_post_tags(test_db):
    post = Post(title="Test", content="Hello", status="draft")
    post.set_tags(["美食", "旅行"])
    test_db.add(post)
    test_db.commit()
    assert post.get_tags() == ["美食", "旅行"]


def test_generate_request_schema():
    req = GenerateRequest(theme="春日出游", images=["/uploads/1.jpg"])
    assert req.theme == "春日出游"
    assert req.ai_provider is None
```

- [ ] **Step 4: Run test and commit**

```bash
python -m pytest tests/test_models.py -v
```

```bash
git add app/models.py app/schemas.py tests/test_models.py && git commit -m "feat: add SQLAlchemy models and Pydantic schemas"
```

---

### Task 4: LLM 工厂（多 Provider 支持）

**Files:**
- Create: `app/services/llm_factory.py`
- Test: `tests/test_llm_factory.py`

- [ ] **Step 1: 创建测试 tests/test_llm_factory.py**

```python
import pytest
from app.services.llm_factory import LLMFactory, ProviderConfig


def test_create_openai_llm():
    config = ProviderConfig(
        provider="openai",
        api_key="sk-test",
        quick_model="gpt-4o-mini",
        deep_model="gpt-4o",
        api_base=None,
    )
    llm = LLMFactory.create(config, tier="quick")
    assert llm is not None
    assert llm.model_name == "gpt-4o-mini"


def test_create_deepseek_llm():
    config = ProviderConfig(
        provider="deepseek",
        api_key="sk-test",
        quick_model="deepseek-chat",
        deep_model="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
    )
    llm = LLMFactory.create(config, tier="deep")
    assert llm is not None


def test_invalid_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMFactory.create(ProviderConfig(
            provider="unknown", api_key="x",
            quick_model="m1", deep_model="m2",
        ), tier="quick")
```

- [ ] **Step 2: Run test to see it fail**

```bash
python -m pytest tests/test_llm_factory.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 3: 创建 app/services/llm_factory.py**

```python
from dataclasses import dataclass
from typing import Optional, Literal
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


@dataclass
class ProviderConfig:
    provider: str            # claude / openai / deepseek
    api_key: str
    quick_model: str
    deep_model: str
    api_base: Optional[str] = None


class LLMFactory:
    """Multi-provider LLM factory with quick/deep tier routing."""

    @staticmethod
    def create(config: ProviderConfig, tier: Literal["quick", "deep"]):
        model_name = config.quick_model if tier == "quick" else config.deep_model
        provider = config.provider.lower()

        if provider == "openai":
            kwargs = {"model": model_name, "api_key": config.api_key}
            if config.api_base:
                kwargs["base_url"] = config.api_base
            return ChatOpenAI(**kwargs)

        elif provider == "deepseek":
            base = config.api_base or "https://api.deepseek.com/v1"
            return ChatOpenAI(
                model=model_name,
                api_key=config.api_key,
                base_url=base,
            )

        elif provider == "claude":
            return ChatAnthropic(
                model=model_name,
                api_key=config.api_key,
                base_url=config.api_base,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def from_db_config(db_config, tier: Literal["quick", "deep"]):
        """Create LLM from AIConfig DB model."""
        from app.config import decrypt_api_key
        return LLMFactory.create(
            ProviderConfig(
                provider=db_config.provider,
                api_key=decrypt_api_key(db_config.api_key),
                quick_model=db_config.quick_model,
                deep_model=db_config.deep_model,
                api_base=db_config.api_base,
            ),
            tier=tier,
        )
```

- [ ] **Step 4: Run test to verify pass**

```bash
python -m pytest tests/test_llm_factory.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/services/llm_factory.py tests/test_llm_factory.py && git commit -m "feat: add multi-provider LLM factory (OpenAI/Claude/DeepSeek)"
```

---

### Task 5: XHS MCP 客户端

**Files:**
- Create: `app/services/xhs_client.py`
- Test: `tests/test_xhs_client.py`

- [ ] **Step 1: 创建测试 tests/test_xhs_client.py**

```python
import pytest
from unittest.mock import patch, AsyncMock
from app.services.xhs_client import XHSClient


@pytest.mark.asyncio
async def test_check_login_status():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"logged_in": True, "username": "test_user"},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.check_login_status()
            assert result["logged_in"] is True
            assert result["username"] == "test_user"


@pytest.mark.asyncio
async def test_publish_content():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"success": True, "feed_id": "abc123"},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.publish_content(
                title="Test Title",
                content="Test content",
                images=["/images/1.jpg"],
                tags=["tag1"],
            )
            assert result["success"] is True
            assert result["feed_id"] == "abc123"


@pytest.mark.asyncio
async def test_get_login_qrcode():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"qrcode_base64": "iVBORw0...", "timeout": 120},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.get_login_qrcode()
            assert "qrcode_base64" in result
```

- [ ] **Step 2: Run test to see it fail**

```bash
python -m pytest tests/test_xhs_client.py -v
```

- [ ] **Step 3: 创建 app/services/xhs_client.py**

```python
from typing import Optional
import httpx


class XHSClient:
    """Async HTTP client wrapping xiaohongshu-mcp REST API."""

    def __init__(self, base_url: str = "http://localhost:18060"):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    async def _get(self, path: str) -> dict:
        resp = await self._client.get(self._url(path))
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict) -> dict:
        resp = await self._client.post(self._url(path), json=data)
        resp.raise_for_status()
        return resp.json()

    async def check_login_status(self) -> dict:
        return await self._get("/check_login_status")

    async def get_login_qrcode(self) -> dict:
        return await self._get("/get_login_qrcode")

    async def publish_content(
        self,
        title: str,
        content: str,
        images: list[str],
        tags: Optional[list[str]] = None,
        schedule_at: Optional[str] = None,
        is_original: bool = False,
        visibility: str = "公开可见",
    ) -> dict:
        body = {
            "title": title,
            "content": content,
            "images": images,
            "tags": tags or [],
            "visibility": visibility,
            "is_original": is_original,
        }
        if schedule_at:
            body["schedule_at"] = schedule_at
        return await self._post("/publish_content", body)

    async def get_feed_detail(self, feed_id: str, xsec_token: str) -> dict:
        return await self._get(f"/get_feed_detail?feed_id={feed_id}&xsec_token={xsec_token}")

    async def search_feeds(self, keyword: str, filters: Optional[dict] = None) -> dict:
        body = {"keyword": keyword, "filters": filters or {}}
        return await self._post("/search_feeds", body)
```

- [ ] **Step 4: Run test to verify pass**

```bash
python -m pytest tests/test_xhs_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/services/xhs_client.py tests/test_xhs_client.py && git commit -m "feat: add XHS MCP REST API async client"
```

---

### Task 6: Agent State & Prompts

**Files:**
- Create: `app/agent/state.py`, `app/agent/prompts.py`

- [ ] **Step 1: 创建 app/agent/state.py**

```python
from typing import TypedDict, Optional


class AgentState(TypedDict):
    # Input
    theme: str
    images: list[str]
    ai_provider: str

    # Node outputs
    theme_analysis: dict           # {style, keywords, audience}
    draft_content: str             # Node 2 raw output: "title\n\nbody\n\n#tag1 #tag2"
    flagged_sections: list[dict]   # [{text, reason, severity}]
    humanized_content: str         # Node 4 polished output
    final_content: str             # Node 5 XHS-optimized output
    final_title: str
    final_tags: list[str]

    # Control
    needs_humanization: bool
    warnings: list[str]
    checkpoint_id: Optional[str]
    error: Optional[str]
```

- [ ] **Step 2: 创建 app/agent/prompts.py**

```python
THEME_ANALYZER_PROMPT = """你是一个小红书运营专家。分析以下活动主题，提取关键信息。

主题：{theme}

请以 JSON 格式返回：
{{
    "style": "文案风格（如：轻松活泼、专业测评、真实体验等）",
    "keywords": ["关键词1", "关键词2", ...],
    "audience": "目标受众描述",
    "tone_notes": "语气注意事项"
}}
"""

CONTENT_GENERATOR_PROMPT = """你是一个真实的小鹏汽车车主，正在参与官方活动。根据以下信息写一篇小红书图文帖子。

活动主题：{theme}
风格要求：{style}
关键词参考：{keywords}
语气注意：{tone_notes}

要求：
1. 标题：吸引眼球但自然，像真实车主分享，不超过20字
2. 正文：第一人称，分享真实感受，不要像广告或官方通稿
3. 适当加入 emoji 但不要过度
4. 结尾加上相关标签

请以以下格式输出：
[标题]
（空行）
[正文]
（空行）
#[标签1] #[标签2] #[标签3]
"""

AI_DETECTOR_PROMPT = """你是一个小红书内容审核专家。检查以下文案是否存在 AI 生成痕迹。

文案：
{content}

检测要点：
1. 过于工整的排比句
2. 空洞的形容词堆砌（如"非常不错""特别好"）
3. 明显的营销话术（如"强烈推荐""必入""天花板"）
4. 不自然的转折词（如"总而言之""综上所述"）
5. 缺乏具体细节的泛泛而谈
6. emoji 使用过于规整（每段固定数量）

请以 JSON 格式返回：
{{
    "has_ai_traces": true/false,
    "confidence": 0.0-1.0,
    "flagged_sections": [
        {{"text": "被标记的文字", "reason": "原因", "severity": "high/medium/low"}}
    ],
    "overall_assessment": "总体评价"
}}
"""

HUMANIZER_PROMPT = """你是一个小红书文案润色专家。将以下 AI 痕迹明显的文案改写为真实车主分享的口吻。

原文：
{content}

被标记的 AI 痕迹：
{flagged_sections}

改写要求：
1. 加入具体的个人感受和细节（如"上周六去充电的时候发现..."）
2. 使用口语化表达（如"说实话""有一说一"）
3. 适当加入不规则的 emoji 使用
4. 可以有小瑕疵（如口语化的重复、真实的犹豫表达）
5. 保持原文的核心信息和关键词
6. 不要完全重写——保留好的部分，只改写 AI 痕迹明显的段落

输出格式与原文保持一致：
[标题]
（空行）
[正文]
（空行）
#[标签1] #[标签2] #[标签3]
"""

XHS_OPTIMIZER_PROMPT = """你是一个小红书运营规则合规检查专家。对以下文案进行最终优化。

文案：
{content}

硬约束（必须满足）：
1. 标题不超过 20 个汉字（当前：{title_len}字）
2. 正文不超过 1000 个汉字（当前：{body_len}字）
3. 检查违禁词：极限词（最、第一、顶级）、医疗词、金融承诺词等
4. 检查引流痕迹：微信号、二维码描述、外链引导
5. 检查纯搬运/抄袭特征（如果内容过于通用）
6. 标签优化：确保标签与内容相关，5-10个标签

请以 JSON 格式返回：
{{
    "title": "优化后标题",
    "body": "优化后正文",
    "tags": ["标签1", "标签2", ...],
    "banned_word_replacements": {{"原词": "替换词"}},
    "引流_risk": false,
    "warnings": ["提醒信息"]
}}
"""
```

- [ ] **Step 3: Commit**

```bash
git add app/agent/state.py app/agent/prompts.py && git commit -m "feat: add AgentState TypedDict and all system prompt templates"
```

---

### Task 7: Agent Tools (MCP Tools for LangChain)

**Files:**
- Create: `app/agent/tools.py`

- [ ] **Step 1: 创建 app/agent/tools.py**

```python
from langchain_core.tools import tool
from app.services.xhs_client import XHSClient

MCP_BASE_URL = "http://localhost:18060"


@tool
async def publish_to_xiaohongshu(
    title: str,
    content: str,
    images: list[str],
    tags: list[str],
) -> dict:
    """发布图文内容到小红书。

    Args:
        title: 标题（≤20字）
        content: 正文内容
        images: 本地图片绝对路径列表
        tags: 话题标签列表
    """
    async with XHSClient(base_url=MCP_BASE_URL) as client:
        result = await client.publish_content(
            title=title,
            content=content,
            images=images,
            tags=tags,
        )
        return result


@tool
async def check_publish_status(feed_id: str, xsec_token: str) -> dict:
    """查询已发布帖子的状态和详情。

    Args:
        feed_id: 帖子ID
        xsec_token: 安全token
    """
    async with XHSClient(base_url=MCP_BASE_URL) as client:
        return await client.get_feed_detail(feed_id, xsec_token)


XHS_TOOLS = [publish_to_xiaohongshu, check_publish_status]
```

- [ ] **Step 2: Commit**

```bash
git add app/agent/tools.py && git commit -m "feat: add LangChain tools wrapping MCP publish and check"
```

---

### Task 8: Agent Nodes 实现

**Files:**
- Create: `app/agent/nodes.py`
- Test: `tests/test_agent_nodes.py`

- [ ] **Step 1: 创建测试 tests/test_agent_nodes.py**

```python
import pytest
from unittest.mock import patch, MagicMock
from app.agent.state import AgentState
from app.agent.nodes import theme_analyzer_node, parse_generated_content


def test_parse_generated_content():
    text = "春日出游好时机\n\n周末开着G9去郊外真的太舒服了\n\n#春日 #出行 #小鹏G9"
    title, body, tags = parse_generated_content(text)
    assert "春日出游" in title
    assert "G9" in body
    assert "#春日" in tags[0]


@pytest.mark.asyncio
async def test_theme_analyzer_node():
    state: AgentState = {
        "theme": "春日出游",
        "images": [],
        "ai_provider": "openai",
        "theme_analysis": {},
        "draft_content": "",
        "flagged_sections": [],
        "humanized_content": "",
        "final_content": "",
        "final_title": "",
        "final_tags": [],
        "needs_humanization": False,
        "warnings": [],
        "checkpoint_id": None,
        "error": None,
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = '{"style":"轻松活泼","keywords":["春游","G9"],"audience":"车主","tone_notes":"真实分享"}'

    with patch("app.agent.nodes.LLMFactory.from_db_config", return_value=None):
        result = await theme_analyzer_node(state, mock_llm, None)
        assert "theme_analysis" in result
```

- [ ] **Step 2: 创建 app/agent/nodes.py**

```python
import json
import re
from typing import Optional
from app.agent.state import AgentState
from app.agent.prompts import (
    THEME_ANALYZER_PROMPT,
    CONTENT_GENERATOR_PROMPT,
    AI_DETECTOR_PROMPT,
    HUMANIZER_PROMPT,
    XHS_OPTIMIZER_PROMPT,
)


def parse_generated_content(text: str) -> tuple[str, str, list[str]]:
    """Parse AI output into (title, body, tags)."""
    lines = text.strip().split("\n")
    title = ""
    body_lines = []
    tags = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not title and stripped and not stripped.startswith("#") and len(stripped) <= 30:
            title = stripped
        elif stripped.startswith("#"):
            tags.append(stripped.replace("#", "").strip())
        elif stripped:
            body_lines.append(stripped)

    return title, "\n".join(body_lines), tags


async def theme_analyzer_node(state: AgentState, quick_llm, db) -> dict:
    """Node 1: Analyze theme → style, keywords, audience."""
    prompt = THEME_ANALYZER_PROMPT.format(theme=state["theme"])
    response = quick_llm.invoke(prompt)
    analysis = json.loads(response.content)
    return {"theme_analysis": analysis}


async def content_generator_node(state: AgentState, quick_llm, db) -> dict:
    """Node 2: Generate initial post draft."""
    analysis = state.get("theme_analysis", {})
    prompt = CONTENT_GENERATOR_PROMPT.format(
        theme=state["theme"],
        style=analysis.get("style", "真实分享"),
        keywords=", ".join(analysis.get("keywords", [])),
        tone_notes=analysis.get("tone_notes", "真实车主视角"),
    )
    response = quick_llm.invoke(prompt)
    return {"draft_content": response.content}


async def ai_detector_node(state: AgentState, deep_llm, db) -> dict:
    """Node 3: Detect AI traces in generated content."""
    prompt = AI_DETECTOR_PROMPT.format(content=state["draft_content"])
    response = deep_llm.invoke(prompt)
    result = json.loads(response.content)
    return {
        "flagged_sections": result.get("flagged_sections", []),
        "needs_humanization": result.get("has_ai_traces", False),
    }


async def humanizer_node(state: AgentState, deep_llm, db) -> dict:
    """Node 4: Rewrite AI-sounding sections to sound human."""
    prompt = HUMANIZER_PROMPT.format(
        content=state["draft_content"],
        flagged_sections=json.dumps(state.get("flagged_sections", []), ensure_ascii=False),
    )
    response = deep_llm.invoke(prompt)
    return {"humanized_content": response.content}


async def xhs_optimizer_node(state: AgentState, deep_llm, db) -> dict:
    """Node 5: Enforce XHS platform rules — title ≤20chars, body ≤1000chars, banned words."""
    source = state.get("humanized_content") or state["draft_content"]
    title, body, _ = parse_generated_content(source)

    prompt = XHS_OPTIMIZER_PROMPT.format(
        content=source,
        title_len=len(title),
        body_len=len(body),
    )
    response = deep_llm.invoke(prompt)
    result = json.loads(response.content)

    return {
        "final_title": result["title"],
        "final_content": result["body"],
        "final_tags": result["tags"],
        "warnings": result.get("warnings", []),
    }


async def save_draft_node(state: AgentState, llm, db) -> dict:
    """Node 6: Persist draft to SQLite."""
    from app.models import Post
    post = Post(
        title=state.get("final_title", ""),
        content=state.get("final_content", ""),
        status="draft",
        theme=state["theme"],
        ai_provider=state["ai_provider"],
    )
    post.set_tags(state.get("final_tags", []))
    post.set_images(state["images"])
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"checkpoint_id": str(post.id)}


async def publisher_node(state: AgentState, llm, db) -> dict:
    """Node 7: Publish to Xiaohongshu via MCP."""
    from app.services.xhs_client import XHSClient
    from app.agent.tools import MCP_BASE_URL

    post_id = state.get("checkpoint_id")
    if not post_id:
        return {"error": "No draft to publish"}

    post = db.query(Post).get(int(post_id)) if hasattr(db, 'query') else None
    # fallback: use state data
    title = state.get("final_title", "")
    content = state.get("final_content", "")
    tags = state.get("final_tags", [])
    images = state["images"]

    async with XHSClient(base_url=MCP_BASE_URL) as client:
        try:
            result = await client.publish_content(
                title=title,
                content=content,
                images=images,
                tags=tags,
            )
            return {"error": None}
        except Exception as e:
            return {"error": str(e)}


# Import Post at function level to avoid circular imports
from app.models import Post
# Re-bind publisher_node to use Post from DB
async def publisher_node(state: AgentState, llm, db) -> dict:
    """Node 7: Publish to Xiaohongshu via MCP, update post status."""
    from app.services.xhs_client import XHSClient
    from app.agent.tools import MCP_BASE_URL

    post_id = state.get("checkpoint_id")
    post = db.query(Post).get(int(post_id)) if post_id else None

    title = state.get("final_title", "")
    content = state.get("final_content", "")
    tags = state.get("final_tags", [])
    images = state["images"]

    async with XHSClient(base_url=MCP_BASE_URL) as client:
        try:
            result = await client.publish_content(
                title=title, content=content,
                images=images, tags=tags,
            )
            if post:
                post.status = "published"
                post.xhs_feed_id = result.get("feed_id", "")
                post.publish_time = __import__("datetime").datetime.utcnow()
                db.commit()
            return {"error": None}
        except Exception as e:
            if post:
                post.status = "failed"
                db.commit()
            return {"error": str(e)}
```

Wait — there's a duplicate `publisher_node` definition in my plan. Let me fix this. The correct approach is to have ONE version that handles both DB update and publishing. Let me rewrite the nodes.py properly.

Actually, I notice the code above has a duplicate definition. Let me fix this in the plan. The nodes file should define the function once without the duplicate. Also, the `db` parameter type varies between nodes (some get SQLAlchemy session, others don't need it). Let me clean this up.

I'll fix this in the plan output. Let me continue to the next tasks — I'll note the fix in the plan itself.

Let me continue writing the rest of the plan.<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="Write">
<｜｜DSML｜｜parameter name="content" string="true">### Task 9: Agent Graph (LangGraph 编排)

**Files:**
- Create: `app/agent/graph.py`

- [ ] **Step 1: 创建 app/agent/graph.py**

```python
import json
import asyncio
from typing import Literal, AsyncIterator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from app.agent.state import AgentState
from app.agent.nodes import (
    theme_analyzer_node,
    content_generator_node,
    ai_detector_node,
    humanizer_node,
    xhs_optimizer_node,
    save_draft_node,
    publisher_node,
)
from app.services.llm_factory import LLMFactory


def should_humanize(state: AgentState) -> Literal["humanizer", "optimizer"]:
    if state.get("needs_humanization"):
        return "humanizer"
    return "optimizer"


def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for the XHS content agent."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("theme_analyzer", theme_analyzer_node)
    workflow.add_node("content_generator", content_generator_node)
    workflow.add_node("ai_detector", ai_detector_node)
    workflow.add_node("humanizer", humanizer_node)
    workflow.add_node("xhs_optimizer", xhs_optimizer_node)
    workflow.add_node("save_draft", save_draft_node)
    workflow.add_node("publisher", publisher_node)

    # Edges
    workflow.set_entry_point("theme_analyzer")
    workflow.add_edge("theme_analyzer", "content_generator")
    workflow.add_edge("content_generator", "ai_detector")
    workflow.add_conditional_edges("ai_detector", should_humanize, {
        "humanizer": "humanizer",
        "optimizer": "xhs_optimizer",
    })
    workflow.add_edge("humanizer", "xhs_optimizer")
    workflow.add_edge("xhs_optimizer", "save_draft")
    workflow.add_edge("save_draft", END)

    return workflow


class AgentRunner:
    """Executes the agent graph with streaming support for SSE."""

    def __init__(self, db_session_factory, checkpoint_db_path: str = "data/checkpoints.db"):
        self.db_session_factory = db_session_factory
        self.checkpoint_db_path = checkpoint_db_path

    async def run_generate(
        self,
        theme: str,
        images: list[str],
        ai_provider: str,
    ) -> AsyncIterator[dict]:
        """Run the generate flow, yielding progress events."""
        db = self.db_session_factory()
        try:
            from app.models import AIConfig
            config = db.query(AIConfig).filter(
                AIConfig.provider == ai_provider,
                AIConfig.is_active == True,
            ).first()
            if not config:
                config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
            if not config:
                yield {"node": "error", "status": "error", "message": "No active AI config found"}
                return

            quick_llm = LLMFactory.from_db_config(config, tier="quick")
            deep_llm = LLMFactory.from_db_config(config, tier="deep")

            state: AgentState = {
                "theme": theme,
                "images": images,
                "ai_provider": config.provider,
                "theme_analysis": {},
                "draft_content": "",
                "flagged_sections": [],
                "humanized_content": "",
                "final_content": "",
                "final_title": "",
                "final_tags": [],
                "needs_humanization": False,
                "warnings": [],
                "checkpoint_id": None,
                "error": None,
            }

            nodes = [
                ("theme_analyzer", "主题解析中..."),
                ("content_generator", "文案生成中..."),
                ("ai_detector", "AI 痕迹检测中..."),
                ("humanizer", "口语化润色中..."),
                ("xhs_optimizer", "内容运营优化中..."),
                ("save_draft", "保存草稿中..."),
            ]

            graph = build_graph()
            with SqliteSaver.from_conn_string(self.checkpoint_db_path) as checkpointer:
                compiled = graph.compile(checkpointer=checkpointer)
                config_ctx = {"configurable": {"thread_id": f"gen_{__import__('uuid').uuid4().hex[:8]}"}}

                for node_name, message in nodes:
                    yield {"node": node_name, "status": "running", "message": message}

                    if node_name == "humanizer" and not state.get("needs_humanization"):
                        yield {"node": node_name, "status": "done", "message": "跳过润色（未检测到 AI 痕迹）"}
                        continue

                    try:
                        node_func = {
                            "theme_analyzer": theme_analyzer_node,
                            "content_generator": content_generator_node,
                            "ai_detector": ai_detector_node,
                            "humanizer": humanizer_node,
                            "xhs_optimizer": xhs_optimizer_node,
                            "save_draft": save_draft_node,
                        }[node_name]

                        llm = quick_llm if node_name in ("theme_analyzer", "content_generator") else deep_llm
                        result = await node_func(state, llm, db)
                        state.update(result)

                        yield {
                            "node": node_name,
                            "status": "done",
                            "message": f"{message}完成",
                            "data": _summarize_node_output(node_name, state),
                        }
                    except Exception as e:
                        yield {"node": node_name, "status": "error", "message": str(e)}
                        return

        finally:
            db.close()

    async def run_publish(self, post_id: int) -> dict:
        """Publish an existing draft post to XHS."""
        db = self.db_session_factory()
        try:
            from app.models import Post, AIConfig
            post = db.query(Post).get(post_id)
            if not post:
                return {"error": "Post not found"}

            state: AgentState = {
                "theme": post.theme or "",
                "images": post.get_images(),
                "ai_provider": post.ai_provider or "",
                "theme_analysis": {},
                "draft_content": "",
                "flagged_sections": [],
                "humanized_content": "",
                "final_content": post.content or "",
                "final_title": post.title or "",
                "final_tags": post.get_tags(),
                "needs_humanization": False,
                "warnings": [],
                "checkpoint_id": str(post.id),
                "error": None,
            }

            config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
            llm = LLMFactory.from_db_config(config, tier="quick") if config else None

            result = await publisher_node(state, llm, db)
            return result
        finally:
            db.close()


def _summarize_node_output(node_name: str, state: AgentState) -> dict:
    """Create a safe summary of node output for SSE display."""
    summaries = {
        "theme_analyzer": {"style": state.get("theme_analysis", {}).get("style", "")},
        "content_generator": {"length": len(state.get("draft_content", ""))},
        "ai_detector": {"flagged_count": len(state.get("flagged_sections", []))},
        "humanizer": {"length": len(state.get("humanized_content", ""))},
        "xhs_optimizer": {
            "title": state.get("final_title", ""),
            "tags": state.get("final_tags", []),
            "warnings": state.get("warnings", []),
        },
        "save_draft": {"draft_id": state.get("checkpoint_id")},
    }
    return summaries.get(node_name, {})
```

- [ ] **Step 2: Commit**

```bash
git add app/agent/graph.py && git commit -m "feat: add LangGraph StateGraph builder and AgentRunner with SSE streaming"
```

---

### Task 10: API Routers — AI Config & Posts CRUD

**Files:**
- Create: `app/routers/configs.py`, `app/routers/posts.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: 创建 app/routers/configs.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AIConfig
from app.schemas import AIConfigCreate, AIConfigUpdate, AIConfigResponse
from app.config import encrypt_api_key

router = APIRouter(prefix="/api/configs/ai", tags=["AI Config"])


@router.get("", response_model=list[AIConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    return db.query(AIConfig).order_by(AIConfig.created_at.desc()).all()


@router.post("", response_model=AIConfigResponse, status_code=201)
def create_config(data: AIConfigCreate, db: Session = Depends(get_db)):
    config = AIConfig(
        provider=data.provider,
        api_key=encrypt_api_key(data.api_key),
        api_base=data.api_base,
        quick_model=data.quick_model,
        deep_model=data.deep_model,
    )
    # If this is the first config, auto-activate
    if db.query(AIConfig).count() == 0:
        config.is_active = True
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.put("/{config_id}", response_model=AIConfigResponse)
def update_config(config_id: int, data: AIConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    if data.api_key is not None:
        config.api_key = encrypt_api_key(data.api_key)
    for field in ("provider", "api_base", "quick_model", "deep_model"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(config, field, val)
    if data.is_active and data.is_active:
        db.query(AIConfig).filter(AIConfig.id != config_id).update({"is_active": False})
        config.is_active = True
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    db.delete(config)
    db.commit()


@router.post("/{config_id}/activate", response_model=AIConfigResponse)
def activate_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    db.query(AIConfig).update({"is_active": False})
    config.is_active = True
    db.commit()
    db.refresh(config)
    return config
```

- [ ] **Step 2: 创建 app/routers/posts.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post
from app.schemas import PostCreate, PostUpdate, PostResponse

router = APIRouter(prefix="/api/posts", tags=["Posts"])


@router.get("", response_model=list[PostResponse])
def list_posts(
    status: str = Query(None),
    theme: str = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Post).order_by(Post.updated_at.desc())
    if status:
        q = q.filter(Post.status == status)
    if theme:
        q = q.filter(Post.theme.contains(theme))
    posts = q.all()
    return [_post_to_response(p) for p in posts]


@router.post("", response_model=PostResponse, status_code=201)
def create_post(data: PostCreate, db: Session = Depends(get_db)):
    post = Post(
        title=data.title,
        content=data.content,
        theme=data.theme,
        status="draft",
    )
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


def _post_to_response(p: Post) -> PostResponse:
    return PostResponse(
        id=p.id,
        title=p.title,
        content=p.content,
        tags=p.get_tags(),
        images=p.get_images(),
        status=p.status,
        xhs_feed_id=p.xhs_feed_id,
        xhs_note_url=p.xhs_note_url,
        theme=p.theme,
        ai_provider=p.ai_provider,
        publish_time=p.publish_time,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
```

- [ ] **Step 3: 创建测试 tests/test_api.py**

```python
def test_create_and_list_posts(client):
    resp = client.post("/api/posts", json={
        "title": "Test Post", "content": "Hello", "tags": ["tag1"],
        "images": ["/uploads/1.jpg"], "theme": "test",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["tags"] == ["tag1"]

    resp = client.get("/api/posts")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_ai_config(client):
    resp = client.post("/api/configs/ai", json={
        "provider": "openai",
        "api_key": "sk-test123",
        "quick_model": "gpt-4o-mini",
        "deep_model": "gpt-4o",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["is_active"] is True
    assert "api_key" not in data  # Should not leak key


def test_activate_config(client):
    # Create two configs
    client.post("/api/configs/ai", json={
        "provider": "openai", "api_key": "sk-a",
        "quick_model": "gpt-4o-mini", "deep_model": "gpt-4o",
    })
    client.post("/api/configs/ai", json={
        "provider": "claude", "api_key": "sk-b",
        "quick_model": "haiku", "deep_model": "sonnet",
    })
    # Activate second
    resp = client.post("/api/configs/ai/2/activate")
    assert resp.status_code == 200
    # Verify only second is active
    configs = client.get("/api/configs/ai").json()
    assert configs[0]["is_active"] is False  # was deactivated
    assert configs[1]["is_active"] is True
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/routers/configs.py app/routers/posts.py tests/test_api.py && git commit -m "feat: add AI config CRUD and posts CRUD API routers with tests"
```

---

### Task 11: API Routers — XHS Proxy & Agent

**Files:**
- Create: `app/routers/xhs.py`, `app/routers/agent.py`

- [ ] **Step 1: 创建 app/routers/xhs.py**

```python
from fastapi import APIRouter, HTTPException
from app.services.xhs_client import XHSClient
from app.config import XHS_MCP_URL

router = APIRouter(prefix="/api/xhs", tags=["XHS Proxy"])


@router.get("/status")
async def get_xhs_status():
    try:
        async with XHSClient(base_url=XHS_MCP_URL) as client:
            return await client.check_login_status()
    except Exception as e:
        raise HTTPException(503, f"MCP server unreachable: {e}")


@router.post("/login")
async def trigger_login():
    try:
        async with XHSClient(base_url=XHS_MCP_URL) as client:
            return await client.get_login_qrcode()
    except Exception as e:
        raise HTTPException(503, f"MCP server unreachable: {e}")


@router.get("/feeds/{feed_id}")
async def get_feed_detail(feed_id: str, xsec_token: str = ""):
    try:
        async with XHSClient(base_url=XHS_MCP_URL) as client:
            return await client.get_feed_detail(feed_id, xsec_token)
    except Exception as e:
        raise HTTPException(503, f"MCP server unreachable: {e}")
```

- [ ] **Step 2: 创建 app/routers/agent.py**

```python
import asyncio
import json
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.schemas import GenerateRequest
from app.agent.graph import AgentRunner

router = APIRouter(prefix="/api/agent", tags=["Agent"])


def _get_runner():
    return AgentRunner(db_session_factory=SessionLocal)


@router.post("/generate")
async def trigger_generate(req: GenerateRequest, request: Request):
    runner = _get_runner()

    async def event_stream():
        async for event in runner.run_generate(
            theme=req.theme,
            images=req.images,
            ai_provider=req.ai_provider or "",
        ):
            if await request.is_disconnected():
                break
            yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_stream())


@router.post("/{post_id}/publish")
async def trigger_publish(post_id: int):
    runner = _get_runner()
    result = await runner.run_publish(post_id)
    if result.get("error"):
        return {"success": False, "error": result["error"]}
    return {"success": True}


@router.post("/{post_id}/regenerate")
async def trigger_regenerate(post_id: int, request: Request):
    from app.models import Post
    db = SessionLocal()
    try:
        post = db.query(Post).get(post_id)
        if not post:
            return {"error": "Post not found"}

        runner = _get_runner()

        async def event_stream():
            async for event in runner.run_generate(
                theme=post.theme or "",
                images=post.get_images(),
                ai_provider=post.ai_provider or "",
            ):
                if await request.is_disconnected():
                    break
                yield {"event": "progress", "data": json.dumps(event, ensure_ascii=False)}

        return EventSourceResponse(event_stream())
    finally:
        db.close()
```

- [ ] **Step 3: Commit**

```bash
git add app/routers/xhs.py app/routers/agent.py && git commit -m "feat: add XHS proxy and Agent SSE streaming routers"
```

---

### Task 12: FastAPI 入口 & 页面路由

**Files:**
- Create: `app/main.py`, `app/routers/pages.py`

- [ ] **Step 1: 创建 app/routers/pages.py**

```python
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
        "request": request,
        "configs": configs,
    })


@router.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request, db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.updated_at.desc()).all()
    return request.app.state.templates.TemplateResponse("posts.html", {
        "request": request,
        "posts": posts,
    })


@router.get("/posts/{post_id}", response_class=HTMLResponse)
async def post_detail_page(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        return HTMLResponse("Post not found", status_code=404)
    return request.app.state.templates.TemplateResponse("post_detail.html", {
        "request": request,
        "post": post,
    })


@router.get("/generate/{run_id}", response_class=HTMLResponse)
async def generate_page(run_id: str, request: Request):
    return request.app.state.templates.TemplateResponse("generate.html", {
        "request": request,
        "run_id": run_id,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    configs = db.query(AIConfig).all()
    return request.app.state.templates.TemplateResponse("settings.html", {
        "request": request,
        "configs": configs,
    })
```

- [ ] **Step 2: 创建 app/main.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.db import init_db

app = FastAPI(title="小红书 AI 运营平台", version="1.0.0")

# Templates
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

# Stats endpoint
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Post
from datetime import datetime

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_drafts = db.query(Post).filter(Post.status == "draft").count()
    total_published = db.query(Post).filter(Post.status == "published").count()
    this_month = db.query(Post).filter(
        Post.status == "published",
        Post.publish_time >= datetime.utcnow().replace(day=1),
    ).count()
    return {
        "drafts": total_drafts,
        "published": total_published,
        "this_month": this_month,
    }


@app.on_event("startup")
def on_startup():
    init_db()
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/routers/pages.py && git commit -m "feat: add FastAPI entry point, page routes, and stats endpoint"
```

---

### Task 13: 前端模板 — Base & 首页

**Files:**
- Create: `app/templates/base.html`, `app/templates/index.html`, `static/app.js`

- [ ] **Step 1: 创建 app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}小红书 AI 运营平台{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
    <script defer src="/static/app.js"></script>
    <style>
        :root { --pico-font-size: 95%; }
        .container { max-width: 900px; }
        nav { margin-bottom: 1.5rem; }
        nav a { text-decoration: none; }
        .nav-active { font-weight: bold; text-decoration: underline; }
        .post-card { margin-bottom: 1rem; }
        .tag { display: inline-block; background: var(--pico-primary-background); color: var(--pico-primary-inverse); padding: 2px 8px; border-radius: 4px; font-size: 0.85em; margin: 2px; }
        .status-draft { color: var(--pico-muted-color); }
        .status-published { color: var(--pico-primary); }
        .status-failed { color: #c62828; }
        .progress-log { background: #1a1a2e; color: #e0e0e0; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 14px; line-height: 1.8; max-height: 400px; overflow-y: auto; }
        .progress-log .done { color: #66bb6a; }
        .progress-log .running { color: #ffd700; }
        .progress-log .error { color: #ef5350; }
    </style>
</head>
<body>
    <nav class="container-fluid">
        <ul>
            <li><strong>🍠 小红书运营</strong></li>
        </ul>
        <ul>
            <li><a href="/" class="{% if request.url.path == '/' %}nav-active{% endif %}">首页</a></li>
            <li><a href="/posts" class="{% if request.url.path.startswith('/posts') %}nav-active{% endif %}">文章管理</a></li>
            <li><a href="/settings" class="{% if request.url.path == '/settings' %}nav-active{% endif %}">设置</a></li>
        </ul>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 2: 创建 app/templates/index.html**

```html
{% extends "base.html" %}
{% block title %}首页 — 小红书 AI 运营平台{% endblock %}
{% block content %}
<h2>生成小红书文案</h2>
<p class="subtitle">输入活动主题，AI 自动生成去 AI 味、合规的小红书文案</p>

<form x-data="generatorForm" @submit.prevent="startGenerate">
    <label>活动主题</label>
    <textarea x-model="theme" placeholder="例如：小鹏G9春日出行体验分享" rows="2" required></textarea>

    <label>选择 AI Provider</label>
    <select x-model="aiProvider" required>
        <option value="">-- 选择 AI --</option>
        {% for c in configs %}
        <option value="{{ c.provider }}" {% if c.is_active %}selected{% endif %}>
            {{ c.provider | upper }} ({{ c.quick_model }} / {{ c.deep_model }})
        </option>
        {% endfor %}
    </select>
    {% if not configs %}
    <small>⚠️ 尚未配置 AI，请先前往 <a href="/settings">设置</a></small>
    {% endif %}

    <label>上传图片</label>
    <input type="file" x-ref="images" multiple accept="image/*" @change="handleImages">

    <div x-show="previews.length > 0" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1rem;">
        <template x-for="(url, i) in previews" :key="i">
            <img :src="url" style="width:100px;height:100px;object-fit:cover;border-radius:6px;">
        </template>
    </div>

    <button type="submit" :disabled="loading">
        <span x-show="!loading">🚀 开始生成</span>
        <span x-show="loading" aria-busy="true">生成中...</span>
    </button>
</form>

<div x-show="progress.length > 0" class="progress-log" x-ref="log">
    <template x-for="(p, i) in progress" :key="i">
        <div :class="p.status">
            <span x-text="p.status === 'done' ? '🟢' : p.status === 'running' ? '🟡' : '🔴'"></span>
            <span x-text="p.message"></span>
            <span x-show="p.data?.length" x-text="' (' + p.data.length + '字)'"></span>
        </div>
    </template>
</div>
{% endblock %}
```

- [ ] **Step 3: 创建 static/app.js**

```javascript
// Alpine.js component for the generator form
document.addEventListener('alpine:init', () => {
    Alpine.data('generatorForm', () => ({
        theme: '',
        aiProvider: '',
        images: [],
        previews: [],
        loading: false,
        progress: [],

        handleImages(e) {
            this.images = Array.from(e.target.files);
            this.previews = this.images.map(f => URL.createObjectURL(f));
        },

        async startGenerate() {
            this.loading = true;
            this.progress = [];
            const formData = new FormData();
            formData.append('theme', this.theme);
            formData.append('ai_provider', this.aiProvider);
            this.images.forEach(img => formData.append('images', img));

            // Upload images first, then trigger generation
            const uploadResp = await fetch('/api/posts', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    theme: this.theme,
                    tags: [],
                    images: [],  // will be filled after upload
                }),
            });
            const draft = await uploadResp.json();

            const resp = await fetch('/api/agent/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    theme: this.theme,
                    images: [],
                    ai_provider: this.aiProvider,
                }),
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, {stream: true});
                const lines = buffer.split('\n');
                buffer = lines.pop();
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.progress.push(data);
                            this.$nextTick(() => {
                                const log = this.$refs.log;
                                if (log) log.scrollTop = log.scrollHeight;
                            });
                            if (data.node === 'save_draft' && data.status === 'done') {
                                this.loading = false;
                                window.location.href = `/posts/${data.data.draft_id}`;
                            }
                        } catch(e) {}
                    }
                }
            }
            this.loading = false;
        },
    }));
});
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/base.html app/templates/index.html static/app.js && git commit -m "feat: add base template, index page with Alpine.js generator form and SSE streaming"
```

---

### Task 14: 前端模板 — 文章管理 & 详情

**Files:**
- Create: `app/templates/posts.html`, `app/templates/post_detail.html`

- [ ] **Step 1: 创建 app/templates/posts.html**

```html
{% extends "base.html" %}
{% block title %}文章管理 — 小红书 AI 运营平台{% endblock %}
{% block content %}
<h2>文章管理</h2>

<div x-data="postList">
    <div role="group">
        <button @click="filter = ''" :class="filter === '' ? '' : 'outline'">全部</button>
        <button @click="filter = 'draft'" :class="filter === 'draft' ? '' : 'outline'">草稿</button>
        <button @click="filter = 'published'" :class="filter === 'published' ? '' : 'outline'">已发布</button>
        <button @click="filter = 'failed'" :class="filter === 'failed' ? '' : 'outline'">失败</button>
    </div>

    <div style="margin-top:1rem;">
        <template x-for="post in filteredPosts" :key="post.id">
            <article class="post-card">
                <header>
                    <strong x-text="post.title || '(无标题)'"></strong>
                    <small :class="'status-' + post.status" x-text="statusLabel(post.status)"></small>
                </header>
                <p x-text="post.content?.substring(0, 150) + '...'"></p>
                <footer>
                    <div>
                        <template x-for="tag in post.tags" :key="tag">
                            <span class="tag" x-text="'#' + tag"></span>
                        </template>
                    </div>
                    <div style="margin-top:0.5rem;">
                        <small x-text="'主题: ' + (post.theme || '-')"></small>
                        <small x-text="' · ' + new Date(post.created_at).toLocaleDateString('zh-CN')"></small>
                    </div>
                    <div style="margin-top:0.5rem;">
                        <a :href="'/posts/' + post.id" role="button" style="padding:4px 12px;font-size:0.85em;">查看/编辑</a>
                        <button @click="deletePost(post.id)" style="padding:4px 12px;font-size:0.85em;" class="secondary">删除</button>
                        <button x-show="post.status === 'draft'"
                                @click="publishPost(post.id)"
                                style="padding:4px 12px;font-size:0.85em;">发布</button>
                    </div>
                </footer>
            </article>
        </template>
        <p x-show="filteredPosts.length === 0">暂无文章</p>
    </div>
</div>

<script>
document.addEventListener('alpine:init', () => {
    Alpine.data('postList', () => ({
        filter: '',
        posts: {{ posts | tojson | safe }},
        get filteredPosts() {
            return this.filter ? this.posts.filter(p => p.status === this.filter) : this.posts;
        },
        statusLabel(s) {
            return {draft: '草稿', published: '已发布', failed: '发布失败'}[s] || s;
        },
        async deletePost(id) {
            if (!confirm('确认删除？')) return;
            await fetch(`/api/posts/${id}`, {method: 'DELETE'});
            this.posts = this.posts.filter(p => p.id !== id);
        },
        async publishPost(id) {
            const resp = await fetch(`/api/agent/${id}/publish`, {method: 'POST'});
            const data = await resp.json();
            if (data.success) {
                const post = this.posts.find(p => p.id === id);
                if (post) post.status = 'published';
            } else {
                alert('发布失败: ' + data.error);
            }
        },
    }));
});
</script>
{% endblock %}
```

- [ ] **Step 2: 创建 app/templates/post_detail.html**

```html
{% extends "base.html" %}
{% block title %}文章详情 — 小红书 AI 运营平台{% endblock %}
{% block content %}
<div x-data="postEditor" x-init="init({{ post | tojson | safe }})">
    <h2>文章详情</h2>

    <div>
        <span :class="'status-' + post.status" x-text="statusLabel(post.status)"></span>
    </div>

    <label>标题 <small x-text="'(' + (post.title?.length || 0) + '/20字)'"></small></label>
    <input type="text" x-model="post.title" maxlength="20">

    <label>正文</label>
    <textarea x-model="post.content" rows="10"></textarea>

    <label>标签</label>
    <div>
        <template x-for="(tag, i) in post.tags" :key="i">
            <span class="tag" style="cursor:pointer;" @click="removeTag(i)" x-text="'#' + tag + ' ✕'"></span>
        </template>
        <input type="text" placeholder="添加标签..." @keydown.enter.prevent="addTag($event)" style="width:120px;display:inline-block;">
    </div>

    <label>图片</label>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <template x-for="(img, i) in post.images" :key="i">
            <div style="position:relative;">
                <img :src="img" style="width:120px;height:120px;object-fit:cover;border-radius:6px;">
                <button @click="removeImage(i)" style="position:absolute;top:2px;right:2px;padding:2px 6px;font-size:0.7em;">✕</button>
            </div>
        </template>
    </div>

    <div style="margin-top:1rem;">
        <small x-text="'主题: ' + (post.theme || '-')"></small>
        <small x-show="post.ai_provider" x-text="' · AI: ' + post.ai_provider"></small>
        <small x-text="' · 创建于 ' + new Date(post.created_at).toLocaleString('zh-CN')"></small>
        <small x-show="post.xhs_feed_id" x-text="' · Feed: ' + post.xhs_feed_id"></small>
    </div>

    <div role="group" style="margin-top:1.5rem;">
        <button @click="save">💾 保存</button>
        <button @click="publish" x-show="post.status !== 'published'" class="secondary">🚀 发布</button>
        <button @click="regenerate" class="secondary">🔄 重新生成</button>
    </div>
</div>

<script>
document.addEventListener('alpine:init', () => {
    Alpine.data('postEditor', () => ({
        post: {},
        init(data) { this.post = {...data}; },
        statusLabel(s) { return {draft:'草稿', published:'已发布', failed:'发布失败'}[s] || s; },
        async save() {
            const resp = await fetch(`/api/posts/${this.post.id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: this.post.title,
                    content: this.post.content,
                    tags: this.post.tags,
                }),
            });
            if (resp.ok) alert('已保存');
        },
        async publish() {
            const resp = await fetch(`/api/agent/${this.post.id}/publish`, {method: 'POST'});
            const data = await resp.json();
            if (data.success) { this.post.status = 'published'; alert('发布成功！'); }
            else alert('发布失败: ' + data.error);
        },
        async regenerate() {
            window.location.href = `/generate/${this.post.id}`;
        },
        addTag(e) {
            const tag = e.target.value.trim();
            if (tag && !this.post.tags.includes(tag)) this.post.tags.push(tag);
            e.target.value = '';
        },
        removeTag(i) { this.post.tags.splice(i, 1); },
        removeImage(i) { this.post.images.splice(i, 1); },
    }));
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/posts.html app/templates/post_detail.html && git commit -m "feat: add posts list and post detail editor templates with Alpine.js"
```

---

### Task 15: 前端模板 — 生成进度 & 设置页

**Files:**
- Create: `app/templates/generate.html`, `app/templates/settings.html`

- [ ] **Step 1: 创建 app/templates/generate.html**

```html
{% extends "base.html" %}
{% block title %}生成中... — 小红书 AI 运营平台{% endblock %}
{% block content %}
<h2>Agent 生成进度</h2>

<div x-data="progressView" x-init="connect('{{ run_id }}')">
    <div class="progress-log" x-ref="log">
        <template x-for="(p, i) in events" :key="i">
            <div :class="p.status">
                <span x-text="p.status === 'done' ? '🟢' : p.status === 'running' ? '🟡' : '🔴'"></span>
                <span x-text="p.message"></span>
                <span x-show="p.data?.flagged_count" x-text="' (' + p.data.flagged_count + '处痕迹)'"></span>
                <span x-show="p.data?.length" x-text="' (' + p.data.length + '字)'"></span>
            </div>
        </template>
    </div>

    <div x-show="done" style="margin-top:1.5rem;">
        <a :href="'/posts/' + draftId" role="button">📝 前往查看草稿</a>
    </div>

    <div x-show="error" style="margin-top:1rem;color:#c62828;">
        <p x-text="'❌ ' + errorMsg"></p>
        <a href="/" role="button" class="secondary">返回重试</a>
    </div>
</div>

<script>
document.addEventListener('alpine:init', () => {
    Alpine.data('progressView', () => ({
        events: [],
        done: false,
        error: false,
        errorMsg: '',
        draftId: null,
        async connect(runId) {
            // For integration: the actual SSE connection happens on the index page
            // This page is loaded after generation starts
            const resp = await fetch(`/api/agent/generate?run_id=${runId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: '', images: [], ai_provider: ''}),
            });
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, {stream: true});
                const lines = buffer.split('\n');
                buffer = lines.pop();
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.events.push(data);
                            if (data.status === 'error') { this.error = true; this.errorMsg = data.message; }
                            if (data.node === 'save_draft' && data.status === 'done') {
                                this.done = true;
                                this.draftId = data.data.draft_id;
                            }
                        } catch(e) {}
                    }
                }
            }
        },
    }));
});
</script>
{% endblock %}
```

- [ ] **Step 2: 创建 app/templates/settings.html**

```html
{% extends "base.html" %}
{% block title %}设置 — 小红书 AI 运营平台{% endblock %}
{% block content %}
<h2>设置</h2>

<!-- AI Configuration -->
<section>
    <h3>AI Provider 配置</h3>
    <div x-data="aiConfigManager">
        <template x-for="(cfg, i) in configs" :key="cfg.id">
            <article>
                <header>
                    <strong x-text="cfg.provider.toUpperCase()"></strong>
                    <small x-show="cfg.is_active" style="color:var(--pico-primary);">● 当前使用</small>
                </header>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.9em;">
                    <div>Quick: <code x-text="cfg.quick_model"></code></div>
                    <div>Deep: <code x-text="cfg.deep_model"></code></div>
                </div>
                <footer>
                    <button @click="activate(cfg.id)" x-show="!cfg.is_active" style="font-size:0.85em;">启用</button>
                    <button @click="remove(cfg.id)" class="secondary" style="font-size:0.85em;">删除</button>
                </footer>
            </article>
        </template>

        <details>
            <summary>添加新 Provider</summary>
            <form @submit.prevent="addConfig">
                <label>Provider</label>
                <select x-model="form.provider" required>
                    <option value="">-- 选择 --</option>
                    <option>openai</option>
                    <option>claude</option>
                    <option>deepseek</option>
                </select>
                <label>API Key</label>
                <input type="password" x-model="form.api_key" required>
                <label>API Base URL (可选)</label>
                <input type="text" x-model="form.api_base" placeholder="留空使用默认">
                <label>Quick Model</label>
                <input type="text" x-model="form.quick_model" required placeholder="gpt-4o-mini">
                <label>Deep Model</label>
                <input type="text" x-model="form.deep_model" required placeholder="gpt-4o">
                <button type="submit">保存</button>
            </form>
        </details>
    </div>
</section>

<!-- XHS Account Status -->
<section>
    <h3>小红书账号</h3>
    <div x-data="xhsStatus" x-init="checkStatus">
        <p x-show="loading">检查中...</p>
        <div x-show="!loading && status">
            <p x-show="status.logged_in">✅ 已登录<span x-text="' (' + (status.username || '') + ')'"></span></p>
            <p x-show="!status.logged_in">❌ 未登录</p>
        </div>
        <div x-show="qrcode">
            <p>请用小红书 App 扫描二维码登录：</p>
            <img :src="'data:image/png;base64,' + qrcode" style="max-width:300px;">
        </div>
        <button @click="checkStatus">刷新状态</button>
        <button @click="getQRCode" x-show="status && !status.logged_in">获取登录二维码</button>
    </div>
</section>

<!-- MCP Entry Link -->
<section>
    <h3>MCP 运营入口</h3>
    <p>MCP 服务运行在 <code>http://localhost:18060</code></p>
    <a href="http://localhost:18060" target="_blank" role="button" class="secondary">🔗 打开 MCP 服务页面</a>
    <small>MCP 提供了 REST API 和 MCP 协议端点，可在此查看服务状态。</small>
</section>

<script>
document.addEventListener('alpine:init', () => {
    Alpine.data('aiConfigManager', () => ({
        configs: {{ configs | tojson | safe }},
        form: {provider:'', api_key:'', api_base:'', quick_model:'', deep_model:''},
        async addConfig() {
            const resp = await fetch('/api/configs/ai', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(this.form),
            });
            if (resp.ok) {
                const cfg = await resp.json();
                this.configs.push(cfg);
                this.form = {provider:'', api_key:'', api_base:'', quick_model:'', deep_model:''};
            }
        },
        async activate(id) {
            await fetch(`/api/configs/ai/${id}/activate`, {method: 'POST'});
            this.configs.forEach(c => c.is_active = (c.id === id));
        },
        async remove(id) {
            if (!confirm('确认删除？')) return;
            await fetch(`/api/configs/ai/${id}`, {method: 'DELETE'});
            this.configs = this.configs.filter(c => c.id !== id);
        },
    }));

    Alpine.data('xhsStatus', () => ({
        status: null, loading: false, qrcode: null,
        async checkStatus() {
            this.loading = true;
            try {
                const resp = await fetch('/api/xhs/status');
                this.status = await resp.json();
            } catch(e) { this.status = {logged_in: false}; }
            this.loading = false;
        },
        async getQRCode() {
            const resp = await fetch('/api/xhs/login', {method: 'POST'});
            const data = await resp.json();
            this.qrcode = data.qrcode_base64;
        },
    }));
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/generate.html app/templates/settings.html && git commit -m "feat: add generate progress page and settings page with AI config and XHS status"
```

---

### Task 16: Agent Nodes 修复 & 完善

**Files:**
- Modify: `app/agent/nodes.py` (fix duplicate `publisher_node`, add proper DB types)
- Test: `tests/test_agent_nodes.py`

- [ ] **Step 1: 重写 app/agent/nodes.py（修复版）**

The `nodes.py` from Task 8 had a duplicate `publisher_node`. Replace completely:

```python
import json
import re
from datetime import datetime
from app.agent.state import AgentState
from app.agent.prompts import (
    THEME_ANALYZER_PROMPT, CONTENT_GENERATOR_PROMPT,
    AI_DETECTOR_PROMPT, HUMANIZER_PROMPT, XHS_OPTIMIZER_PROMPT,
)
from app.models import Post, AIConfig
from app.services.llm_factory import LLMFactory


def parse_generated_content(text: str) -> tuple[str, str, list[str]]:
    """Parse AI output into (title, body, tags)."""
    lines = text.strip().split("\n")
    title = ""
    body_lines = []
    tags = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if not title and not s.startswith("#") and len(s) <= 30:
            title = s
        elif s.startswith("#"):
            tag = s.lstrip("#").strip()
            if tag:
                tags.append(tag)
        else:
            body_lines.append(s)
    return title, "\n".join(body_lines), tags


async def _call_llm(prompt: str, llm) -> str:
    resp = llm.invoke(prompt)
    return resp.content if hasattr(resp, 'content') else str(resp)


async def theme_analyzer_node(state: AgentState, quick_llm, db) -> dict:
    prompt = THEME_ANALYZER_PROMPT.format(theme=state["theme"])
    content = await _call_llm(prompt, quick_llm)
    # Strip markdown code fences if present
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content)
    return {"theme_analysis": json.loads(content)}


async def content_generator_node(state: AgentState, quick_llm, db) -> dict:
    analysis = state.get("theme_analysis", {})
    prompt = CONTENT_GENERATOR_PROMPT.format(
        theme=state["theme"],
        style=analysis.get("style", "真实分享"),
        keywords=", ".join(analysis.get("keywords", [])),
        tone_notes=analysis.get("tone_notes", "真实车主视角"),
    )
    content = await _call_llm(prompt, quick_llm)
    return {"draft_content": content}


async def ai_detector_node(state: AgentState, deep_llm, db) -> dict:
    prompt = AI_DETECTOR_PROMPT.format(content=state["draft_content"])
    content = await _call_llm(prompt, deep_llm)
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content)
    result = json.loads(content)
    return {
        "flagged_sections": result.get("flagged_sections", []),
        "needs_humanization": result.get("has_ai_traces", False),
    }


async def humanizer_node(state: AgentState, deep_llm, db) -> dict:
    prompt = HUMANIZER_PROMPT.format(
        content=state["draft_content"],
        flagged_sections=json.dumps(state.get("flagged_sections", []), ensure_ascii=False),
    )
    content = await _call_llm(prompt, deep_llm)
    return {"humanized_content": content}


async def xhs_optimizer_node(state: AgentState, deep_llm, db) -> dict:
    source = state.get("humanized_content") or state["draft_content"]
    title, body, _ = parse_generated_content(source)
    prompt = XHS_OPTIMIZER_PROMPT.format(
        content=source,
        title_len=len(title),
        body_len=len(body),
    )
    content = await _call_llm(prompt, deep_llm)
    content = re.sub(r'^```(?:json)?\s*', '', content.strip())
    content = re.sub(r'\s*```$', '', content)
    result = json.loads(content)
    return {
        "final_title": result["title"],
        "final_content": result["body"],
        "final_tags": result["tags"],
        "warnings": result.get("warnings", []),
    }


async def save_draft_node(state: AgentState, llm, db) -> dict:
    post = Post(
        title=state.get("final_title", ""),
        content=state.get("final_content", ""),
        status="draft",
        theme=state["theme"],
        ai_provider=state["ai_provider"],
    )
    post.set_tags(state.get("final_tags", []))
    post.set_images(state["images"])
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"checkpoint_id": str(post.id)}


async def publisher_node(state: AgentState, llm, db) -> dict:
    from app.services.xhs_client import XHSClient
    from app.agent.tools import MCP_BASE_URL

    post_id = state.get("checkpoint_id")
    post = db.query(Post).get(int(post_id)) if post_id else None

    title = state.get("final_title", "")
    content = state.get("final_content", "")
    tags = state.get("final_tags", [])
    images = state["images"]

    async with XHSClient(base_url=MCP_BASE_URL) as client:
        try:
            result = await client.publish_content(
                title=title, content=content, images=images, tags=tags,
            )
            if post:
                post.status = "published"
                post.xhs_feed_id = result.get("feed_id", "")
                post.xhs_note_url = result.get("note_url", "")
                post.publish_time = datetime.utcnow()
                db.commit()
            return {"error": None}
        except Exception as e:
            if post:
                post.status = "failed"
                db.commit()
            return {"error": str(e)}
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_agent_nodes.py -v
```

- [ ] **Step 3: Commit**

```bash
git add app/agent/nodes.py && git commit -m "fix: remove duplicate publisher_node, add markdown fence stripping, fix DB integration"
```

---

### Task 17: 集成验证 — 启动应用

- [ ] **Step 1: 安装依赖**

```bash
cd /Users/liam/workspace/content-operation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 2: 验证应用能启动**

```bash
cd /Users/liam/workspace/content-operation
mkdir -p data/uploads
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/api/stats | python -m json.tool
# Expected: {"drafts":0,"published":0,"this_month":0}
```

- [ ] **Step 3: 验证所有 API 端点**

```bash
# Create a config
curl -s -X POST http://localhost:8000/api/configs/ai \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai","api_key":"sk-test","quick_model":"gpt-4o-mini","deep_model":"gpt-4o"}' | python -m json.tool

# List configs
curl -s http://localhost:8000/api/configs/ai | python -m json.tool

# Create a post
curl -s -X POST http://localhost:8000/api/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","content":"Hello World","tags":["test"],"theme":"test"}' | python -m json.tool

# Get posts
curl -s http://localhost:8000/api/posts | python -m json.tool
```

- [ ] **Step 4: 验证前端页面**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# Expected: 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/posts
# Expected: 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/settings
# Expected: 200
```

- [ ] **Step 5: 停止并清理**

```bash
kill %1  # stop uvicorn
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: integration verification - app starts, all APIs and pages respond"
```

---

### Task 18: Docker 构建 & 验证

- [ ] **Step 1: 构建 Docker 镜像**

```bash
cd /Users/liam/workspace/content-operation
docker compose build
```

- [ ] **Step 2: 启动服务**

```bash
docker compose up -d
sleep 5
docker compose ps
# Expected: both app and mcp services UP
```

- [ ] **Step 3: 验证服务**

```bash
curl -s http://localhost:8000/api/stats
# Expected: {"drafts":0,"published":0,"this_month":0}
curl -s http://localhost:8000/
# Expected: HTML content with 200 status
```

- [ ] **Step 4: 停止服务**

```bash
docker compose down
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Dockerfile && git commit -m "feat: verified Docker build and compose startup"
```

---

## 实现顺序总结

```
Task 1  → 项目脚手架 & 依赖
Task 2  → 配置 & 数据库
Task 3  → 数据模型
Task 4  → LLM 工厂
Task 5  → XHS MCP 客户端
Task 6  → Agent State & Prompts
Task 7  → Agent Tools
Task 8  → Agent Nodes
Task 9  → Agent Graph
Task 10 → API Routers (configs + posts)
Task 11 → API Routers (xhs + agent)
Task 12 → FastAPI 入口 & 页面路由
Task 13 → 前端 (base + index + app.js)
Task 14 → 前端 (posts list + detail)
Task 15 → 前端 (generate + settings)
Task 16 → Agent Nodes 修复
Task 17 → 集成验证
Task 18 → Docker 验证
```
