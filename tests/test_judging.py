"""Exercise the real HTTP client, CLI preflight, and report/error contracts."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from typer.testing import CliRunner

from enronqa.cli import app
from enronqa.judging import JudgeConfig, JudgeError, score
from enronqa.data import Dataset

runner = CliRunner()
BATCH = "\n".join(
    json.dumps({"question_id": q, "answer": a})
    for q, a in [("q1", "It was approved."), ("q2", "I don't know"), ("q3", "Chef")]
)


@pytest.fixture
def api(monkeypatch):
    class State:
        responses = deque()
        calls = []
        active = 0
        peak = 0
        delay = 0
        lock = threading.Lock()

    state = State()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            with state.lock:
                state.calls.append((self.path, dict(self.headers), body))
                state.active += 1
                state.peak = max(state.peak, state.active)
                response = (
                    state.responses.popleft() if state.responses else '{"correct":true}'
                )
            try:
                time.sleep(state.delay)
                if isinstance(response, tuple):
                    status, raw = response
                    self.send_response(status)
                    if status == 302:
                        self.send_header("Location", "/should-not-follow")
                    self.end_headers()
                    self.wfile.write(raw.encode())
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(
                            {
                                "choices": [
                                    {
                                        "message": {"content": response},
                                        "finish_reason": "stop",
                                    }
                                ]
                            }
                        ).encode()
                    )
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with state.lock:
                    state.active -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}/v1"
    monkeypatch.setenv("OPENAI_BASE_URL", state.url)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-do-not-emit")
    yield state
    server.shutdown()
    server.server_close()
    thread.join()


def run_batch(extra=(), data=BATCH):
    return runner.invoke(
        app, ["score", "-", "--set", "all", "--model", "test-model", *extra], input=data
    )


def test_batch_boolean_and_ordinary_unknown_answer(corpus, api):
    api.responses.extend(['{"correct":true}', '{"correct":false}', '{"correct":true}'])
    records = [json.loads(line) for line in BATCH.splitlines()]
    records[0].update(status="untrusted", judgment={"correct": False}, latency_ms=4)
    result = run_batch(data="\n".join(map(json.dumps, records)))
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["summary"] == {
        "submitted": 3,
        "judged": 3,
        "failed": 0,
        "unprocessed": 0,
        "attempts": 3,
        "correct": 2,
        "incorrect": 1,
        "denominator": 3,
        "accuracy": 2 / 3,
    }
    assert "abstained" not in result.stdout
    assert "test-secret" not in result.stdout
    row = report["results"][0]
    assert row["status"] == "ok" and row["judgment"] == {"correct": True}
    assert row["metadata"]["status"] == "untrusted"
    assert row["reference_answers"] == ["approved", "yes"]
    path, headers, body = api.calls[0]
    assert path == "/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-secret-do-not-emit"
    inputs = json.loads(body["messages"][1]["content"])
    assert inputs == {
        "question": "Was it approved?",
        "submitted_answer": "It was approved.",
        "reference_answer": "approved",
        "source": "Synthetic email one",
    }
    assert (
        json.loads(api.calls[1][2]["messages"][1]["content"])["submitted_answer"]
        == "I don't know"
    )
    assert report["judge"]["model"] == "test-model"
    assert len(report["judge"]["prompt"]["sha256"]) == 64


def test_check_verbose(corpus, api):
    api.responses.append('{"correct":false,"explanation":"Missing the amount."}')
    result = runner.invoke(
        app,
        ["check", "q2", "--answer", "unknown", "--model", "test-model", "--verbose"],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert "coverage" not in report and report["warnings"] == []
    assert report["summary"]["accuracy"] == 0
    assert report["results"][0]["judgment"]["explanation"] == "Missing the amount."
    assert report["judge"]["prompt"]["verbose"] is True


@pytest.mark.parametrize(
    "judgment",
    [
        None,
        False,
        0,
        "a string",
        [1, {"anything": True}],
        {"question_id": "override", "status": "fake", "arbitrary": [1, 2]},
    ],
)
def test_custom_json_unrestricted(corpus, api, tmp_path, judgment):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Return any pure JSON you choose.", encoding="utf-8")
    api.responses.append(json.dumps(judgment))
    result = run_batch(["--judge-prompt", str(prompt)], BATCH.splitlines()[0])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    row = report["results"][0]
    assert row["question_id"] == "q1" and row["status"] == "ok"
    assert row["judgment"] == judgment
    assert "accuracy" not in report["summary"] and "correct" not in report["summary"]
    assert api.calls[0][2]["messages"][0]["content"] == prompt.read_text()


@pytest.mark.parametrize(
    "bad",
    [
        '```json\n{"correct":true}\n```',
        '{"correct":1}',
        '{"correct":"true"}',
        '{"correct":true,"extra":1}',
        "[]",
        "null",
        '{"correct":true,"correct":false}',
        "not JSON",
        '{"correct": NaN}',
        '{"correct":true} trailing',
        '{"correct":true,"x":"\\ud800"}',
        '{"correct":1e999}',
    ],
)
def test_bad_judgment_is_failure_not_incorrect(corpus, api, bad):
    api.responses.append(bad)
    result = run_batch(["--retries", "0"], BATCH.splitlines()[0])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["summary"]["accuracy"] is None
    assert report["summary"]["incorrect"] == 0 and report["summary"]["failed"] == 1
    assert report["results"][0]["error"]["code"] == "invalid_response"


def test_retry_malformed_and_transient_then_success(corpus, api):
    api.responses.extend(["invalid", (429, "rate limited"), '{"correct":false}'])
    result = run_batch(data=BATCH.splitlines()[0])
    assert result.exit_code == 0, result.output
    assert len(api.calls) == 3
    assert json.loads(result.stdout)["results"][0]["attempts"] == 3


def test_exhausted_failure_continues_and_saves(corpus, api, tmp_path):
    api.responses.extend(["invalid"] * 3)
    out = tmp_path / "report.json"
    result = run_batch(["--output", str(out)])
    assert result.exit_code == 1 and result.stdout == ""
    report = json.loads(out.read_text())
    assert report["summary"]["judged"] == 2 and report["summary"]["failed"] == 1
    assert report["summary"]["accuracy"] == 1 and report["summary"]["denominator"] == 2
    assert report["summary"]["attempts"] == 5


def test_breaker_stops_scheduling(corpus, api):
    api.responses.extend(["bad"] * 6)
    result = run_batch(["--max-consecutive-failures", "2"])
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and len(api.calls) == 6
    assert report["summary"]["failed"] == 2 and report["summary"]["unprocessed"] == 1
    assert report["processing"]["stop_reason"] == "consecutive_failures"
    assert report["results"][-1]["attempts"] == 0


def test_success_resets_failure_count(corpus, api):
    api.responses.extend(["bad", '{"correct":true}', "bad"])
    result = run_batch(["--retries", "0", "--max-consecutive-failures", "2"])
    report = json.loads(result.stdout)
    assert len(api.calls) == 3 and report["processing"]["stop_reason"] is None
    assert report["summary"]["failed"] == 2 and report["summary"]["judged"] == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 302])
def test_fatal_http_stops_without_retries_or_credential_leak(corpus, api, status):
    api.responses.append((status, "provider echoes test-secret-do-not-emit"))
    result = run_batch()
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and len(api.calls) == 1
    assert report["summary"]["unprocessed"] == 2
    assert report["processing"]["stop_reason"] == "configuration_error"
    assert "test-secret" not in result.output
    assert f"HTTP {status}" in report["results"][0]["error"]["message"]


def test_concurrency_bound_and_order(corpus, api):
    api.delay = 0.08
    result = run_batch(["--concurrency", "2"])
    assert result.exit_code == 0, result.output
    assert api.peak == 2
    assert [r["question_id"] for r in json.loads(result.stdout)["results"]] == [
        "q1",
        "q2",
        "q3",
    ]


def test_timeout(corpus, api):
    api.delay = 0.1
    result = run_batch(["--timeout", ".01", "--retries", "0"], BATCH.splitlines()[0])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["results"][0]["error"]["code"] == "request_error"


@pytest.mark.parametrize(
    "extra",
    [
        ["--verbose", "--judge-prompt", "missing"],
        ["--judge-prompt", "missing"],
        ["--base-url", "not-a-url"],
        ["--base-url", "https://name:secret@example.com"],
        ["--base-url", "https://example.com?api_key=secret"],
        ["--api-key-env", "MISSING_KEY"],
        ["--retries", "-1"],
        ["--concurrency", "0"],
        ["--max-consecutive-failures", "0"],
        ["--timeout", "nan"],
    ],
)
def test_config_errors_before_reading_batch(corpus, api, monkeypatch, extra):
    def no_read(*a):
        pytest.fail("Must not read a batch on invalid configuration")

    monkeypatch.setattr("enronqa.cli.read_batch", no_read)
    result = run_batch(extra)
    assert result.exit_code == 2, result.output
    assert not api.calls


def test_missing_model_and_endpoint_fail_before_stdin(corpus, api, monkeypatch):
    result = runner.invoke(app, ["score", "-", "--set", "test"])
    assert result.exit_code == 2 and "--model" in result.stderr
    monkeypatch.delenv("OPENAI_BASE_URL")
    result = run_batch()
    assert result.exit_code == 2 and "--base-url" in result.stderr
    assert not api.calls


def test_full_validation_before_any_api(corpus, api):
    result = run_batch(data=BATCH + '\nnot json\n{"question_id":"q1","answer":""}')
    assert result.exit_code == 2 and not api.calls
    report = json.loads(result.stdout)
    assert {e["line"] for e in report["errors"]} == {4, 5}
    assert "results" not in report


def test_override_key_env_and_endpoint(corpus, api, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("FIREWORKS_TEST_KEY", "other-test-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unused.invalid")
    result = run_batch(
        ["--base-url", api.url, "--api-key-env", "FIREWORKS_TEST_KEY"],
        BATCH.splitlines()[0],
    )
    assert result.exit_code == 0
    assert api.calls[0][1]["Authorization"] == "Bearer other-test-secret"
    assert "other-test-secret" not in result.output


def test_external_judge_input_no_credentials(corpus, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    path = tmp_path / "answers.jsonl"
    path.write_text(BATCH.splitlines()[0])
    result = runner.invoke(app, ["judge-input", str(path), "--set", "test"])
    assert result.exit_code == 0, result.output
    assert "Warning:" in result.stderr
    packet = json.loads(result.stdout)
    assert packet["question"] == "Was it approved?"
    assert packet["reference_answer"] == "approved"
    assert packet["source"] == {
        "document_id": "d1",
        "email": "Synthetic email one",
        "user": "a",
    }
    assert packet["dataset"]["revision"] and packet["question_id"] == "q1"
    out = tmp_path / "inputs.jsonl"
    args = ["judge-input", "-", "--set", "all", "--output", str(out)]
    assert runner.invoke(app, args, input=BATCH).exit_code == 0
    assert len(out.read_text().splitlines()) == 3
    assert runner.invoke(app, args, input=BATCH).exit_code == 2
    assert runner.invoke(app, args + ["--force"], input=BATCH).exit_code == 0


def test_invalid_external_export_emits_no_records(corpus, tmp_path):
    out = tmp_path / "keep.jsonl"
    out.write_text("keep")
    result = runner.invoke(
        app,
        ["judge-input", "-", "--set", "test", "--output", str(out), "--force"],
        input=BATCH,
    )
    assert result.exit_code == 2 and result.stdout == ""
    assert out.read_text() == "keep"
    assert json.loads(result.stderr)["errors"][0]["question_id"] == "q3"


def test_missing_source_rejects_before_network(corpus, api, monkeypatch):
    monkeypatch.setattr(Dataset, "document", lambda self, did: None)
    result = run_batch()
    assert result.exit_code == 2 and not api.calls
    assert "Source email missing" in result.stderr


def test_default_five_consecutive_failures(monkeypatch):
    config = JudgeConfig("http://unused", "test", "hidden", retries=0)
    calls = []

    def fail(packet, config):
        calls.append(packet["question_id"])
        raise JudgeError("invalid_response", "bad")

    monkeypatch.setattr("enronqa.judging.request_judgment", fail)
    packets = [{"question_id": str(i)} for i in range(9)]
    report = score(packets, {"valid": True}, config)
    assert calls == ["0", "1", "2", "3", "4"]
    assert report["summary"]["unprocessed"] == 4
    assert "hidden" not in repr(config)


@pytest.mark.skipif(os.name != "posix", reason="POSIX SIGINT integration")
def test_interrupt_preserves_completed_and_inflight(corpus, api, tmp_path):
    api.delay = 0.3
    answers = tmp_path / "answers.jsonl"
    answers.write_text(BATCH)
    out = tmp_path / "report.json"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "enronqa",
            "score",
            str(answers),
            "--set",
            "all",
            "--model",
            "test",
            "--output",
            str(out),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while len(api.calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(api.calls) == 2
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 130, (stdout, stderr)
        report = json.loads(out.read_text())
        assert report["processing"]["stop_reason"] == "interrupted"
        assert report["results"][0]["status"] == "ok"
        assert report["results"][1]["status"] == "ok"
        assert report["results"][2]["status"] == "unprocessed"
        assert len(api.calls) == 2
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
