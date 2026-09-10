"""Session 1 诗词机器人：按既定架构实现本地控制台对话。"""

import os
import re
import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from pathlib import Path

COURSE_DEMOS = Path(__file__).resolve().parents[2] / "course-demos"
if str(COURSE_DEMOS) not in sys.path:
    sys.path.insert(0, str(COURSE_DEMOS))

from common.llm import call_llm_safe

SYSTEM_PROMPT = (
    "你是一位古诗词聊天助手。请理解用户的含义和情绪，"
    "选择一句与之贴切的、真实存在的中国古诗词作为回答。"
    "不要自创、改写或拼接诗句；优先选择你确信原文的诗句。"
    "正常回答只输出诗句，不加标题、作者、引号或解释。"
)
MOCK_REPLY = "[Mock / Fallback：固定示例]\n海内存知己，天涯若比邻。"
API_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY")

# 按实际函数与分支核对的静态图，不是自动解析源码生成的图。
DIAGRAM = """%% 静态 Mermaid：按实现核对，非自动解析源码；用于与原始设计人工对照。
flowchart TB
    start["main：命令行入口"] --> diagram{"--diagram？"}
    diagram -- 是 --> source["输出静态 Mermaid 并退出，不调用模型"]
    diagram -- 否 --> user["--once 输入或 run_console 连续输入"]
    user --> clean["clean_message_text：首尾空白与开头提及清洗"]
    clean --> empty{"清洗后为空？"}
    empty -- 是 --> hint["提示输入一句话，不调用模型"]
    empty -- 否 --> prompt["build_prompt：理解含义，选择已有古诗词"]
    prompt --> offline["offline_mode：--mock 时临时移除进程密钥"]
    offline --> llm
    config["course-demos/.env 或环境变量"] -. 由共享模块加载 .-> llm
    subgraph shared["course-demos/common/llm.py"]
        llm["call_llm_safe：统一调用入口"] --> provider{"有模型密钥？"}
        provider -- 是 --> real["真实 LLM 请求"]
        provider -- 否 --> fallback["返回带 Mock / Fallback 标记的固定示例"]
        real -- API 失败 --> fallback
    end
    real -- API 成功 --> restore["离开 offline_mode，恢复临时移除的密钥"]
    fallback --> restore
    restore --> reply["输出诗句或带标记的固定示例"]
"""


def clean_message_text(text: str) -> str:
    """只删除首尾空白及连续的开头 Slack 风格提及。"""
    return re.sub(r"^(<@[A-Z0-9]+>\s*)+", "", text.strip()).strip()


def build_prompt(text: str) -> tuple[str, str]:
    return SYSTEM_PROMPT, f"用户的话：\n{text}\n请用一句合适的已有古诗词回答。"


@contextmanager
def offline_mode(enabled: bool):
    """共享模块已经加载配置；只临时修改本进程，不读写配置文件。"""
    if not enabled:
        yield
        return
    saved = {name: os.environ.pop(name, None) for name in API_KEYS}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def handle_message(text: str, mock: bool = False) -> str:
    cleaned = clean_message_text(text)
    if not cleaned:
        return "请输入一句话。"
    system, user = build_prompt(cleaned)
    with offline_mode(mock):
        return call_llm_safe(system=system, user=user, mock=MOCK_REPLY)


def run_console(mock: bool = False):
    print("诗词聊天机器人：输入一句话，输入 quit 或 exit 退出。")
    while True:
        try:
            text = input("你> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.strip().lower() in ("quit", "exit"):
            return
        print(handle_message(text, mock=mock))


def main():
    parser = ArgumentParser(description="本地古诗词聊天机器人")
    parser.add_argument("--once", metavar="一句话", help="处理一次输入后退出")
    parser.add_argument("--mock", action="store_true", help="通过共享接口强制离线")
    parser.add_argument("--diagram", action="store_true", help="只输出静态 Mermaid 源码")
    args = parser.parse_args()
    if args.diagram:
        print(DIAGRAM, end="")
    elif args.once is not None:
        print(handle_message(args.once, mock=args.mock))
    else:
        run_console(mock=args.mock)


if __name__ == "__main__":
    main()
