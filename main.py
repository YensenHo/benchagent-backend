"""
BenchAgent API — FastAPI 入口
POST /api/eval/submit  → 提交Agent评测
GET  /api/eval/status/{id} → 查询进度
GET  /api/eval/report/{id} → 获取报告
"""
import os, uuid, json, logging
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio

from evaluator import AgentEvaluator, run_eval_sync, EvalResult
from judge import LLMJudge, LatencyJudge, SafetyJudge, ReportBuilder, EvalReport, JudgeScores

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BenchAgent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 简单内存存储（MVP阶段，后续换 SQLite/Postgres）
_store = {}


class SubmitRequest(BaseModel):
    agent_url: str
    agent_name: str = "Unknown Agent"
    interface_type: str = "auto"  # auto, openai, rest


class EvalStatus(BaseModel):
    eval_id: str
    status: str  # pending, running, completed, failed
    agent_name: str
    submitted_at: str
    completed_at: Optional[str] = None
    report: Optional[dict] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/eval/submit")
async def submit_eval(req: SubmitRequest):
    """提交Agent评测"""
    eval_id = str(uuid.uuid4())[:8]

    _store[eval_id] = {
        "status": "running",
        "agent_name": req.agent_name,
        "agent_url": req.agent_url,
        "interface_type": req.interface_type,
        "submitted_at": datetime.now().isoformat(),
        "report": None,
        "error": None
    }

    # 异步运行评测
    asyncio.create_task(_run_eval_task(eval_id, req))

    return {"eval_id": eval_id, "status": "running"}


@app.get("/api/eval/status/{eval_id}")
def get_status(eval_id: str):
    """查询评测进度"""
    if eval_id not in _store:
        raise HTTPException(status_code=404, detail="评测ID不存在")
    rec = _store[eval_id]
    return EvalStatus(
        eval_id=eval_id,
        status=rec["status"],
        agent_name=rec["agent_name"],
        submitted_at=rec["submitted_at"],
        completed_at=rec.get("completed_at"),
        report=rec.get("report")
    )


@app.get("/api/eval/report/{eval_id}")
def get_report(eval_id: str):
    """获取评测报告（JSON）"""
    if eval_id not in _store:
        raise HTTPException(status_code=404, detail="评测ID不存在")
    rec = _store[eval_id]
    if rec["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"评测尚未完成，当前状态: {rec['status']}")
    return rec["report"]


async def _run_eval_task(eval_id: str, req: SubmitRequest):
    """后台执行评测"""
    try:
        # 1. 运行评测引擎
        evaluator = AgentEvaluator()
        eval_result = await evaluator.run_eval(
            agent_url=req.agent_url,
            agent_name=req.agent_name,
            interface_type=req.interface_type
        )

        # 2. 逐题评分
        llm_judge = LLMJudge()
        latency_judge = LatencyJudge()
        safety_judge = SafetyJudge()

        judge_scores = []
        for qr in eval_result.question_results:
            # LLM 评分（准确率 + 幻觉）
            llm_scores = await llm_judge._score_async(
                qr.question, qr.response.reply,
                qr.response.latency_ms, qr.response.timed_out,
                qr.response.tool_calls
            )

            # 延迟评分
            lat_scores = latency_judge.score(
                qr.question, qr.response.reply,
                qr.response.latency_ms, qr.response.timed_out,
                qr.response.tool_calls
            )

            # 安全评分
            saf_scores = safety_judge.score(
                qr.question, qr.response.reply,
                qr.response.latency_ms, qr.response.timed_out,
                qr.response.tool_calls
            )

            # 合并（JudgeScores 已在文件顶部导入）
            combined = JudgeScores(
                question_id=qr.question_id,
                accuracy=llm_scores.accuracy,
                hallucination=llm_scores.hallucination,
                latency_score=lat_scores.latency_score,
                safety_score=saf_scores.safety_score,
                reason=llm_scores.reason,
                hallucination_flag=llm_scores.hallucination_flag
            )
            # 加权总分
            combined.overall = round(
                combined.accuracy * 0.45 +
                combined.hallucination * 0.25 +
                combined.latency_score * 0.15 +
                combined.safety_score * 0.15,
                1
            )
            judge_scores.append(combined)

        # 3. 生成报告
        benchmark = evaluator.benchmark
        report = ReportBuilder.build(eval_result, judge_scores, benchmark["scoring"])

        # 4. 存储
        _store[eval_id]["status"] = "completed"
        _store[eval_id]["completed_at"] = datetime.now().isoformat()
        _store[eval_id]["report"] = {
            "agent_name": report.agent_name,
            "overall_score": report.overall_score,
            "dimensions": {
                "accuracy": report.accuracy_avg,
                "hallucination": report.hallucination_avg,
                "latency": report.latency_avg,
                "safety": report.safety_avg
            },
            "stats": {
                "total_questions": report.total_questions,
                "completed": report.completed,
                "failed": report.failed,
                "timed_out": report.timed_out,
                "avg_latency_ms": report.avg_latency_ms
            },
            "per_question": [
                {
                    "id": s.question_id,
                    "accuracy": s.accuracy,
                    "hallucination": s.hallucination,
                    "latency": s.latency_score,
                    "safety": s.safety_score,
                    "overall": s.overall,
                    "hallucination_flag": s.hallucination_flag,
                    "reason": s.reason
                }
                for s in judge_scores
            ]
        }

        logger.info(f"评测完成: {eval_id} 总分={report.overall_score}")

    except Exception as e:
        logger.error(f"评测失败: {eval_id} error={e}")
        _store[eval_id]["status"] = "failed"
        _store[eval_id]["error"] = str(e)


@app.get("/api/leaderboard")
def leaderboard(limit: int = 20):
    """获取排行榜：已完成评测的 Agent 按总分降序"""
    completed = [
        {"eval_id": eid, **rec}
        for eid, rec in _store.items()
        if rec.get("status") == "completed" and rec.get("report")
    ]
    # 按总分降序
    completed.sort(key=lambda x: x["report"]["overall_score"], reverse=True)
    top = completed[:limit]
    return {
        "total": len(completed),
        "top": [
            {
                "rank": i + 1,
                "agent_name": r["report"]["agent_name"],
                "overall_score": r["report"]["overall_score"],
                "dimensions": r["report"]["dimensions"],
                "completed_at": r.get("completed_at", ""),
            }
            for i, r in enumerate(top)
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
