"""REST 适配器 — 标准 POST /eval 端点"""
import httpx
from .base import BaseAdapter


class RESTAdapter(BaseAdapter):
    """通过 POST /eval 与 Agent 通信"""

    async def send(self, user_message: str, context=None, test_id="", timeout=30) -> dict:
        body = {
            "test_id": test_id,
            "user_message": user_message,
        }
        if context:
            body["context"] = context

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/eval",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "reply": data.get("reply", ""),
                "tool_calls": data.get("tool_calls", [])
            }
