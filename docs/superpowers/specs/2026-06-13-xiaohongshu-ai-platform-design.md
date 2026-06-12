# 小红书 AI 运营平台 — 设计规格说明

## 概述

面向小鹏汽车车主个人使用的小红书 AI 运营平台。用户输入官方活动主题，平台通过 LangGraph 多 Agent 协作生成符合小红书规范、去 AI 味的图文文案，经用户审核后通过 xiaohongshu-mcp 发布到小红书。

### 核心需求

- 输入活动主题 → AI 生成文案，用户提供图片
- 多 AI provider 可配置（Claude API / OpenAI API / DeepSeek API，后续可扩展）
- 文案必须去 AI 味（小红书打击 AI 生成内容，严重会限流/封号）
- 草稿管理、文章管理（查看、编辑、发布、删除）
- 遵循小红书运营规则（标题≤20字、正文≤1000字、违禁词检测、引流检测等）

---

## 1. 整体架构

```
                        Docker (docker compose)

  ┌──────────────────────┐    ┌──────────────────────────┐
  │  Python Backend       │    │  xiaohongshu-mcp (Go)    │
  │  (FastAPI + LangGraph)│───▶│  + Chrome headless        │
  │  port 8000            │REST│  port 18060              │
  │                       │◀───│                          │
  │  ┌─────────────────┐  │    │  publish_content         │
  │  │ LangGraph Agent │  │    │  get_feed_detail         │
  │  │ (7 Node 多Agent) │  │    │  search_feeds            │
  │  └─────────────────┘  │    │  check_login_status      │
  │  ┌─────────────────┐  │    │  get_login_qrcode        │
  │  │ SQLite           │  │    │  ...                     │
  │  │ (草稿/配置/记忆) │  │    └──────────────────────────┘
  │  └─────────────────┘  │
  │  ┌─────────────────┐  │
  │  │ Jinja2 模板      │  │
  │  │ + Alpine.js      │  │
  │  └─────────────────┘  │
  └──────────────────────┘
```

| 决策 | 选择 | 理由 |
|------|------|------|
| 前后端关系 | FastAPI 直接渲染 HTML + Jinja2 + Alpine.js | 个人工具，5 个页面，无需前后分离 |
| Agent 框架 | LangChain + LangGraph StateGraph | 社区最成熟，langchain-mcp-adapters 原生支持 MCP |
| Agent 与后端关系 | 内嵌在 FastAPI 中，请求即触发 | 简单直接 |
| 与 MCP 通信 | REST API（MCP 自带 `/api/v1/*`） | httpx 直调，简单可靠 |
| 数据库 | SQLite 单文件 | volume 挂载持久化，零运维 |
| 部署 | Docker Compose 双容器 | 一键启动，隔离干净 |
| 前端技术 | Jinja2 + Alpine.js + Pico.css | 无构建步骤，全部在 Python 镜像内 |

---

## 2. Agent 架构 (LangGraph StateGraph)

借鉴 TradingAgents 的多 Agent + 对抗辩论模式，设计 7 个 Agent Node：

```
用户输入 主题 + 图片 + AI provider
        │
        ▼
┌──────────────────────────────────┐
│ Node 1: Theme Analyzer (quick)   │  解析主题 → 风格约束 → 关键词
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Node 2: Content Generator (quick)│  生成标题 + 正文 + 标签初稿
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Node 3: AI Detector (deep)       │  对抗环节：检测 AI 痕迹 / 空洞话术 /
│        对抗环节                   │  营销腔 → 输出 flagged_sections
└────────────────┬─────────────────┘
                 │
          has_ai_traces?
       是 ▼           否 ▼
┌──────────────────┐     │
│ Node 4: Humanizer │     │  口语化改写 → 模拟真实车主分享
│ (deep)            │     │
└────────┬─────────┘     │
         └───────┬───────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Node 5: XHS Content Optimizer    │  小红书运营规则硬约束检查：
│ (deep)                            │  · 标题 ≤ 20 字
│                                   │  · 正文 ≤ 1000 字
│                                   │  · 违禁词扫描 & 替换
│                                   │  · 引流/搬运特征检测
│                                   │  · Tags 相关性优化
│ → 输出 final_content               │
└────────────────┬─────────────────┘
                 │
                 ▼
┌──────────────────────────────────┐
│ Node 6: Save Draft                │  存入 SQLite（LangGraph Checkpoint）
│                                   │  → 返回前端供用户审核
└────────────────┬─────────────────┘
                 │
         ┌───────┼───────┬──────────┐
         ▼       ▼       ▼          ▼
      编辑    发布    保存草稿    重新生成
                │
                ▼
       ┌──────────────────┐
       │ Node 7: Publisher │  调用 xiaohongshu-mcp REST API
       │ (MCP Tool)        │  发布图文到小红书
       └──────────────────┘
```

