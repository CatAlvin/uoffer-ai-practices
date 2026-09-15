# 练习 A：同一快照，两类读者

## 作业展示

- [实验报告](summary_two_audiences.md)
- 同一份课堂长素材分别生成工程师版和管理者版摘要。
- 两版均使用 DeepSeek `deepseek-chat` 和 `single` 策略，只改变受众参数。
- 报告包含两份完整输出，以及每版三条结论的原文证据。

## 运行

在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r practices/session-03/exercise-a/requirements.txt
Copy-Item practices/session-03/exercise-a/course-demos/.env.example practices/session-03/exercise-a/course-demos/.env
```

在新建的 `.env` 中填写 `DEEPSEEK_API_KEY`，保持其他供应商密钥为空，然后运行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 practices/session-03/exercise-a/run_exercise_a.py
```

运行结果保存在 `practices/session-03/exercise-a/run-results/`。
