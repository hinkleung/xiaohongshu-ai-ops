from typing import TypedDict, Optional


class AgentState(TypedDict):
    # Input
    theme: str
    activity_description: str  # raw long activity brief
    images: list[str]
    ai_provider: str

    # Node outputs
    theme_analysis: dict           # {style, keywords, audience}
    draft_content: str             # Node 2 raw output
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