### Agent State

```python
class AgentState(TypedDict):
    theme: str              # 活动主题
    images: list[str]       # 用户上传的图片路径
    ai_provider: str        # 用户选择的 AI: claude / openai / deepseek

    theme_analysis: dict    # Node 1 输出: 风格约束、关键词
    draft_content: str      # Node 2 输出: 初版文案
    flagged_sections: list  # Node 3 输出: 被标记的 AI 段
    humanized_content: str  # Node 4 输出: 润色后文案
    final_content: str      # Node 5 输出: 经运营规则优化后的文案

    needs_humanization: bool  # Node 3 判定是否需要润色
    warnings: list[str]     # Node 5 输出的提醒（违禁词替换等）
    checkpoint_id: str      # 草稿 ID
```

### 双模型分层

| 层级 | 用途 | 适用 Node | 推荐模型 |
|------|------|-----------|---------|
| quick_think | 生成初稿、解析主题 | 1, 2 | GPT-4o-mini / DeepSeek-V3 |
| deep_think | 质量把关、对抗检测、润色 | 3, 4, 5 | Claude Sonnet 4.6 / GPT-4o |

每个 AI provider 配置时需分别指定 quick 和 deep 使用的模型。

### 记忆系统

- `generation_history` 表记录每次生成的完整 State 快照
- Node 5 在优化时可检索历史成功帖子的风格特征
- 后续版本可引入 BM25 检索（参考 TradingAgents 模式）

---

## 3. 数据模型 (SQLite)

### ai_config — AI 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| provider | TEXT NOT NULL | claude / openai / deepseek |
| api_key | TEXT NOT NULL | 加密存储（Fernet 对称加密） |
| api_base | TEXT | 自定义 endpoint（可选） |
| quick_model | TEXT | 如 gpt-4o-mini |
| deep_model | TEXT | 如 claude-sonnet-4-6 |
| is_active | BOOLEAN DEFAULT 0 | 当前启用的 provider（只能一个） |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### posts — 帖子

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| title | TEXT | 标题（≤20字） |
| content | TEXT | 正文 |
| tags | TEXT | JSON: ["tag1", "tag2"] |
| images | TEXT | JSON: ["/uploads/img1.jpg"] |
| status | TEXT NOT NULL | draft / published / failed |
| xhs_feed_id | TEXT | 发布后的小红书 feed id |
| xhs_note_url | TEXT | 发布后的小红书链接 |
| theme | TEXT | 关联的活动主题 |
| ai_provider | TEXT | 生成时用的 AI |
| publish_time | TIMESTAMP | 发布时间（支持定时） |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### generation_history — 生成记录（记忆基础）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| post_id | INTEGER FK→posts | 关联帖子 |
| node | TEXT | 哪个 Agent Node |
| input_state | TEXT JSON | 输入状态快照 |
| output_state | TEXT JSON | 输出状态快照 |
| ai_provider | TEXT | |
| tokens_used | INTEGER | |
| created_at | TIMESTAMP | |

### agent_checkpoints

LangGraph `SqliteSaver` 自动管理的表（thread_id, checkpoint_id, checkpoint, metadata），提供断点续跑 + 草稿恢复能力。

---

## 4. API 设计

```
POST   /api/agent/generate         触发 Agent 生成（返回 SSE 流）
GET    /api/agent/stream/{run_id}  订阅 Agent 运行进度（SSE）

GET    /api/posts                  文章列表（?status=draft|published&?theme=xxx）
POST   /api/posts                  创建草稿（手动新建）
GET    /api/posts/{id}             文章详情（HTML 片段或 JSON）
PUT    /api/posts/{id}             更新文章（编辑文案/图片）
DELETE /api/posts/{id}             删除文章
POST   /api/posts/{id}/publish     发布到小红书（触发 Agent Publisher Node）
POST   /api/posts/{id}/regenerate  重新生成（回到 Agent Node 2）

GET    /api/configs/ai             获取 AI 配置列表
POST   /api/configs/ai             新增 AI 配置
PUT    /api/configs/ai/{id}        更新 AI 配置
DELETE /api/configs/ai/{id}        删除 AI 配置
POST   /api/configs/ai/{id}/activate  切换启用的 AI

GET    /api/xhs/status             查看 MCP 登录状态
POST   /api/xhs/login              触发扫码登录（返回二维码 base64）
GET    /api/xhs/feeds/{id}         查看已发布帖子详情（从 MCP 拉）

GET    /api/stats                  简单统计（草稿数/已发布数/本月发布数）
```

