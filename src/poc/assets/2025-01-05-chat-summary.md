# Agent Sphere 群聊当日总结（2025-01-05）

参与人：marquez.yang@zoom.us，max.lin@zoom.us

- 确认 Agent Sphere 目标：先落地会议/聊天汇总到超级上下文，后续接任务层。
- 商定数据源：Zoom 会议转录 + Slack 群聊摘要，先用内置 POC API 模拟。
- 技术栈：Memory 层用内存版，后续切换 Mongo；Task 层先 LLM 推理 + 规则兜底。
- 待办：
  - Max：准备一段示例转录供 ingest_raw 体验（截止 1/06）。
  - Marquez：检查 MONGO_URI 配置与端口占用（截止 1/06）。
