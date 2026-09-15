"""L3 练习 B：复用 A 的固定快照，预演或执行课程 Map-Reduce。

--preview 只使用本地记录器，不调用 llm.call_llm。
--run     通过课程 summarize() 和 llm.call_llm() 执行真实 Map-Reduce。
"""
import argparse
import hashlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parent
A_DIR = ROOT / "evidence/a"
B_DIR = ROOT / "run-results"
sys.path.insert(0, str(ROOT / "course-demos"))

from common import llm
from common.summarization import FOCUS, estimate_tokens, summarize


AUDIENCE = "engineer"
STRATEGY = "map-reduce"
CHUNK_TOKENS = 4000
CONTEXT_BUDGET = 32000
OUTPUT_RESERVE = 1500
EXPECTED_PROVIDER = "deepseek"
EXPECTED_MODEL = "deepseek-chat"
EXPECTED_SNAPSHOT_SHA256 = "8ad6dced2c94ee4656f2eb9238bb7d40e519c92d12a8e18c254159e476effe8a"
EXPECTED_FIXTURE_SHA256 = "8470018c4cde872920b812775314355df333d5dc61bca648421dcc96eb6c2e02"
SOURCE_ID = "demo:manifest/C_DEMO/1700000000.000001"
SOURCE_PREFIX = f"[source {SOURCE_ID}]\n"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configuration():
    return {
        "provider": llm.llm_provider(),
        "model": llm.llm_model(),
        "temperature": inspect.signature(llm.call_llm).parameters["temperature"].default,
        "timeout_seconds": llm._timeout(),
        "max_retries": llm._max_retries(),
    }


def bound_request(arguments):
    bound = inspect.signature(llm.call_llm).bind(**arguments)
    bound.apply_defaults()
    return {
        "system": bound.arguments["system"],
        "user": bound.arguments["user"],
        "temperature": bound.arguments["temperature"],
        "max_output_tokens": bound.arguments["max_output_tokens"],
        "provider": llm.llm_provider(),
        "model": llm.llm_model(),
    }


def classify_stage(system):
    if "当前是片段：保留关键事实、时间、状态和未知项，勿过早压缩。" in system:
        return "map"
    if "合并重复事实，按时间整理，无法解释的矛盾保留。" in system:
        return "reduce"
    raise RuntimeError("unknown_course_stage_prompt")


def validate_a():
    required = [
        "input_snapshot.json", "engineer.snapshot.json", "engineer.request.json",
        "engineer.result.json", "engineer.raw.txt",
    ]
    missing = [name for name in required if not (A_DIR / name).is_file()]
    if missing:
        raise RuntimeError("missing_a_artifacts:" + ",".join(missing))

    snapshot = read_json(A_DIR / "input_snapshot.json")
    a_snapshot = read_json(A_DIR / "engineer.snapshot.json")
    a_request = read_json(A_DIR / "engineer.request.json")
    a_result = read_json(A_DIR / "engineer.result.json")
    raw = (A_DIR / "engineer.raw.txt").read_text(encoding="utf-8")

    if canonical(snapshot) != canonical(a_snapshot):
        raise RuntimeError("a_saved_snapshots_differ")
    snapshot_hash = sha256_text(canonical(snapshot))
    if snapshot_hash != EXPECTED_SNAPSHOT_SHA256:
        raise RuntimeError("a_snapshot_hash_changed")
    if len(snapshot) != 1 or snapshot[0].get("source") != "manifest_replay":
        raise RuntimeError("a_snapshot_identity_changed")
    fixture = ROOT / "course-demos/session-03-pipeline-agent/fixtures/long.json"
    if sha256_file(fixture) != EXPECTED_FIXTURE_SHA256:
        raise RuntimeError("teacher_long_fixture_changed")
    if (a_request.get("provider") != EXPECTED_PROVIDER
            or a_request.get("model") != EXPECTED_MODEL
            or a_request.get("temperature") != 0.3
            or a_request.get("max_output_tokens") != OUTPUT_RESERVE):
        raise RuntimeError("a_single_request_settings_changed")
    if (a_result.get("text") != raw or a_result.get("mode") != EXPECTED_PROVIDER
            or a_result.get("model") != EXPECTED_MODEL
            or a_result.get("audience") != AUDIENCE
            or a_result.get("strategy") != "single"):
        raise RuntimeError("a_engineer_output_not_linked_to_snapshot")

    current = configuration()
    if (current["provider"], current["model"], current["temperature"]) != (
            EXPECTED_PROVIDER, EXPECTED_MODEL, 0.3):
        raise RuntimeError("current_model_configuration_changed")
    if current["timeout_seconds"] != 60.0 or current["max_retries"] != 1:
        raise RuntimeError("current_timeout_or_retry_settings_differ_from_a")

    captured = []

    def capture_single(**arguments):
        captured.append(bound_request(arguments))
        return "LOCAL REQUEST RECONSTRUCTION; NO MODEL CALL"

    reconstructed = summarize(
        snapshot, audience=AUDIENCE, strategy="single", mock=False,
        context_budget=CONTEXT_BUDGET, output_reserve=OUTPUT_RESERVE,
        chunk_tokens=CHUNK_TOKENS, caller=capture_single,
    )
    if len(captured) != 1 or captured[0] != a_request:
        raise RuntimeError("current_single_request_differs_from_a")
    if reconstructed.get("mode") != EXPECTED_PROVIDER:
        raise RuntimeError("current_single_would_not_be_real_provider")

    return snapshot, a_request, current


