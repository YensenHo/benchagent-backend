"""OpenAI-compatible 适配器 — 兼容大多数 Agent 框架"""
import httpx
from .base import BaseAdapter


class OpenAIAdapter(BaseAdapter):
    """通过 POST /v1/chat/completions 与 Agent 通信"""

    async def send(self, user_message: str, context=None, test_id="", timeout=30) -> dict:
        messages = []

        # 如果有上下文（多轮对话），先拼接历史消息
        if context and "previous_messages" in context:
            messages.extend(context["previous_messages"])

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        body = {
            "model": "agent",  # 兼容大多数框架
            "messages": messages,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            data = resp.json()

            reply = ""
            tool_calls = []

            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    msg = choice["message"]
                    reply = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])

            return {"reply": reply, "tool_calls": tool_calls}
