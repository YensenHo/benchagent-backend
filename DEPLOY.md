# BenchAgent — Railway 部署指南

## 方法一：GitHub 一键部署（推荐）

1. 把 backend/ 推到一个 GitHub 仓库
2. 打开 https://railway.app → New Project → Deploy from GitHub repo
3. 选择仓库，设置 Root Directory 为 `backend`
4. 在 Variables 中添加：
   ```
   LLM_JUDGE_API_KEY=sk-964767a3fbce4ccf9b0fa2ce41a6b03d
   LLM_JUDGE_MODEL=deepseek-chat
   LLM_JUDGE_BASE_URL=https://api.deepseek.com/v1
   ```
5. 部署完成后得到 `xxx.railway.app` 域名
6. 更新前端 `index.html` 中 localStorage 的 `benchagent_api_base` 为该域名

## 方法二：CLI 部署

```bash
# 安装 Railway CLI
brew install railway

# 登录
railway login

# 初始化
cd ~/agent-bench/backend
railway init

# 设置环境变量
railway variables set LLM_JUDGE_API_KEY=sk-964767a3fbce4ccf9b0fa2ce41a6b03d
railway variables set LLM_JUDGE_MODEL=deepseek-chat
railway variables set LLM_JUDGE_BASE_URL=https://api.deepseek.com/v1

# 部署
railway up
```

## 部署后

拿到 Railway 域名（如 `benchagent.railway.app`），然后：
1. 打开前端 `https://frontend-tau-liard-21.vercel.app`
2. 弹窗输入 `https://benchagent.railway.app`（不要带端口）
3. 前端自动记住，后续访问不再弹窗
