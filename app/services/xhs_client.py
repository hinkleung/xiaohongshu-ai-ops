import logging
from typing import Optional
import httpx

logger = logging.getLogger("app.xhs_client")


class XHSClient:
    """Async HTTP client wrapping xiaohongshu-mcp REST API.

    Real API paths (from routes.go):
      GET  /health
      ANY  /mcp
      GET  /api/v1/login/status
      GET  /api/v1/login/qrcode
      DELETE /api/v1/login/cookies
      POST /api/v1/publish
      POST /api/v1/publish_video
      GET  /api/v1/feeds/list
      GET|POST /api/v1/feeds/search
      POST /api/v1/feeds/detail
      POST /api/v1/user/profile
      POST /api/v1/feeds/comment
      POST /api/v1/feeds/comment/reply
      GET  /api/v1/user/me

    Response format (from handlers_api.go):
      Success: {"success": true, "data": {...}, "message": "..."}
      Error:   {"error": "...", "code": "...", "details": ...}
    """

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
        return f"{self.base_url}{path}"

    async def _get(self, path: str) -> dict:
        logger.debug("MCP GET %s", path)
        resp = await self._client.get(self._url(path))
        resp.raise_for_status()
        body = resp.json()
        # Unwrap {success:true, data:..., message:...}
        if isinstance(body, dict) and body.get("success"):
            return body["data"]
        return body

    async def _post(self, path: str, data: dict) -> dict:
        logger.debug("MCP POST %s", path)
        resp = await self._client.post(self._url(path), json=data)
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and body.get("success"):
            return body["data"]
        return body

    async def _delete(self, path: str) -> dict:
        logger.debug("MCP DELETE %s", path)
        resp = await self._client.delete(self._url(path))
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and body.get("success"):
            return body["data"]
        return body

    # ── Login ──────────────────────────────────────────

    async def check_login_status(self) -> dict:
        """GET /api/v1/login/status → {is_logged_in, username}"""
        return await self._get("/api/v1/login/status")

    async def get_login_qrcode(self) -> dict:
        """GET /api/v1/login/qrcode → {timeout, is_logged_in, qrcode_base64}"""
        return await self._get("/api/v1/login/qrcode")

    async def logout(self) -> dict:
        """DELETE /api/v1/login/cookies → delete cookies, reset login state"""
        return await self._delete("/api/v1/login/cookies")

    # ── Publish ────────────────────────────────────────

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
        """POST /api/v1/publish"""
        body: dict = {
            "title": title,
            "content": content,
            "images": images,
            "tags": tags or [],
            "visibility": visibility,
            "is_original": is_original,
        }
        if schedule_at:
            body["schedule_at"] = schedule_at
        return await self._post("/api/v1/publish", body)

    # ── Feeds ──────────────────────────────────────────

    async def get_feed_detail(self, feed_id: str, xsec_token: str) -> dict:
        """POST /api/v1/feeds/detail"""
        return await self._post("/api/v1/feeds/detail", {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
        })

    async def search_feeds(self, keyword: str, filters: Optional[dict] = None) -> dict:
        """POST /api/v1/feeds/search"""
        return await self._post("/api/v1/feeds/search", {
            "keyword": keyword,
            "filters": filters or {},
        })

    # ── User / Feeds ────────────────────────────────────

    async def get_my_profile(self) -> dict:
        """GET /api/v1/user/me → user profile info"""
        return await self._get("/api/v1/user/me")

    async def list_my_feeds(self) -> dict:
        """GET /api/v1/feeds/list → my note/feed list"""
        return await self._get("/api/v1/feeds/list")
