import logging
from typing import Optional
import httpx

logger = logging.getLogger("app.xhs_client")


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
        logger.debug("MCP GET %s", path)
        resp = await self._client.get(self._url(path))
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, data: dict) -> dict:
        logger.debug("MCP POST %s", path)
        resp = await self._client.post(self._url(path), json=data)
        resp.raise_for_status()
        return resp.json()

    async def check_login_status(self) -> dict:
        return await self._get("/check_login_status")

    async def get_login_qrcode(self) -> dict:
        return await self._get("/get_login_qrcode")

    async def publish_content(
        self, title: str, content: str, images: list[str],
        tags: Optional[list[str]] = None, schedule_at: Optional[str] = None,
        is_original: bool = False, visibility: str = "公开可见",
    ) -> dict:
        body = {
            "title": title, "content": content, "images": images,
            "tags": tags or [], "visibility": visibility, "is_original": is_original,
        }
        if schedule_at:
            body["schedule_at"] = schedule_at
        return await self._post("/publish_content", body)

    async def get_feed_detail(self, feed_id: str, xsec_token: str) -> dict:
        return await self._get(f"/get_feed_detail?feed_id={feed_id}&xsec_token={xsec_token}")

    async def search_feeds(self, keyword: str, filters: Optional[dict] = None) -> dict:
        return await self._post("/search_feeds", {"keyword": keyword, "filters": filters or {}})
