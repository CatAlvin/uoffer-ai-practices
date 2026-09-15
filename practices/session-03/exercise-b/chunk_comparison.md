# L3 练习 B：Single 与 Map-Reduce 比较

> **复核状态：已由吴博涵完成核对。** 本报告依据保存的课堂原文、真实 Map/Reduce 原始输出和练习 A 的 Single 原始输出形成。

## 1. 实验设置

- 固定输入：复用练习 A 保存的完整 `input_snapshot.json`，没有使用 Single 摘要代替原文。
- 输入快照 SHA-256（规范化 JSON）：`8ad6dced2c94ee4656f2eb9238bb7d40e519c92d12a8e18c254159e476effe8a`。
- 消息数量：1 条合并长消息，正文内部包含 09:00—10:40 的多人模拟讨论。
- 数据来源：`source=manifest_replay`。
- 来源标识：`demo:manifest/C_DEMO/1700000000.000001`。
- 受众：`engineer`。
- 供应商 / 模型：DeepSeek / `deepseek-chat`。
- 模式：真实模型调用；通过课程 `common.summarization.summarize()` 和 `common.llm.call_llm()` 执行，没有新建模型客户端。
- 策略：练习 A 为 `single`；本次为 `map-reduce`。
- 固定参数：`temperature=0.3`、`context_budget=32000`、`output_reserve=1500`、`chunk_tokens=4000`。
- 分块数：2 个 Map 片段，与预演一致。
- 正常路径：Map 1 → Map 2 → Reduce，共 3 次共享接口调用。
- 运行时间：2026-09-16 04:52:06—04:52:20（Asia/Shanghai），总耗时 13.625 秒。
- 实际命令：

```powershell
Set-Location '<uoffer-ai-practices 仓库目录>'
& ./.venv/Scripts/python.exe -B -X utf8 practices/session-03/exercise-b/run_exercise_b.py --run
```

三次调用都返回非空真实文本，`mock_callback_invoked=false`；没有预算超限、路径变化或自动重跑。练习 A 的 Single 没有重新调用。

## 2. Single 对照来源

Single 直接复用练习 A 的原始工程师版：

- 原始输出：`evidence/a/engineer.raw.txt`
- 对应实际请求：`evidence/a/engineer.request.json`
- 对应完整快照：`evidence/a/input_snapshot.json`
- Single 原始输出 SHA-256：`82d571a3b480ce1922a000f5e8678aa04381ee32991625133811a57cdd810d51`

执行前已确认 `engineer.raw.txt` 与 A 的 `engineer.result.json`、`summary_runs.jsonl` 对应同一快照和 Single 请求；当前课程 Prompt 重建结果与 A 保存的实际请求逐字段一致。因此本次没有重新生成 Single。

## 3. 分块参数、顺序与预算

课程函数使用 `estimate_tokens()` 估算预算；该函数实际返回 UTF-8 字节数，以下数值不是模型真实 token 数。

| 阶段 | 来源 | 输入预算估计 | system 估计 | 加上 1500 输出预留和 256 固定余量 | 结果 |
| --- | --- | ---: | ---: | ---: | --- |
| Map 1 | `demo:manifest/C_DEMO/1700000000.000001` | 3998 | 616 | 6370 / 32000 | 通过 |
| Map 2 | `demo:manifest/C_DEMO/1700000000.000001` | 3297 | 616 | 5669 / 32000 | 通过 |
| Reduce | 两份真实 Map 输出 | 5727 | 598 | 8081 / 32000 | 通过 |

每个 Map 输入均由课程代码添加外层 `[source ...]`。移除该包装后，两个片段按 1、2 顺序拼接与 A 的 Single `user` 输入逐字一致：没有复制、重排、overlap 或截断。老师当前实现按预算切最大字符前缀，分界落在 09:53 的一句话中间；本次未修改该行为。

Reduce 输入由两份实际 Map 原始输出按课程逻辑完整组成，保存内容与 `result.json` 的两个 partial 逐字一致。Reduce 调用前经过上述现有预算检查，没有删减 Map 输出以绕过预算。

## 4. Map / Reduce 原始产物

本次实验的必要证据保存在 `evidence/map-reduce/`；重新运行时生成内容写入本目录的 `run-results/`。

| 阶段 | 实际输入 | 完整原始输出 | 输出 SHA-256 |
| --- | --- | --- | --- |
| Map 1 | `evidence/map-reduce/map-01.input.txt` | `evidence/map-reduce/map-01.raw.txt` | `a5ae15ec0e54e601497624475df8c9c9ad36297a2a95a8143abd3d40e08eec4a` |
| Map 2 | `evidence/map-reduce/map-02.input.txt` | `evidence/map-reduce/map-02.raw.txt` | `a5809a6f6e31f83bf941cde6c833023681fc332e5e010269487df435a6247ee7` |
| Reduce | `evidence/map-reduce/reduce-01.input.txt` | `evidence/map-reduce/reduce-01.raw.txt` | `199742a31969297a6f5d95380c677b1f1f12dab5e1cd0fd79fa85bf560f2d91e` |

表中的文件是本次真实实验的原始输入和输出，没有改写摘要内容。

## 5. 事实链：回滚完成与服务恢复

### 5.1 原文

原文只取自 `evidence/a/input_snapshot.json`，来源标识为 `demo:manifest/C_DEMO/1700000000.000001`，没有把 Single 摘要当作原文。

原文内部时间和关键文本：

