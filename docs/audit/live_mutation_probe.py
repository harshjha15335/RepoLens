"""Exercise only disposable audit data through the public API."""

import io
import json
import time
import zipfile
from pathlib import Path

import httpx

BASE = "https://computers-welfare-anytime-stem.trycloudflare.com/api"
results = []
repository_id = None


def record(name, passed, detail=None):
    results.append({"check": name, "passed": passed, "detail": detail})
    if not passed:
        raise AssertionError(f"{name}: {detail}")


def await_ready(client):
    for _ in range(60):
        response = client.get(f"/repositories/{repository_id}/status")
        response.raise_for_status()
        body = response.json()
        if body["status"] in ("READY", "FAILED"):
            record("indexing completed", body["status"] == "READY", body)
            return body
        time.sleep(0.5)
    record("indexing completed", False, "Timed out after 60 status polls")


archive = io.BytesIO()
with zipfile.ZipFile(archive, "w") as output:
    output.writestr("README.md", "# Disposable audit repository\nAdds two numbers.\n")
    output.writestr("audit_math.py", "class AuditMath:\n    def add(self, a, b):\n        return a + b\n")
    output.writestr("greeting.ts", "export function greet(name: string): string { return `Hello ${name}`; }\n")

try:
    with httpx.Client(base_url=BASE, timeout=45) as client:
        response = client.post("/repositories/upload", files={
            "file": (f"disposable-audit-{time.time_ns()}.zip", archive.getvalue(), "application/zip")
        })
        response.raise_for_status()
        body = response.json()
        repository_id = body["id"]
        record("ZIP upload accepted", body["status"] == "PENDING", body["name"])
        ready = await_ready(client)
        files = client.get(f"/repositories/{repository_id}/files").json()
        record("all three source files indexed", len(files) == 3, [item["path"] for item in files])
        retrieved = client.post("/retrieval/search", json={
            "repository_id": repository_id, "query": "AuditMath add two numbers", "strategy": "bm25", "top_k": 4
        })
        retrieved.raise_for_status()
        record("new repository retrieval", any("return a + b" in item["content"] for item in retrieved.json()["chunks"]))
        response = client.post(f"/repositories/{repository_id}/index")
        response.raise_for_status()
        record("ZIP reindex queued", response.json()["status"] == "PENDING")
        reindexed = await_ready(client)
        record("reindex preserves unique file/chunk counts", ready["stats"]["files"] == reindexed["stats"]["files"]
               and ready["stats"]["chunks"] == reindexed["stats"]["chunks"], reindexed["stats"])
finally:
    if repository_id:
        with httpx.Client(base_url=BASE, timeout=45) as client:
            deleted = client.delete(f"/repositories/{repository_id}")
            deleted.raise_for_status()
            record("disposable repository deleted", client.get(f"/repositories/{repository_id}").status_code == 404)
    Path(__file__).with_name("public-mutation-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

print(f"{sum(result['passed'] for result in results)}/{len(results)} disposable runtime checks passed")
