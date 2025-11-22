# 任务层 POC 用法

本次迭代实现了一个极简“任务管理 / 项目管理”层，基于会议 delta 调用记忆层，并输出规则化的动作列表（谁需要被通知、通知内容）。逻辑很简单，目的是示范任务层入口和动作形态。
新增：默认先用 LLM 做动作推理，失败时回退到规则。

## 运行

```bash
uv run server.py  # FastAPI 默认 8000
```

依赖上一次的记忆层 POC（内存存储）。

## 基本流程

1) 先用记忆层创建主题（同 `docs/memory-poc.md`）。
2) 调用任务层接口处理会议 delta，得到：
   - 更新后的 topic 状态（来自记忆层）
   - `actions` 列表：面向具体用户的提醒/通知

## API

### 处理会议 delta 并生成动作

 `POST /api/poc/task/topics/{topic_id}/process`

请求体沿用记忆层的 `MeetingDelta` 结构：

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

示例返回（截断）：

```json
{
  "topic": { "...": "更新后的 topic 状态（含超级上下文）" },
  "actions": [
    {
      "action_type": "notify",
      "target_user": "bob",
      "message": "新任务: 更新前端接口定义，截止 2025-01-10（来自会议 kickoff-001）",
      "severity": "info",
      "tags": []
    },
    {
      "action_type": "notify",
      "target_user": "alice",
      "message": "风险提醒: 后端接口可能延迟（会议 kickoff-001）",
      "severity": "warning",
      "tags": ["backend"]
    }
  ]
}
```

## 内置规则（简单版）

- `tasks` → 给 owner 一条 `info` 通知。
- `risks` → 给角色为 `pm` / `owner` / `admin` 的成员发 `warning`，如果没有这类角色则通知全部成员。
- `decisions` → 通知决策中的 `actors`，若未提供则默认通知全员。

后续可以将这些动作交给集成层（Slack/Zoom/Webhook/Jira）执行；当前仅返回数据结构。

### LLM 动作推理
- Prompt 包含主题信息、成员角色、最近摘要和当前会议 delta。
- 输出结构：数组元素 `{"action_type": "notify|ask|escalate", "target_user": "...或all", "message": "...", "severity": "info|warning|critical", "tags": []}`。
- 如果解析失败则自动回退规则。***
