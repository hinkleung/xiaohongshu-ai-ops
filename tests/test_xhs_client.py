import pytest
from unittest.mock import patch, AsyncMock
from app.services.xhs_client import XHSClient


@pytest.mark.asyncio
async def test_check_login_status():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"success": True, "data": {"is_logged_in": True, "username": "test_user"}},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.check_login_status()
            assert result["is_logged_in"] is True
            assert result["username"] == "test_user"


@pytest.mark.asyncio
async def test_publish_content():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"success": True, "data": {"feed_id": "abc123", "note_url": "https://..."}},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.publish_content(
                title="Test", content="Hello", images=["/images/1.jpg"], tags=["tag1"],
            )
            assert result["feed_id"] == "abc123"


@pytest.mark.asyncio
async def test_check_login_status_legacy_format():
    """Handle response without success wrapper."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"is_logged_in": False},
        )
        async with XHSClient(base_url="http://localhost:18060") as client:
            result = await client.check_login_status()
            assert result["is_logged_in"] is False