---

## 5. 前端页面

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | 首页/主题输入 | 输入主题、选择 AI、上传图片、点击生成 → SSE 展示进度 |
| `/posts` | 文章管理 | Tab 切换草稿/已发布/失败，列表含操作按钮 |
| `/posts/{id}` | 文章详情 & 编辑 | 富文本编辑标题/正文/标签，图片预览，保存/发布/重新生成 |
| `/generate/{run_id}` | 生成过程页 | SSE 实时流式展示 Agent 各 Node 进度和输出 |
| `/settings` | 设置 | AI 配置 CRUD、小红书登录状态、扫码入口、MCP 运营入口链接、System Prompt 自定义 |

**技术栈：** Jinja2 模板 + Alpine.js（交互）+ Pico.css（样式），无构建步骤。

**SSE 流式展示：** 生成过程中页面实时展示：
```
🟢 主题解析完成 → "春日出游" → 风格：轻松活泼、车主视角
🟢 文案生成完成 → 初稿已生成 (328字)
🟡 AI 检测中... → 发现 3 处疑似 AI 痕迹
🟢 润色完成 → 已口语化改写
🟢 内容优化完成 → 标题14字 ✅ 无违禁词 ✅ 标签已优化
🟢 草稿已保存 → 前往查看
```

---

## 6. Docker 部署

### docker-compose.yml

```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
    environment:
      - XHS_MCP_URL=http://mcp:18060
    depends_on: [mcp]

  mcp:
    image: xpzouying/xiaohongshu-mcp
    ports: ["18060:18060"]
    volumes:
      - ./mcp-data:/app/data
      - ./data/uploads:/images
    command: -headless=true
```

### Python 项目结构

```
content-operation/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py              # FastAPI 入口 + 生命周期
│   ├── config.py            # 配置加载（环境变量 + DB）
│   ├── db.py                # SQLite 初始化 & 连接
│   ├── models.py            # SQLAlchemy 模型 + Pydantic 校验
│   ├── routers/
│   │   ├── agent.py         # /api/agent/* SSE 流式
│   │   ├── posts.py         # /api/posts/* CRUD
│   │   ├── configs.py       # /api/configs/* AI 配置
│   │   ├── xhs.py           # /api/xhs/* MCP 状态代理
│   │   └── pages.py         # / 前端页面路由
│   ├── agent/
│   │   ├── graph.py         # LangGraph StateGraph 定义 + 条件边
│   │   ├── nodes.py         # 7 个 Agent Node 实现
│   │   ├── state.py         # AgentState TypedDict
│   │   ├── prompts.py       # System prompts 模板
│   │   └── tools.py         # MCP REST 封装为 LangChain Tool
│   ├── services/
│   │   ├── xhs_client.py    # httpx 封装 MCP REST API
│   │   └── llm_factory.py   # 多 provider LLM 工厂
│   └── templates/
│       ├── base.html        # 布局骨架
│       ├── index.html       # 首页 / 生成
│       ├── posts.html       # 文章列表
│       ├── post_detail.html # 文章详情 / 编辑
│       ├── generate.html    # 生成进度页
│       └── settings.html    # 设置页
├── static/
│   └── app.js               # Alpine.js 交互逻辑
└── data/                     # 运行时数据（gitignore）
    ├── app.db
    └── uploads/
```

### 错误处理矩阵

| 场景 | 处理方式 |
|------|---------|
| MCP 不可达 | Agent 运行前先 check_login_status，不可用时前端提示 |
| MCP 登录过期 | 前端展示扫码入口（get_login_qrcode） |
| AI API 调用失败 | Agent Node try/catch → generation_history 标记 → 前端显示错误 + 重试 |
| 发布失败 | posts.status = 'failed' → 用户可重试 |
| 发帖超限（≥50/天） | Node 6 发布前检查当天 count，超限时阻止 + 提醒 |
| 图片路径含中文 | Node 6 发布前校验，警告用户重命名 |

---

## 7. 非功能性需求

- **安全：** API Key 使用 Fernet 对称加密存储于 SQLite
- **数据持久化：** SQLite + uploads 目录通过 Docker volume 挂载到宿主机
- **启动方式：** `docker compose up -d` 一键启动，访问 `http://localhost:8000`
- **小红书合规：** 同一账号不在多个网页端同时登录；发帖间隔遵守平台限制
