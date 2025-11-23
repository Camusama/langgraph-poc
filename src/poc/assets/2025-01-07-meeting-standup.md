# Agent Sphere 站会摘要（2025-01-07）

与会：max.lin@zoom.us，otis.shou@zoom.us，gamego.yang@zoom.us（marquez 缺席）

## 关键事实
- 分段脚本初版完成：每段 900 token 左右，逐段送入 ingest_raw。
- 任务层 LLM 对于分段后的 delta 可以逐段产出 actions，然后合并。
- 前端 demo 需要展示 meeting_id 与 “why”。

## 决策
- 暂不修改 Mongo 结构；“why” 信息先放在动作 message 里，后续再结构化。
- 没有关键干系人参与的会议，仍要在动作中标明“因缺席，请确认”。

## 风险
- 分段后上下文丢失可能导致重复提醒，需要简单去重或合并。
- 缺席干系人的风险提醒可能被忽略，需要提高 severity。

## 任务
- Max：在分段脚本中加入 dedup 逻辑（截止 1/09）。
- Otis：设计 “缺席提醒” 文案模板（截止 1/09）。
