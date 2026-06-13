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
