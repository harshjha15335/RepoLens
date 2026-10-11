"""Verify real model generation and concurrent writes through the public proxy."""

import json
import runpy
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE = "https://computers-welfare-anytime-stem.trycloudflare.com/api"
results = []
started = time.monotonic()
with httpx.Client(base_url=BASE, timeout=160) as client:
    response = client.post("/sessions", params={
        "repository_id": "a044a248-81e8-42c0-bacf-18ea31f1bee2", "tutor_mode": "debug"
    })
    response.raise_for_status()
    session_id = response.json()["id"]
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(client.post, "/chat", json={
                "repository_id": "a044a248-81e8-42c0-bacf-18ea31f1bee2",
                "session_id": session_id, "tutor_mode": "debug",
                "question": "Debug these selected constructor lines. Identify any actual issue concisely.",
                "code_context": {"file_path": "src\\calculator.py", "start_line": 7, "end_line": 9,
                                 "action": "debug"},
            })
            time.sleep(1)
            runpy.run_path(str(Path(__file__).with_name("live_mutation_probe.py")), run_name="__main__")
            results.append({"check": "upload and reindex completed during model generation",
                            "passed": not pending.done(), "elapsed_seconds": round(time.monotonic() - started, 2)})
            print(json.dumps(results[-1]), flush=True)
            answer = pending.result()
            answer.raise_for_status()
            body = answer.json()
            results.append({"check": "selected-code debug chat returned grounded answer",
                            "passed": bool(body["answer"]) and any(
                                c["file_path"] == "src\\calculator.py" and 7 <= c["start_line"] <= c["end_line"] <= 9
                                for c in body["citations"]),
                            "metadata": body["retrieval_metadata"], "answer": body["answer"]})
            saved = client.get(f"/sessions/{session_id}")
            saved.raise_for_status()
            results.append({"check": "successful exchange persisted atomically", "passed": len(saved.json()["messages"]) == 2})
    finally:
        client.delete(f"/sessions/{session_id}").raise_for_status()
        Path(__file__).with_name("public-chat-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
assert all(item["passed"] for item in results), results
print(f"{len(results)}/{len(results)} concurrent chat checks passed", flush=True)
