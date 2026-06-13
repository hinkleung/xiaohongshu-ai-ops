from typing import Literal, AsyncIterator
from langgraph.graph import StateGraph, END
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
from app.models import Post, AIConfig
from app.services.llm_factory import LLMFactory


def should_humanize(state: AgentState) -> Literal["humanizer", "optimizer"]:
    if state.get("needs_humanization"):
        return "humanizer"
    return "optimizer"


def build_graph() -> StateGraph:
    """Build the LangGraph StateGraph for the XHS content agent."""
    workflow = StateGraph(AgentState)

    workflow.add_node("theme_analyzer", theme_analyzer_node)
    workflow.add_node("content_generator", content_generator_node)
    workflow.add_node("ai_detector", ai_detector_node)
    workflow.add_node("humanizer", humanizer_node)
    workflow.add_node("xhs_optimizer", xhs_optimizer_node)
    workflow.add_node("save_draft", save_draft_node)
    workflow.add_node("publisher", publisher_node)

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
        self, theme: str, images: list[str], ai_provider: str,
    ) -> AsyncIterator[dict]:
        """Run the generate flow, yielding progress events."""
        db = self.db_session_factory()
        try:
            config = db.query(AIConfig).filter(
                AIConfig.provider == ai_provider, AIConfig.is_active == True,
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

            node_order = [
                ("theme_analyzer", "主题解析中..."),
                ("content_generator", "文案生成中..."),
                ("ai_detector", "AI 痕迹检测中..."),
                ("humanizer", "口语化润色中..."),
                ("xhs_optimizer", "内容运营优化中..."),
                ("save_draft", "保存草稿中..."),
            ]

            node_funcs = {
                "theme_analyzer": theme_analyzer_node,
                "content_generator": content_generator_node,
                "ai_detector": ai_detector_node,
                "humanizer": humanizer_node,
                "xhs_optimizer": xhs_optimizer_node,
                "save_draft": save_draft_node,
            }

            for node_name, message in node_order:
                yield {"node": node_name, "status": "running", "message": message}

                if node_name == "humanizer" and not state.get("needs_humanization"):
                    yield {"node": node_name, "status": "done", "message": "跳过润色（未检测到 AI 痕迹）"}
                    continue

                try:
                    fn = node_funcs[node_name]
                    llm = quick_llm if node_name in ("theme_analyzer", "content_generator") else deep_llm
                    result = await fn(state, llm, db)
                    state.update(result)

                    yield {
                        "node": node_name, "status": "done",
                        "message": f"{message}完成",
                        "data": _summarize(node_name, state),
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
            return await publisher_node(state, llm, db)
        finally:
            db.close()


def _summarize(node_name: str, state: AgentState) -> dict:
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
