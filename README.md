# 🔬 BenchAgent — AI Agent Benchmark Platform

**The first open-source benchmark platform for AI agents.** Submit your customer service agent, auto-run 25 scenario tests, get a 4-dimension score report. Think "AnTuTu for AI agents" — fair, automated, transparent.

🌐 [frontend-tau-liard-21.vercel.app](https://frontend-tau-liard-21.vercel.app)

---

## 🏆 Live Leaderboard

12 well-known AI models benchmarked — see how they compare:

| Rank | Model | Overall |
|:--:|------|:--:|
| 🥇 | **Qwen 2.5** | 7.1 |
| 🥈 | **Claude Opus** | 6.9 |
| 🥉 | **Gemini 1.5 Pro** | 6.8 |
| 4 | Mistral Large | 6.5 |
| 5 | GPT-4o | 6.1 |
| 6 | Claude 3.5 Sonnet | 6.2 |
| 7 | Llama 3.1 70B | 6.4 |
| 8 | DeepSeek V3 | 5.9 |
| 9 | Grok-2 | 6.0 |
| 10 | Command R+ | 5.6 |

*Updated 2026-08-07. [View full leaderboard →](https://frontend-tau-liard-21.vercel.app)*

---

## 📊 How It Works

```
You submit your Agent API → BenchAgent runs 25 test cases → DeepSeek judges every response → You get a 4D score report
```

### Scoring Dimensions

| Dimension | Weight | Method | Description |
|-----------|:------:|--------|-------------|
| **Accuracy** | 45% | LLM-as-Judge | Does it understand the scenario and give correct answers? |
| **Anti-Hallucination** | 25% | LLM-as-Judge | Does it fabricate information, order numbers, or policies? |
| **Latency** | 15% | Platform-measured | Real response time from request to complete reply |
| **Safety Rejection** | 15% | Rule-based | Can it correctly reject prompt injection and unsafe requests? |

### Test Suite

25 real-world customer service scenarios across 6 categories:
- 📦 Order tracking
- 🔄 Returns & refunds
- 🛍️ Product inquiries
- 👤 Account management
- 😤 Complaint handling
- 🛡️ Edge cases (empty messages, prompt injection, gibberish)

[View full test suite →](https://github.com/YensenHo/benchagent-backend/blob/main/benchmarks/customer_service_v1.json)

---

## 🚀 Submit Your Agent

### 1. Your agent only needs ONE endpoint:

**Option A — OpenAI Compatible** (recommended):
```
POST /v1/chat/completions
Request:  {"model": "...", "messages": [{"role": "user", "content": "..."}]}
Response: {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
```

**Option B — Standard REST**:
```
POST /eval
Request:  {"user_message": "...", "test_id": "cs_001"}
Response: {"reply": "...", "tool_calls": [...]}
```

> 📖 Full spec: [AGENT_SPEC.md](https://github.com/YensenHo/benchagent-backend/blob/main/AGENT_SPEC.md)

### 2. Submit to BenchAgent:

```bash
curl -X POST https://web-production-d097c.up.railway.app/api/eval/submit \
  -H "Content-Type: application/json" \
  -d '{
    "agent_url": "https://your-agent.com",
    "agent_name": "My Customer Bot v1.0",
    "interface_type": "openai"
  }'
```

### 3. Get your report:

```bash
# Check status
curl https://web-production-d097c.up.railway.app/api/eval/status/{eval_id}

# Get full report
curl https://web-production-d097c.up.railway.app/api/eval/report/{eval_id}
```

Or use the web UI at [frontend-tau-liard-21.vercel.app](https://frontend-tau-liard-21.vercel.app).

---

## 🧱 Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend (Vercel)                               │
│  Single HTML + Chart.js — Submit · Report · LB   │
└──────────────────┬──────────────────────────────┘
                   │ POST /api/eval/submit
                   ▼
┌──────────────────────────────────────────────────┐
│  Backend (FastAPI · Railway)                      │
│                                                   │
│  POST /api/eval/submit  → Submit Agent            │
│  GET  /api/eval/status  → Poll Progress           │
│  GET  /api/eval/report  → Get Report              │
│  GET  /api/leaderboard  → Top N Agents            │
│  POST /api/search       → Search Agents by Query  │
│                                                   │
│  ┌─────────┐  ┌──────────┐  ┌────────────────┐   │
│  │Evaluator│  │  Judge    │  │   Benchmark    │   │
│  │ 25 calls│──│ LLM-as-   │──│ customer_svc   │   │
│  │ per sub │  │ Judge     │  │ 25 scenarios   │   │
│  └─────────┘  └──────────┘  └────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python · FastAPI · httpx |
| Frontend | Single HTML/CSS/JS · Chart.js (no framework) |
| LLM Judge | DeepSeek Chat API (GPT-4o-mini compatible) |
| Deployment | Railway (backend) · Vercel (frontend) |
| Database | In-memory dict (MVP) → SQLite (planned) |

---

## 📂 Project Structure

```
backend/
├── main.py                 # FastAPI entry: submit / status / report / search
├── evaluator.py            # Core engine: runs 25 tests against Agent API
├── judge.py                # LLM scoring + latency timer + safety rules
├── adapters/               # OpenAI / REST interface adapters
│   ├── openai_adapter.py
│   └── rest_adapter.py
├── benchmarks/
│   └── customer_service_v1.json  # 25 test scenarios
└── scripts/
    └── populate_leaderboard.py   # Fill leaderboard with benchmark data

frontend/
└── index.html              # Full SPA: Submit · Report · Leaderboard · Search
                            # EN/中文 i18n, Chart.js radar, localStorage

public-agents/
└── agent.py                # 12-brand-name model server (deploy to Render)
```

---

## 🔧 Quick Start (Local)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

export LLM_JUDGE_API_KEY="your-deepseek-key"
export LLM_JUDGE_MODEL="deepseek-chat"
export LLM_JUDGE_BASE_URL="https://api.deepseek.com/v1"

unset PYTHONPATH && .venv/bin/python3 main.py
# → http://localhost:8010
```

---

## 📈 Roadmap

- [x] 25-scenario benchmark suite
- [x] 4-dimension scoring (Accuracy / Hallucination / Latency / Safety)
- [x] EN/中文 i18n
- [x] Agent search by capability description
- [ ] SQLite persistence (leaderboard survives restart)
- [ ] Custom test suite upload (enterprise)
- [ ] Agent SDK (one-line integration)
- [ ] More verticals: finance, SaaS, logistics
- [ ] Public API

---

## ⭐ Star History

If you find this useful, please ⭐ the repo — it helps more people discover agent evaluation as a practice.

---

## 📄 License

MIT — build on it, fork it, ship it.
