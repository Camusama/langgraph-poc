# 记忆层 POC 用法

本次迭代实现了一个最简版本的“超级上下文”层，放在 `src/poc/memory`。完全内存存储，重启会丢失，目的是演示数据形态和个性化输出。

## 运行

```bash
uv run server.py  # FastAPI 默认端口 8000
```

## 核心能力

- 创建主题（带成员与职责）
- 接收一场会议的结构化 delta（facts/decisions/risks/tasks/notes）并写入超级上下文
- 针对某个用户输出个性化视图（action items、风险、决策、最近高亮）
- 新增：支持直接输入会议原文，由 LLM 生成结构化 delta（`ingest_raw`）

## API 速查

1) 创建主题：`POST /api/poc/memory/topics`

```json
{
  "title": "AI 工作圈 POC",
  "goal": "验证记忆层和任务层交互",
  "members": [
    {"user_id": "alice", "display_name": "Alice", "role": "PM", "responsibilities": ["需求", "风险"]},
    {"user_id": "bob", "display_name": "Bob", "role": "FE", "responsibilities": ["前端", "UI"]}
  ]
}
```

返回值里包含 `topic_id`，后续接口使用。

2) 写入会议增量：`POST /api/poc/memory/topics/{topic_id}/ingest`

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

3) 获取个性化视图：`GET /api/poc/memory/topics/{topic_id}/view/{user_id}`

返回字段：`highlights`、`action_items`、`risks`、`decisions`、`mentions`。

4) 直接喂会议原文，让 LLM 产出 delta：`POST /api/poc/memory/topics/{topic_id}/ingest_raw`
```json
{
  "meeting_id": "kickoff-001",
  "transcript": "Alice: 我们要改前端接口... Bob: 需要后端 schema ..."
}
```

5) 列表/查看主题：
- `GET /api/poc/memory/topics`
- `GET /api/poc/memory/topics/{topic_id}`

## 说明

- 相关性算法非常简单：命中 `actors`、任务 owner，或文本包含成员的职责关键词即视为“与我相关”。
- `recent_notes` 保留最近 10 条会议摘要，便于任务层后续调用。
- 未来接入集成层（Mongo）时，可以把 `MemoryService` 底层替换为持久化实现。
- LLM 配置沿用项目默认的 `basic` 模型（环境变量见 README）；解析失败时会返回 400。
