"""Adapter 基类"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseAdapter(ABC):
    """Agent 接口适配器基类"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    async def send(self, user_message: str, context: Optional[dict] = None,
                   test_id: str = "", timeout: int = 30) -> dict:
        """
        向 Agent 发送一条用户消息，返回 Agent 的回复。
        返回格式: {"reply": "...", "tool_calls": [...]}
        """
        ...
