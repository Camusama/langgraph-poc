# Agent Sphere 同步会摘要（2025-01-08）

与会：marquez.yang@zoom.us，otis.shou@zoom.us，gamego.yang@zoom.us（max 缺席）

## 关键事实
- LLM actions 支持 “ask” 类型，用于确认缺席人员的待办。
- 分段脚本已在内部测试：两段转录生成的 actions 可合并，缺席者会收到 “请确认” 提醒。

## 决策
- 对缺席的 owner，动作文案加 “[缺席确认]” 前缀，severity=warning。
- Gamego 的前端会显示 action.source（meeting_id），方便追溯。

## 风险
- 如果分段过多，动作列表过长，需要 top-N 策略。
- 长期未确认的 “ask” 需要二次提醒，暂未实现。

## 任务
- Otis：起草 top-N 策略（只保留最关键的 8 条动作）（截止 1/10）。
- Marquez：用新规则跑一遍 quick-demo，检验缺席提醒是否出现（截止 1/10）。
- Marquez：安排一次 15min 风险确认 touch-base（缺席者需要确认），截止 1/10 上午。
