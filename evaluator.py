"""
BenchAgent Evaluator — 核心评测引擎
负责：加载测试集 → 逐个调 Agent → 收集回复 → 返回原始结果给 judge 评分
"""
import json, time, asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import httpx

from adapters.base import BaseAdapter
from adapters.rest_adapter import RESTAdapter
from adapters.openai_adapter import OpenAIAdapter


@dataclass
class AgentResponse:
    """Agent 对单道题的回复"""
    reply: str
    tool_calls: list = field(default_factory=list)
    status_code: int = 200
    error: Optional[str] = None
    latency_ms: float = 0       # 平台实际计时
    timed_out: bool = False
    retry_count: int = 0


@dataclass
class QuestionResult:
    """单道题的评测原始数据"""
    question_id: str
    question: dict
    response: AgentResponse
    success: bool                # Agent 是否成功返回了回复


@dataclass
class EvalResult:
    """完整评测结果"""
    agent_name: str
    agent_url: str
    interface_type: str
    total_questions: int
    completed: int
    failed: int
    timed_out: int
    total_latency_ms: float
    avg_latency_ms: float
    question_results: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class AgentEvaluator:
    """核心评测引擎"""

    def __init__(self, benchmark_path: str = None):
        if benchmark_path is None:
            benchmark_path = Path(__file__).parent / "benchmarks" / "customer_service_v1.json"
        self.benchmark = self._load_benchmark(benchmark_path)
        self.retry_config = self.benchmark.get("retry", {"max_attempts": 3, "interval_seconds": 2})

    def _load_benchmark(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f)

    def _get_adapter(self, interface_type: str, agent_url: str) -> BaseAdapter:
        if interface_type == "openai":
            return OpenAIAdapter(agent_url)
        elif interface_type == "rest":
            return RESTAdapter(agent_url)
        else:
            raise ValueError(f"Unknown interface type: {interface_type}")

    def _get_timeout(self, question: dict) -> int:
        """从题目或基准配置获取超时时间"""
        return question.get("timeout", self.benchmark.get("timeouts", {}).get(
            question.get("difficulty", "easy"), 30))

    async def _send_with_retry(self, adapter: BaseAdapter, question: dict, timeout: int) -> AgentResponse:
        """发送请求，支持超时降权和自动重试"""
        last_error = None
        max_attempts = self.retry_config["max_attempts"]
        interval = self.retry_config["interval_seconds"]

        for attempt in range(max_attempts):
            try:
                t_start = time.time()
                result = await adapter.send(
                    user_message=question["user_message"],
                    context=question.get("context"),
                    test_id=question["id"],
                    timeout=timeout
                )
                latency = (time.time() - t_start) * 1000

                return AgentResponse(
                    reply=result.get("reply", ""),
                    tool_calls=result.get("tool_calls", []),
                    status_code=200,
                    latency_ms=latency,
                    retry_count=attempt
                )

            except asyncio.TimeoutError:
                last_error = "timeout"
                if attempt < max_attempts - 1:
                    await asyncio.sleep(interval)
                continue

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
                return AgentResponse(
                    reply="", status_code=e.response.status_code,
                    error=last_error, latency_ms=0, retry_count=attempt
                )

            except Exception as e:
                last_error = str(e)[:200]
                if attempt < max_attempts - 1:
                    await asyncio.sleep(interval)
                continue

        # 全部重试失败
        if last_error == "timeout":
            return AgentResponse(
                reply="[超时未响应]",
                error="timeout after retries",
                latency_ms=timeout * 1000,
                timed_out=True,
                retry_count=max_attempts
            )
        return AgentResponse(
            reply="", error=last_error or "unknown error",
            latency_ms=0, retry_count=max_attempts
        )

    async def run_eval(self, agent_url: str, agent_name: str = "Unknown",
                       interface_type: str = "auto") -> EvalResult:
        """运行完整评测"""
        # 自动检测接口类型
        if interface_type == "auto":
            interface_type = await self._detect_interface(agent_url)

        adapter = self._get_adapter(interface_type, agent_url)

        result = EvalResult(
            agent_name=agent_name,
            agent_url=agent_url,
            interface_type=interface_type,
            total_questions=len(self.benchmark["questions"]),
            completed=0, failed=0, timed_out=0,
            total_latency_ms=0, avg_latency_ms=0
        )

        for question in self.benchmark["questions"]:
            timeout = self._get_timeout(question)
            response = await self._send_with_retry(adapter, question, timeout)

            qr = QuestionResult(
                question_id=question["id"],
                question=question,
                response=response,
                success=bool(response.reply and not response.timed_out)
            )

            if response.timed_out:
                result.timed_out += 1
                result.failed += 1
            elif response.reply:
                result.completed += 1
                result.total_latency_ms += response.latency_ms
            else:
                result.failed += 1

            result.question_results.append(qr)

        if result.completed > 0:
            result.avg_latency_ms = result.total_latency_ms / result.completed

        return result

    async def _detect_interface(self, agent_url: str) -> str:
        """自动检测 Agent 接口类型"""
        # 先试 OpenAI 格式
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{agent_url.rstrip('/')}/v1/chat/completions",
                    json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
                )
                if resp.status_code < 500:
                    return "openai"
        except Exception:
            pass

        # 再试 REST 格式
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{agent_url.rstrip('/')}/eval",
                    json={"test_id": "probe", "user_message": "hi"},
                )
                if resp.status_code < 500:
                    return "rest"
        except Exception:
            pass

        # 默认 REST
        return "rest"


# 同步包装器（MVP 不需要 Celery 时使用）
def run_eval_sync(agent_url: str, agent_name: str = "Unknown",
                  interface_type: str = "auto") -> EvalResult:
    """同步运行评测（适合 MVP / 本地开发）"""
    evaluator = AgentEvaluator()
    return asyncio.run(evaluator.run_eval(agent_url, agent_name, interface_type))
