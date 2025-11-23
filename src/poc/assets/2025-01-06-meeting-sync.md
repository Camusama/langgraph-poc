# Agent Sphere 同步会摘要（2025-01-06）

与会：marquez.yang@zoom.us，max.lin@zoom.us

## 关键事实
- Mongo 集合与索引已验证：topics(topic_id unique)、members(topic_id+user_id unique)、contexts(topic_id index)。
- LLM ingest_raw 初步测试可用，需对长转录分段后再喂。

## 决策
- Actions 优先使用 LLM 推理，若解析失败则回退规则并在日志记录。
- 集成层暂不做删除接口，后续按需补。

## 风险
- 长文本超过 prompt 限制 → 需要分片策略或截断。
- 角色标签缺失会降低相关性判断精度。

## 任务
- Max：编写转录分段小脚本，限制每段 800-1000 token（截止 1/09）。
- Marquez：在 quick-demo.html 加一个“仅跑记忆层 ingest_raw”按钮便于测试（截止 1/09）。
