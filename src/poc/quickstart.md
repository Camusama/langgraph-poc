# POC 快速上手指南

本指南帮助你一次跑通三个 POC 层（集成层 + 记忆层 + 任务层）。均为最简实现，默认本地运行。

## 目录结构速览
- `src/poc/integration/`：Mongo 持久化的 CRUD（主题、成员、上下文）
- `src/poc/memory/`：内存版“超级上下文”与个性化视图
- `src/poc/task/`：基于会议 delta 的任务/提醒规则引擎

## 环境准备
1. Python 3.12，建议按仓库 README 用 `uv` 安装依赖：`uv sync`
2. MongoDB：本地或云端均可。若本地，默认连接 `mongodb://localhost:27017`。
3. 环境变量：如需自定义 Mongo，设置 `MONGO_URI`，例如：
   ```bash
   $env:MONGO_URI="mongodb://localhost:27017"   # PowerShell
   export MONGO_URI="mongodb://localhost:27017" # Bash
   ```

## 启动服务
```bash
uv run server.py  # FastAPI 默认 http://localhost:8000
```
启动后主要 POC 路由：
- 集成层：`/api/poc/integration`
- 记忆层：`/api/poc/memory`
- 任务层：`/api/poc/task`

## 典型串联流程（推荐按此顺序调用）
### 1) 集成层：创建主题并写入上下文
1. 创建主题  
   `POST /api/poc/integration/topics`
   ```json
   {
     "title": "AI 工作圈 POC",
     "description": "演示用",
     "goal": "跑通三层联动"
   }
   ```
   记录返回的 `topic_id`。

2. 添加成员  
   `POST /api/poc/integration/topics/{topic_id}/members`
   ```json
   {
     "user_id": "alice",
     "display_name": "Alice",
     "role": "pm",
     "responsibilities": ["需求", "风险"]
   }
   ```
   再添加一名开发：
   ```json
   {
     "user_id": "bob",
     "display_name": "Bob",
     "role": "fe",
     "responsibilities": ["前端", "UI"]
   }
   ```

3. 写入上下文片段（模拟外部信号）  
   `POST /api/poc/integration/topics/{topic_id}/context`
   ```json
   {
     "author": "alice",
     "text": "后端接口可能延期，需要评估影响",
     "tags": ["risk", "backend"],
     "source": "slack-thread-123"
   }
   ```

> 集成层只是存储，不影响后续 POC 的内存版；后续可替换记忆层的存储为 Mongo。

### 2) 记忆层：创建主题 + ingest 会议 delta + 获取个人视图
> 记忆层当前是纯内存实现，与集成层数据不自动同步。这里单独演示它的接口；新增 `ingest_raw` 支持直接喂会议原文，由 LLM 生成结构化 delta。

1. 创建主题  
   `POST /api/poc/memory/topics`
   ```json
   {
     "title": "AI 工作圈 POC",
     "goal": "验证记忆层",
     "members": [
       {"user_id": "alice", "display_name": "Alice", "role": "pm", "responsibilities": ["需求", "风险"]},
       {"user_id": "bob", "display_name": "Bob", "role": "fe", "responsibilities": ["前端", "UI"]}
     ]
   }
   ```
   记录 `topic_id`。

2. 写入会议增量  
   `POST /api/poc/memory/topics/{topic_id}/ingest`
   ```json
   {
     "meeting_id": "kickoff-001",
     "summary": "讨论了前端截止时间和新风险。",
     "facts": [{"text": "前端需要支持新接口", "actors": ["bob"]}],
     "decisions": [{"text": "UI 走最小可用方案", "actors": ["alice"]}],
     "risks": [{"text": "后端接口可能延迟", "tags": ["backend"]}],
     "tasks": [
       {"title": "更新前端接口定义", "owner": "bob", "due": "2025-01-10", "notes": "等待后端 schema"}
     ],
     "notes": [{"text": "需要下周再同步一次"}]
   }
   ```

3. 获取个性化视图  
   `GET /api/poc/memory/topics/{topic_id}/view/{user_id}`
   - `highlights`、`action_items`、`risks`、`decisions`、`mentions` 将根据成员职责/actors/owner 做简单相关性过滤。

### 3) 任务层：基于会议 delta 生成动作（通知/提醒）
> 任务层调用同样的会议 delta 结构，并复用记忆层（内存版）以更新上下文后生成动作列表。默认先用 LLM 进行动作推理，解析失败时再回退到规则。

`POST /api/poc/task/topics/{topic_id}/process`
```json
{
  "meeting_id": "kickoff-001",
  "summary": "讨论了前端截止时间和新风险。",
  "facts": [{"text": "前端需要支持新接口", "actors": ["bob"]}],
  "decisions": [{"text": "UI 走最小可用方案", "actors": ["alice"]}],
  "risks": [{"text": "后端接口可能延迟", "tags": ["backend"]}],
  "tasks": [
    {"title": "更新前端接口定义", "owner": "bob", "due": "2025-01-10", "notes": "等待后端 schema"}
  ],
  "notes": [{"text": "需要下周再同步一次"}]
}
```
返回：
- `topic`：记忆层更新后的状态（内存版）
- `actions`：规则化动作列表，示例：
  - 通知任务 owner：`新任务: 更新前端接口定义，截止 2025-01-10（来自会议 kickoff-001）`
  - 风险提醒发给 pm/owner/admin：`风险提醒: 后端接口可能延迟（会议 kickoff-001）`
  - 决策通知决策的 actors（若缺省则全员）。

## 常见问题
- **重启后数据丢失**：记忆层与任务层当前都是内存存储；集成层在 Mongo 中是持久的。后续可将记忆层/任务层接到 Mongo 以持久化。
- **端口占用**：默认 8000，可自行修改 `server.py` 启动参数或用环境变量 `UVICORN_PORT`。
- **缺少依赖**：确保 `uv sync` 后存在 `pymongo` 等依赖。

## 下一步可以做什么
- 将记忆层的 `MemoryStore` 换成基于 Mongo 的实现，复用集成层的数据。
- 把任务层 `actions` 接到实际渠道（Slack/Zoom/Webhook/Jira 等）。
- 加入简单的更新/删除接口，或编写 MCP tool 直接封装 `IntegrationService`/`MemoryService`/`TaskOrchestrator`。 

## 一键演示（可视化）
- 文件：`src/poc/quick-demo.html`
- 用法：直接双击浏览器打开，保持后端 `uv run server.py` 运行，点击“一键执行全部步骤”即可依次调用集成层、记忆层（含 LLM 抽取）、任务层并在页面显示返回结果。
   或直接喂会议原文（由 LLM 抽取 delta）：  
   `POST /api/poc/memory/topics/{topic_id}/ingest_raw`
   ```json
   {
     "meeting_id": "kickoff-001",
     "transcript": "Alice: 我们要改前端接口... Bob: 需要后端 schema ..."
   }
   ```