- 09:20，Bob：“回滚完成，所有实例都已经是 v2.3。”
- 09:21，Chen：“错误率从 8% 降到 3.1%，p99 降到 1.4s，但仍显著高于基线。请不要把‘回滚完成’写成‘事故恢复’。”
- 09:23，Alice：“当前状态是已回滚、部分缓解、尚未恢复。”
- 09:45，Chen：指标接近基线，但“现在还不能关闭事故”。
- 10:00，Chen：从 09:45 起连续十五分钟稳定，5xx 为 0.2%—0.3%，p99 为 430—480ms。
- 10:02，Alice：“确认服务已恢复”，并要求表述为“10:00 确认指标稳定，10:02 宣布恢复”。

这条事实链横跨两个片段：09:20—09:45 位于 Map 1，10:00—10:02 位于 Map 2，不是同一块。

### 5.2 Map 阶段

Map 1 输入位置：`evidence/map-reduce/map-01.input.txt` 第 18—20、30 行；Map 1 原始输出位置：`evidence/map-reduce/map-01.raw.txt` 第 14—16、24、32 行。

Map 1 保留了回滚完成与尚未恢复的区别：

> “09:20 Bob：回滚完成，所有实例为v2.3。”
> “09:21 Chen：错误率8%降至3.1%，p99降至1.4s，仍高于基线；未恢复。”
> “09:23 Alice：状态为已回滚、部分缓解、尚未恢复。”
> “09:45 Chen：……开始连续十五分钟观察，事故未关闭。”

Map 2 输入位置：`evidence/map-reduce/map-02.input.txt` 第 4—5 行；Map 2 原始输出位置：`evidence/map-reduce/map-02.raw.txt` 第 4—5、11、19 行。

Map 2 保留了真正恢复的证据和时间：

> “09:45—10:00 指标连续十五分钟稳定：5xx 维持 0.2%—0.3%，p99 430—480ms……”
> “10:02 确认服务已恢复；对外表述为‘10:00 确认指标稳定，10:02 宣布恢复’。”

因此 Map 阶段没有把 09:20 的回滚完成写成服务恢复。两个 partial 分别保留了恢复前和恢复后的状态。

### 5.3 Reduce 阶段

Reduce 实际输入保存在 `evidence/map-reduce/reduce-01.input.txt`，包含上述两份完整 Map 原始输出。Reduce 原始输出位于 `evidence/map-reduce/reduce-01.raw.txt`：

- 第 12—14 行再次写明 09:20 回滚完成、09:21 未恢复、09:23 部分缓解且尚未恢复。
- 第 22 行写明 09:45 仍在观察、事故未关闭。
- 第 26—27 行写明 09:45—10:00 指标连续稳定，并于 10:02 确认恢复。
- 第 35、37 行分别将“09:15—09:20 回滚至 v2.3”和“10:02 服务恢复已确认”列为不同事件。

Reduce 成功把跨块事实重新合并，时间和状态没有混淆。

### 5.4 Single 对照

A 的 `evidence/a/engineer.raw.txt` 第 9—10、16—18 行写明：

> “09:20 回滚完成，所有实例为v2.3。”
> “09:21 ……仍高于基线；未恢复。”
> “10:00 连续十五分钟稳定……”
> “10:02 确认服务恢复……”

Single 没有单独复述 09:23“部分缓解、尚未恢复”，但已经通过 09:21“未恢复”和 10:02“确认恢复”保留核心状态区别。当前没有复述 09:23 这一细节，不自动判定为结论错误。

## 6. 复核结论

对“回滚完成”与“服务恢复”的事实链，人工复核结论为 **一致，未观察到状态混淆**：

1. 原文明确区分 09:20 回滚完成、09:21/09:23 尚未恢复、09:45 仍不能关闭事故，以及 10:02 才确认恢复。
2. Map 1 保留恢复前状态，Map 2 保留恢复确认；相关事实虽然跨块，但没有在 Map 阶段发生状态错误。
3. Reduce 将两块按时间重新连接，明确保留 09:20 与 10:02 两个不同节点。
4. Single 也保留相同的核心区别。

这项结论只针对本次所选的一条事实链，且已由吴博涵完成人工复核。其他未纳入本事实链的内容是否存在遗漏、重复、内部矛盾或口径错误，不在本结论范围内。

## 7. 一个改进建议

建议在保持现有字节预算的前提下，让分块点向前回退到最近的完整句子或自然段边界。当前 1/2 块边界把 09:53 的一句话切成两半，Map 2 从“表达不准确……”开始，丢失该句前半部分的主语上下文。这个建议本轮没有实现，也没有追加模型验证。

## 8. 运行模式和限制

- 本次没有连接 Slack，没有修改老师源码、练习 A 或其他作业。
- 真实模型路径严格为 2 次 Map + 1 次 Reduce；共享接口调用次数为 3。
- `max_retries=1` 是沿用的 SDK 配置。课程日志没有记录实际 SDK 重试次数或底层 HTTP 请求次数，因此不能把 3 次共享接口调用解释为恰好 3 次 HTTP 请求。
- 日志未记录服务端 request ID、响应模型标识、真实 token 用量、finish reason 或费用，本报告不推测这些数值。
- 预算估算是 UTF-8 字节数，不是模型 tokenizer 的实际 token 数。
- 本报告只核对“回滚完成”和“服务恢复”这一条事实链；该事实链已由吴博涵完成人工复核，结论不扩大到其他输出或所有模型。

> **结论状态：已由吴博涵完成人工复核。**
