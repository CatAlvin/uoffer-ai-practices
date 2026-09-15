# 练习 B：Single 与 Map-Reduce 比较

## 作业展示

- [实验报告](chunk_comparison.md)
- [Single 与原始快照](evidence/a/)
- [Map、Reduce 原始证据](evidence/map-reduce/)
- 使用同一份课堂长素材和工程师受众，对比 Single 与两块 Map-Reduce。
- 报告追踪“回滚完成”和“服务恢复”这一条事实链，并给出一项分块改进建议。

## 运行

在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r practices/session-03/exercise-b/requirements.txt
Copy-Item practices/session-03/exercise-b/course-demos/.env.example practices/session-03/exercise-b/course-demos/.env
```

在新建的 `.env` 中填写 `DEEPSEEK_API_KEY`，保持其他供应商密钥为空。先做本地分块预演，再执行真实 Map-Reduce：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 practices/session-03/exercise-b/run_exercise_b.py --preview
.\.venv\Scripts\python.exe -B -X utf8 practices/session-03/exercise-b/run_exercise_b.py --run
```

预演不请求模型；真实运行执行 2 次 Map 和 1 次 Reduce。新结果保存在 `practices/session-03/exercise-b/run-results/`。