def run_preview():
    if B_DIR.exists() and any(path.name != ".gitkeep" for path in B_DIR.iterdir()):
        raise RuntimeError("b_output_directory_already_exists")
    snapshot, a_request, current = validate_a()
    B_DIR.mkdir(parents=True, exist_ok=True)
    preview_dir = B_DIR / "preview"
    preview_dir.mkdir()
    calls = []
    fragments = []

    def preview_caller(**arguments):
        request = bound_request(arguments)
        stage = classify_stage(request["system"])
        index = 1 + sum(row["stage"] == stage for row in calls)
        label = f"{stage}-{index:02d}"
        request_estimate = (
            estimate_tokens(request["system"]) + estimate_tokens(request["user"])
            + OUTPUT_RESERVE + 256
        )
        record = {
            "stage": stage,
            "index": index,
            "label": label,
            "source": SOURCE_ID if stage == "map" else "map outputs",
            "input_characters": len(request["user"]),
            "input_budget_estimate": estimate_tokens(request["user"]),
            "system_budget_estimate": estimate_tokens(request["system"]),
            "total_budget_check": request_estimate,
            "context_budget": CONTEXT_BUDGET,
            "within_context_budget": request_estimate <= CONTEXT_BUDGET,
            "output_reserve": OUTPUT_RESERVE,
            "token_counting": "conservative UTF-8 byte estimate; not actual tokens",
        }
        calls.append(record)
        (preview_dir / f"{label}.input.txt").write_bytes(request["user"].encode("utf-8"))
        write_json(preview_dir / f"{label}.request.json", request)
        if stage == "map":
            if not request["user"].startswith(SOURCE_PREFIX):
                raise RuntimeError("map_source_marker_missing")
            fragment = request["user"][len(SOURCE_PREFIX):]
            fragments.append(fragment)
            (preview_dir / f"{label}.fragment.txt").write_bytes(fragment.encode("utf-8"))
            record.update({
                "fragment_characters": len(fragment),
                "fragment_budget_estimate": estimate_tokens(fragment),
                "outer_source_marker": SOURCE_PREFIX.rstrip("\n"),
            })
            return f"[LOCAL PREVIEW PLACEHOLDER {label}; NOT MODEL OUTPUT]"
        return "[LOCAL PREVIEW PLACEHOLDER reduce-01; NOT MODEL OUTPUT]"

    result = summarize(
        snapshot, audience=AUDIENCE, strategy=STRATEGY, mock=False,
        context_budget=CONTEXT_BUDGET, output_reserve=OUTPUT_RESERVE,
        chunk_tokens=CHUNK_TOKENS, caller=preview_caller,
    )
    map_calls = [row for row in calls if row["stage"] == "map"]
    reduce_calls = [row for row in calls if row["stage"] == "reduce"]
    reconstructed = "".join(fragments)
    if not 2 <= len(map_calls) <= 4:
        raise RuntimeError("preview_chunk_count_outside_2_to_4")
    if len(reduce_calls) != 1 or reconstructed != a_request["user"]:
        raise RuntimeError("preview_does_not_exactly_cover_single_input")
    if any(not row["within_context_budget"] for row in calls):
        raise RuntimeError("preview_budget_check_failed")
    if result.get("strategy") != STRATEGY or len(result.get("partials", [])) != len(map_calls):
        raise RuntimeError("course_map_reduce_preview_incomplete")

    metadata = {
        "status": "preview_completed",
        "created_at": now(),
        "no_real_model_calls": True,
        "shared_llm_call_count": 0,
        "a_single_reusable": True,
        "a_engineer_raw_sha256": sha256_file(A_DIR / "engineer.raw.txt"),
        "input_snapshot_path": str(A_DIR / "input_snapshot.json"),
        "input_snapshot_sha256": EXPECTED_SNAPSHOT_SHA256,
        "single_user_input_sha256": sha256_text(a_request["user"]),
        "current_configuration": current,
        "settings": {
            "audience": AUDIENCE, "strategy": STRATEGY,
            "chunk_tokens": CHUNK_TOKENS, "context_budget": CONTEXT_BUDGET,
            "output_reserve": OUTPUT_RESERVE, "temperature": 0.3,
        },
        "map_fragment_budget": CHUNK_TOKENS,
        "map_count": len(map_calls),
        "expected_real_shared_calls": len(map_calls) + 1,
        "calls": calls,
        "coverage": {
            "fragments_in_original_order": True,
            "concatenated_fragments_equal_a_single_user_input": True,
            "truncation": False,
            "overlap": False,
            "source_marker_added_to_each_map_input": True,
            "preprocessing_difference": "Each Map input adds an outer source marker. Removing that wrapper and concatenating fragments exactly reconstructs A's Single user input.",
        },
        "reduce_budget_rule": "estimate_tokens(reduce_system) + estimate_tokens(actual_reduce_input) + output_reserve + 256 <= context_budget",
        "reduce_preview_warning": "Preview Reduce input contains local placeholders. The real Reduce input and its budget can only be recorded after actual Map outputs exist.",
        "source_code_sha256": {
            "summarization.py": sha256_file(ROOT / "course-demos/common/summarization.py"),
            "llm.py": sha256_file(ROOT / "course-demos/common/llm.py"),
        },
    }
    write_json(B_DIR / "preview_metadata.json", metadata)
    print(json.dumps({
        "status": metadata["status"], "map_count": metadata["map_count"],
        "expected_real_shared_calls": metadata["expected_real_shared_calls"],
        "output": str(B_DIR),
    }, ensure_ascii=False))
    return 0


