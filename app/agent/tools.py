from langchain_core.tools import tool
from app.services.xhs_client import XHSClient
from app.config import XHS_MCP_URL

MCP_BASE_URL = XHS_MCP_URL  # from XHS_MCP_URL env var, default http://localhost:18060


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
