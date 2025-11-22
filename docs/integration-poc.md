# 集成层 POC 用法

本迭代提供了最简单的“集成层”CRUD：基于 MongoDB 存储主题、成员、上下文片段。作为后续与 Zoom/Slack/Webhook 对接的基础。代码在 `src/poc/integration/`。

> 说明：为了快速落地，仅实现增删改查（这里主要是增+查），并通过 FastAPI 暴露。MCP tool 可直接复用这些 Service 方法。

## 前置

- 环境变量：`MONGO_URI`（默认 `mongodb://localhost:27017`）
- 数据库：`langmanus_poc`

## 运行

```bash
uv run server.py  # FastAPI 默认 8000
```

## API 一览

`/api/poc/integration`

1) 创建主题  
`POST /topics`
```json
{
  "title": "AI 工作圈 POC",
  "description": "集成层示例",
  "goal": "持久化超级上下文并对外暴露 CRUD"
}
```
返回包含 `topic_id`。

2) 列出/查看主题  
- `GET /topics`  
- `GET /topics/{topic_id}`

3) 添加成员  
`POST /topics/{topic_id}/members`
```json
{
  "user_id": "alice",
  "display_name": "Alice",
  "role": "pm",
  "responsibilities": ["需求", "风险"]
}
```
查看成员：`GET /topics/{topic_id}/members`

4) 写入上下文片段  
`POST /topics/{topic_id}/context`
```json
{
  "author": "alice",
  "text": "后端接口可能延期，需要评估影响",
  "tags": ["risk", "backend"],
  "source": "meeting-kickoff"
}
```
查看上下文：`GET /topics/{topic_id}/context?limit=50`

## 说明

- 目前不做删除/更新，保证简单。必要时可在 Service 上补充对应方法和接口。
- 集合与索引：
  - `topics(topic_id unique)`
  - `members(topic_id+user_id unique)`
  - `contexts(topic_id index)`
- MCP 工具可直接包装 `IntegrationService` 的方法（Topic/Member/Context 的 CRUD）。当前未加入运行时目录，以保持 POC 轻量。***
