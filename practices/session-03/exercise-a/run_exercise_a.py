"""One authorized pair of L3 summaries, using the unchanged course interfaces."""
import hashlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
FOLDER = ROOT / 'run-results'
sys.path.insert(0, str(ROOT / 'course-demos'))
sys.path.insert(0, str(ROOT / 'course-demos/session-03-pipeline-agent'))

from common import llm
from common.summarization import FOCUS, summarize
from demo_fixtures import load_manifest, replay_events, summary_event
from slack_pipeline_demo import DemoRuntime
from slack_adapter import FakeClient, ReplySender

COMMAND = ('& ./.venv/Scripts/python.exe -B -X utf8 '
           'practices/session-03/exercise-a/run_exercise_a.py')
EXPECTED_FIXTURE_HASH = '8470018c4cde872920b812775314355df333d5dc61bca648421dcc96eb6c2e02'


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def save_json(name, value):
    (FOLDER / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def configuration():
    return {'provider': llm.llm_provider(), 'model': llm.llm_model(),
            'timeout_seconds': llm._timeout(), 'max_retries': llm._max_retries()}


def main():
    # An accidental second invocation must not repeat either paid generation.
    if (FOLDER / 'run_metadata.json').exists() or (FOLDER / 'messages.jsonl').exists():
        print('STOPPED: existing run artifacts; no generation repeated.', flush=True)
        return 1

    FOLDER.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    metadata = {'status': 'running', 'started_at': now(), 'timezone': 'Asia/Shanghai',
                'cwd': str(ROOT), 'command': COMMAND, 'output_folder': str(FOLDER),
                'transport': 'FakeClient; no Slack connection', 'generations': [],
                'course_log_missing': ['request_id', 'response_model', 'finish_reason',
                                       'token_usage', 'actual_http_attempts', 'actual_sdk_retries']}
    runtime = None
    try:
        save_json('run_metadata.json', metadata)
        (FOLDER / 'run_command.ps1').write_bytes(
            (f"Set-Location '{ROOT}'\n{COMMAND}\n").encode('utf-8'))
        fixed = configuration()
        metadata['actual_configuration'] = fixed
        if (fixed['provider'], fixed['model']) != ('deepseek', 'deepseek-chat'):
            raise RuntimeError('provider_or_model_unavailable_or_changed')

        fixture = ROOT / 'course-demos/session-03-pipeline-agent/fixtures/long.json'
        fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if fixture_hash != EXPECTED_FIXTURE_HASH:
            raise RuntimeError('approved_fixture_changed')
        manifest = load_manifest(scenario='long')
        metadata['fixture'] = {'path': str(fixture), 'sha256': fixture_hash,
                               'message_count': len(manifest['messages'])}
        fixed_settings = {'strategy': 'single', 'mock': False,
                          'context_budget': 32000, 'chunk_tokens': 4000}
        metadata['summary_settings'] = {**fixed_settings, 'output_reserve': 1500,
                                        'temperature': inspect.signature(llm.call_llm).parameters['temperature'].default}
        expected_snapshot = None
        first_request = None

        def checked_summary(snapshot, **settings):
            nonlocal first_request
            audience = settings['audience']
            record = {'audience': audience, 'started_at': now(), 'status': 'checking',
                      'shared_llm_calls': 0, 'mock_callback_invoked': False}
            metadata['generations'].append(record)
            save_json('run_metadata.json', metadata)
            call_started = time.monotonic()
            try:
                if audience != ('engineer', 'manager')[len(metadata['generations']) - 1]:
                    raise RuntimeError('unexpected_generation_order')
                if canonical(snapshot) != expected_snapshot:
                    raise RuntimeError('actual_snapshot_changed')
                if {k: v for k, v in settings.items() if k != 'audience'} != fixed_settings:
                    raise RuntimeError('summary_settings_changed')
                if configuration() != fixed:
                    raise RuntimeError('provider_model_or_settings_changed')
                save_json(f'{audience}.snapshot.json', snapshot)
                record['snapshot_sha256'] = digest(canonical(snapshot))

                def recorded_call(**arguments):
                    nonlocal first_request
                    if record['shared_llm_calls'] != 0 or configuration() != fixed:
                        raise RuntimeError('unexpected_extra_call_or_configuration_change')
                    bound = inspect.signature(llm.call_llm).bind(**arguments)
                    bound.apply_defaults()
                    request = {k: bound.arguments[k] for k in ('system', 'user', 'temperature', 'max_output_tokens')}
                    request.update(provider=fixed['provider'], model=fixed['model'])
                    if first_request is None:
                        first_request = request.copy()
                    else:
                        expected = first_request.copy()
                        expected['system'] = expected['system'].replace(
                            '本次只输出一个工程师版本', '本次只输出一个管理者版本').replace(
                            FOCUS['engineer'], FOCUS['manager'])
                        if request != expected:
                            raise RuntimeError('actual_model_input_changed_beyond_audience')
                    save_json(f'{audience}.request.json', request)
                    record['llm_user_input_sha256'] = digest(request['user'])
                    record['system_prompt_sha256'] = digest(request['system'])
                    original_mock = arguments['mock']

                    def observed_mock(system, user):
                        record['mock_callback_invoked'] = True
                        return original_mock(system, user)

                    record['shared_llm_calls'] += 1
                    record['status'] = 'calling_shared_llm'
                    save_json('run_metadata.json', metadata)
                    print(f"{audience}: calling shared LLM ({fixed['provider']}/{fixed['model']})", flush=True)
                    # The course function owns its client, provider choice, timeout and retries.
                    answer = llm.call_llm(**{**arguments, 'mock': observed_mock})
                    if not isinstance(answer, str):
                        raise RuntimeError('non_text_output')
                    (FOLDER / f'{audience}.raw.txt').write_bytes(answer.encode('utf-8'))
                    record['raw_output_sha256'] = digest(answer)
                    if record['mock_callback_invoked'] or not answer.strip():
                        raise RuntimeError('mock_or_empty_output')
                    record['shared_llm_returned_nonempty_text'] = True
                    return answer

                output = summarize(snapshot, **settings, caller=recorded_call)
                save_json(f'{audience}.result.json', output)
                if (record['shared_llm_calls'] != 1 or output['mode'] != fixed['provider']
                        or output['model'] != fixed['model'] or output['strategy'] != 'single'
                        or record['mock_callback_invoked'] or configuration() != fixed):
                    raise RuntimeError('real_generation_not_confirmed')
                if canonical(snapshot) != expected_snapshot:
                    raise RuntimeError('snapshot_mutated_during_generation')
                record['status'] = 'real_output_returned'
                print(f'{audience}: raw output saved', flush=True)
                return output
            except Exception as exc:
                record['status'] = 'stopped'
                record['error_type'] = type(exc).__name__
                # Exception messages may contain request details; do not expose them.
                raise
            finally:
                record['ended_at'] = now()
                record['elapsed_seconds'] = round(time.monotonic() - call_started, 3)
                save_json('run_metadata.json', metadata)

        client = FakeClient()
        runtime = DemoRuntime(FOLDER, 'demo:manifest', manifest['channel_id'], 'demo:bot',
                              'demo:bot-id', ReplySender(client), summarizer=checked_summary,
                              **fixed_settings)
        for body in replay_events(manifest, runtime.registry):
            runtime.ingest(body, source='manifest_replay')
        if not runtime.wait_idle(10) or runtime.incomplete:
            raise RuntimeError('material_replay_incomplete')
        snapshot = runtime.store.snapshot('demo:manifest', manifest['channel_id'])
        if (len(snapshot) != 1 or snapshot[0]['text'] != manifest['messages'][0]['text']
                or snapshot[0]['source'] != 'manifest_replay'):
            raise RuntimeError('unexpected_stored_material')
        expected_snapshot = canonical(snapshot)
        save_json('input_snapshot.json', snapshot)
        stored_bytes = (FOLDER / 'messages.jsonl').read_bytes()
        metadata['input_snapshot_sha256'] = digest(expected_snapshot)
        save_json('run_metadata.json', metadata)

        for i, audience in enumerate(('engineer', 'manager'), 1):
            event = summary_event(manifest['channel_id'], ts=f'9999999999.{i:06d}', audience=audience)
            metadata.setdefault('trigger_events', []).append(event)
            runtime.ingest(event, source='fixture')
            if not runtime.wait_idle(600):
                raise RuntimeError('generation_did_not_finish')
            if (len(metadata['generations']) != i
                    or metadata['generations'][-1]['status'] != 'real_output_returned'
                    or runtime.results[-1]['status'] != 'replied' or runtime.incomplete):
                raise RuntimeError('generation_failed_stop_before_next_audience')
            if (FOLDER / 'messages.jsonl').read_bytes() != stored_bytes:
                raise RuntimeError('stored_input_changed')

        runtime.close()
        if runtime.incomplete:
            raise RuntimeError('runtime_incomplete')
        metadata['status'] = 'completed'
        metadata['identical_actual_snapshots'] = True
        metadata['identical_llm_user_inputs'] = True
        metadata['system_difference_limited_to_existing_audience_and_focus'] = True
        metadata['messages_jsonl_unchanged_after_summaries'] = True
    except Exception as exc:
        metadata['status'] = 'stopped'
        metadata['error_type'] = type(exc).__name__
        print(f'STOPPED: {type(exc).__name__}; inspect saved status, no extra request will run.', flush=True)
    finally:
        if runtime is not None:
            runtime.close()
        metadata['ended_at'] = now()
        metadata['elapsed_seconds'] = round(time.monotonic() - started, 3)
        save_json('run_metadata.json', metadata)
    print(json.dumps({'status': metadata['status'], 'output_folder': str(FOLDER),
                      'generations': [{'audience': r['audience'], 'status': r['status'],
                                       'shared_llm_calls': r['shared_llm_calls']}
                                      for r in metadata['generations']]}, ensure_ascii=False), flush=True)
    return 0 if metadata['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
