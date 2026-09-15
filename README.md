# Uoffer AI Practices

Uoffer AI training practices — Bohan Wu

本仓库用于提交 Uoffer AI 课程作业，目前包含 Session 1 和 Session 3 作业。

## 作业入口

| 内容 | 文件 |
| --- | --- |
| Task 1：原始架构设计 | [poem-bot-design.md](practices/session-01/poem-bot-design.md) |
| Task 2：Python 实现 | [poem_bot.py](practices/session-01/poem_bot.py) |
| Task 2：实现架构图 | [poem-bot-implementation.md](practices/session-01/poem-bot-implementation.md) |
| 操作说明与验证记录 | [Session 1 README](practices/session-01/README.md) |
| 课程练习说明 | [session-01-poem-bot.md](practices/session-01/session-01-poem-bot.md) |
| Session 3 练习 A | [同一快照，两类读者](practices/session-03/exercise-a/README.md) |
| Session 3 练习 B | [Single 与 Map-Reduce 比较](practices/session-03/exercise-b/README.md) |

实现保持“输入 → 清洗 → Prompt → 共享 `call_llm_safe()` → 输出诗句”的链路。支持本地连续对话、`--once`、强制离线 `--mock` 和静态架构图输出 `--diagram`。

## 快速开始

推荐 Python 3.12。在 Windows PowerShell 中执行：

```powershell
git clone https://github.com/CatAlvin/uoffer-ai-practices.git
Set-Location uoffer-ai-practices
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --mock --once "我很想念远方的朋友"
```

预期回答：

```text
[Mock / Fallback：固定示例]
海内存知己，天涯若比邻。
```

输出实现架构图：

```powershell
.\.venv\Scripts\python.exe -X utf8 practices/session-01/poem_bot.py --diagram
```

这是按代码核对的静态 Mermaid，不是自动解析源码所得；原始设计图单独保留。

macOS / Linux 的对应命令：

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python practices/session-01/poem_bot.py --mock --once "我很想念远方的朋友"
```

## 可选：真实模型

离线运行无需密钥。需要真实调用时，在本地复制一次空模板：

```powershell
if (-not (Test-Path 'course-demos/.env')) {
    Copy-Item course-demos/.env.example course-demos/.env
}
```

自行在本地配置 `DEEPSEEK_API_KEY` 或其他支持的模型密钥，然后去掉 `--mock`。供应商选择、超时、重试与错误兜底均沿用共享模块。正常模型回答只输出诗句；无密钥或调用失败则输出带标记的固定示例。

`requirements.txt` 引用 Session 1 所需的 `python-dotenv`、`openai` 依赖，版本取自本次已验证的环境。若选择 Anthropic，需另行安装 `anthropic`。本作业不需要 Slack、Flask 或数据库。

## 文件与来源

```text
uoffer-ai-practices/
├── README.md
├── .gitignore
├── requirements.txt
├── practices/session-01/       作业设计、程序、说明和实现图
└── course-demos/
    ├── .env.example            仅空配置模板
    ├── requirements.txt       Session 1 运行依赖
    └── common/                课程共享 LLM 接口
```

`course-demos/common/` 和课程练习说明沿用 Uoffer 课程提供的文件；共享模块原样保留，便于按作业要求复用接口。设计图、诗词机器人与实现说明属于本次作业交付。

公开仓库不包含 `.env`、密钥文本文件、个人本地目录、虚拟环境或其他课程模块。`.gitignore` 已排除本地凭据；填写真实值后不要强制添加被忽略的文件。