def run_real():
    preview_path = B_DIR / "preview_metadata.json"
    if not preview_path.is_file():
        raise RuntimeError("preview_required_before_real_run")
    if (B_DIR / "run_metadata.json").exists() or list(B_DIR.glob("map-*.raw.txt")) or (B_DIR / "reduce.raw.txt").exists():
        raise RuntimeError("b_real_results_already_exist")
    snapshot, a_request, current = validate_a()
    preview = read_json(preview_path)
    if (preview.get("status") != "preview_completed"
            or preview.get("map_count") not in (2, 3, 4)
            or preview.get("input_snapshot_sha256") != EXPECTED_SNAPSHOT_SHA256
            or preview.get("source_code_sha256", {}).get("summarization.py")
            != sha256_file(ROOT / "course-demos/common/summarization.py")
            or preview.get("source_code_sha256", {}).get("llm.py")
            != sha256_file(ROOT / "course-demos/common/llm.py")):
        raise RuntimeError("preview_or_course_source_changed")

    metadata = {
        "status": "running", "started_at": now(), "timezone": "Asia/Shanghai",
        "command": "& ./.venv/Scripts/python.exe -B -X utf8 practices/session-03/exercise-b/run_exercise_b.py --run",
        "input_snapshot_path": str(A_DIR / "input_snapshot.json"),
        "input_snapshot_sha256": EXPECTED_SNAPSHOT_SHA256,
        "a_single_raw_path": str(A_DIR / "engineer.raw.txt"),
        "a_single_raw_sha256": sha256_file(A_DIR / "engineer.raw.txt"),
        "configuration": current,
        "settings": preview["settings"],
        "expected_stages": [f"map-{i:02d}" for i in range(1, preview["map_count"] + 1)] + ["reduce-01"],
        "calls": [],
        "course_log_missing": ["request_id", "response_model", "finish_reason", "token_usage",
                               "actual_http_attempts", "actual_sdk_retries"],
    }
    write_json(B_DIR / "run_metadata.json", metadata)
    started = time.monotonic()

    def recorded_call(**arguments):
        request = bound_request(arguments)
        stage = classify_stage(request["system"])
        index = 1 + sum(row["stage"] == stage for row in metadata["calls"])
        label = f"{stage}-{index:02d}"
        expected_label = metadata["expected_stages"][len(metadata["calls"])]
        if label != expected_label or configuration() != current:
            raise RuntimeError("stage_order_or_configuration_changed")
        record = {"stage": stage, "index": index, "label": label,
                  "status": "calling_shared_llm", "started_at": now(),
                  "mock_callback_invoked": False,
                  "input_budget_estimate": estimate_tokens(request["user"]),
                  "system_budget_estimate": estimate_tokens(request["system"]),
                  "total_budget_check": estimate_tokens(request["system"]) + estimate_tokens(request["user"]) + OUTPUT_RESERVE + 256}
        metadata["calls"].append(record)
        write_json(B_DIR / f"{label}.request.json", request)
        (B_DIR / f"{label}.input.txt").write_bytes(request["user"].encode("utf-8"))
        write_json(B_DIR / "run_metadata.json", metadata)
        original_mock = arguments["mock"]

        def observed_mock(system, user):
            record["mock_callback_invoked"] = True
            return original_mock(system, user)

        call_started = time.monotonic()
        try:
            output = llm.call_llm(**{**arguments, "mock": observed_mock})
            if not isinstance(output, str) or not output.strip() or record["mock_callback_invoked"]:
                raise RuntimeError("mock_empty_or_non_text_output")
            (B_DIR / f"{label}.raw.txt").write_bytes(output.encode("utf-8"))
            record.update(status="real_output_returned", ended_at=now(),
                          elapsed_seconds=round(time.monotonic() - call_started, 3),
                          raw_output_sha256=sha256_text(output))
            write_json(B_DIR / "run_metadata.json", metadata)
            return output
        except Exception as exc:
            record.update(status="failed", ended_at=now(),
                          elapsed_seconds=round(time.monotonic() - call_started, 3),
                          error_type=type(exc).__name__)
            write_json(B_DIR / "run_metadata.json", metadata)
            raise

    try:
        result = summarize(
            snapshot, audience=AUDIENCE, strategy=STRATEGY, mock=False,
            context_budget=CONTEXT_BUDGET, output_reserve=OUTPUT_RESERVE,
            chunk_tokens=CHUNK_TOKENS, caller=recorded_call,
        )
        if (len(metadata["calls"]) != preview["expected_real_shared_calls"]
                or any(row["status"] != "real_output_returned" for row in metadata["calls"])
                or result.get("mode") != EXPECTED_PROVIDER
                or result.get("model") != EXPECTED_MODEL
                or result.get("strategy") != STRATEGY
                or len(result.get("partials", [])) != preview["map_count"]
                or configuration() != current):
            raise RuntimeError("real_map_reduce_not_confirmed")
        write_json(B_DIR / "result.json", result)
        (B_DIR / "final.raw.txt").write_bytes(result["text"].encode("utf-8"))
        metadata["status"] = "completed"
    except Exception as exc:
        metadata["status"] = "stopped"
        metadata["error_type"] = type(exc).__name__
    finally:
        metadata["ended_at"] = now()
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(B_DIR / "run_metadata.json", metadata)
    print(json.dumps({"status": metadata["status"], "calls": [
        {"stage": row["stage"], "status": row["status"]} for row in metadata["calls"]
    ], "output": str(B_DIR)}, ensure_ascii=False))
    return 0 if metadata["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preview", action="store_true", help="local chunk preview; never call a model")
    modes.add_argument("--run", action="store_true", help="perform the authorized real Map-Reduce run")
    args = parser.parse_args()
    try:
        return run_preview() if args.preview else run_real()
    except Exception as exc:
        print(f"STOPPED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
