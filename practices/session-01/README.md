# Session 1 练习二：诗词聊天机器人操作说明

程序依据 [你的架构设计](poem-bot-design.md) 实现，作业要求见 [老师的说明](session-01-poem-bot.md)。原始设计图与作业文件均保留不变。

## 快速运行

首次克隆请先按[仓库首页](../../README.md)创建虚拟环境并安装依赖，再在项目根目录的 PowerShell 中执行下列命令。

一次 Mock 测试（即使配置了密钥也不会请求真实模型）：

```powershell
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --mock --once "我很想念远方的朋友"
```

固定回答为：

```text
[Mock / Fallback：固定示例]
海内存知己，天涯若比邻。
```

共享模块还可能向标准错误输出一行 `[mock LLM]` 诊断，这是正常的离线提示。固定示例不会随输入变化，也不代表真实模型请求成功。

一次真实模型请求（使用现有课程配置）：

```powershell
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --once "离家很久，今晚格外思念故乡"
```

模型供应商与模型名由共享模块选择。作者验证时使用 DeepSeek；新克隆的仓库不含密钥，默认走离线模拟。共享模块的优先级仍为 OpenAI → Anthropic → DeepSeek → 无密钥模拟。新程序不直接读取或展示凭据内容，不创建独立模型客户端。

连续对话：

```powershell
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --mock
```

去掉 `--mock` 则按课程配置尝试真实请求。输入 `quit` 或 `exit` 退出；空行仅提示“请输入一句话。”并继续对话。每次独立处理一句话，不保存对话历史。

从脚本所在目录运行也可以：

```powershell
Set-Location practices/session-01
..\..\.venv\Scripts\python.exe -X utf8 poem_bot.py --mock --once "朋友即将远行"
```

## 输出架构图

从项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --diagram
```

只输出 Mermaid 源码并退出，不等待输入，不调用模型。`--diagram` 优先于 `--once` 和 `--mock`。可将输出复制到 Mermaid 编辑器，与自己的原始架构逐项对照。

**这是一份按实际代码核对的静态图，不是自动解析 Python 源码生成的图。** 图来自程序中的 `DIAGRAM` 常量，没有读取或复写原始设计文件。图补充展示了空输入、命令行分流与临时密钥恢复分支，核心处理链与原设计保持一致。

## 原始设计与代码对应

| 原始架构环节 | 程序中的对应实现 |
| --- | --- |
| 用户输入 → 程序入口 | `main()` 处理参数；`run_console()` 接收连续输入 |
| 消息清洗 | `clean_message_text()`：先去首尾空白，再去开头连续的 `<@UBOT>` 等大写字母/数字标记 |
| 构造 Prompt | `build_prompt()` 与 `SYSTEM_PROMPT`：理解含义与情绪，选择已有诗句，正常只输出诗句 |
| 统一 LLM 调用 | `handle_message()` 的非空分支始终调用已有 `call_llm_safe()` |
| 是否 Mock | 共享模块按密钥判断；`offline_mode()` 在 `--mock` 时临时移除本进程密钥以进入无密钥分支 |
| LLM 请求、API 失败兜底 | 完全由 `common/llm.py` 提供 |
| 固定示例并告知 Mock | `MOCK_REPLY` 作为 `mock` 参数交给共享接口，由共享接口返回 |
| 输出古诗词 | `main()` 或 `run_console()` 打印 `handle_message()` 的结果 |
| 课程配置依赖 | 导入共享模块时由其加载 `.env` / 环境变量；通过 `__file__` 找到 `course-demos` |

清洗示例：`"  <@UBOT> <@U123> 想念朋友  "` 变为 `"想念朋友"`；正文中的 `朋友 @小王` 或 `想念 <@UBOT>` 不会被删除。只有空白或开头提及标记的输入，清洗后提示输入，不调用模型。一次模式中的 `--once "quit"` 是普通单次输入；退出命令只适用于连续对话。

## 共享模块负责什么

已有 [common/llm.py](../../course-demos/common/llm.py) 提供配置加载、供应商选择、模型选择、SDK 调用、超时与重试、无密钥返回 mock、API 异常返回 fallback。新程序仅提供提示词、固定示例和控制台流程，不重复实现这些行为。

`--mock` 在共享模块导入、配置加载完成后，临时移除 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`，然后正常调用 `call_llm_safe()`。结束后通过 `finally` 恢复原有环境变量，包括原来未设置的状态；不会修改 `.env`，也不会重新加载配置。

真实调用失败时，共享模块可能先打印 `[fallback]` 诊断，再返回带显式标记的固定示例。程序不会依据供应商名称显示“请求成功”，也没有额外添加成功标签。

## 验证记录

2026-09-11 使用已有 Python 虚拟环境验证通过：

| 检查项 | 实测结果 |
| --- | --- |
| 首尾空白、连续开头提及、正文 @ 内容 | 按规则清洗，正文保留 |
| 空白或仅提及标记的输入 | 提示输入，不调用模型 |
| 已有密钥时强制 Mock | 仍经过共享接口的无密钥路径；未创建网络客户端 |
| 不同输入的 Mock 结果 | 均返回规定的固定示例 |
| 临时环境变量恢复 | 正常返回和异常离开后均恢复原状态 |
| `--diagram` | 只输出静态 Mermaid，不读取输入、不调用模型；优先于 `--once` |
| 项目根目录、脚本目录运行 | 两个位置的单次 Mock 均通过 |
| 连续输入、空行、quit / exit | 正常提示、回复与退出 |
| DeepSeek 真实请求 | 返回“露从今夜白，月是故乡明。” |
| DeepSeek 真实 API 错误兜底 | 无效模型触发 `BadRequestError`、HTTP 400，返回带标记的固定示例 |

真实成功通过观察共享 `call_llm()` 实际返回、未抛异常、且结果不是固定示例确认，不是只看 `llm_provider()`。失败测试在独立测试进程中临时设置 `DEMO_MODEL=session01-intentionally-invalid-model`；两次真实请求测试临时使用 30 秒超时、0 次重试，均通过已有共享接口完成。诊断只输出诗句与错误类型/状态码，不展示凭据。

以上为作业开发时的验证记录；测试没有修改配置文件、共享模块、原始设计或作业说明。公开提交不包含作者的本地凭据。
