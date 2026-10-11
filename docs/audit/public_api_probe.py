"""Run read-only public backend checks and save a compact result record."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


BASE = "https://computers-welfare-anytime-stem.trycloudflare.com/api"
REPO = "a044a248-81e8-42c0-bacf-18ea31f1bee2"
EVALUATION = "f22efa66-af80-4055-8fe4-61cfb07c879b"
OUTPUT = Path(__file__).with_name("public-api-results.json")


def main():
    checks = []
    with httpx.Client(base_url=BASE, timeout=90) as client:
        def check(name, method, path, *, json_body=None, params=None, validate=None):
            response = client.request(method, path, json=json_body, params=params)
            try:
                body = response.json()
            except ValueError:
                body = {"raw": response.text[:300]}
            passed, detail = validate(response.status_code, body)
            checks.append({
                "name": name,
                "status_code": response.status_code,
                "passed": passed,
                "detail": detail,
            })
            return body

        check("health", "GET", "/health", validate=lambda status, body: (
            status == 200 and body.get("status") == "healthy", body.get("components")
        ))
        check("repository ready", "GET", f"/repositories/{REPO}", validate=lambda status, body: (
            status == 200 and body.get("status") == "READY", body.get("stats")
        ))
        files = check("indexed files", "GET", f"/repositories/{REPO}/files", validate=lambda status, body: (
            status == 200 and len(body) == 4, [row.get("path") for row in body] if isinstance(body, list) else body
        ))
        check("source content", "GET", f"/repositories/{REPO}/files/content",
              params={"path": "src\\calculator.py"}, validate=lambda status, body: (
                  status == 200 and "class Calculator" in body.get("content", ""),
                  {"path": body.get("path"), "lines": body.get("total_lines")}
              ))
        graph = check("graph", "GET", f"/repositories/{REPO}/graph", validate=lambda status, body: (
            status == 200 and len(body.get("nodes", [])) > 0 and all(
                e["source"] in {n["id"] for n in body.get("nodes", [])}
                and e["target"] in {n["id"] for n in body.get("nodes", [])}
                for e in body.get("edges", [])
            ), body.get("stats")
        ))
        check("call flows", "GET", f"/repositories/{REPO}/call-flows", validate=lambda status, body: (
            status == 200 and body.get("total", 0) > 0 and all(
                flow.get("caller", {}).get("name") and flow.get("callee", {}).get("name")
                for flow in body.get("flows", [])
            ), {"total": body.get("total"), "relationships": sorted({
                flow.get("relationship") for flow in body.get("flows", [])
            })}
        ))
        for strategy in ("bm25", "dense", "hybrid_rrf", "graph_expansion"):
            body = check(f"retrieval {strategy}", "POST", "/retrieval/search", json_body={
                "repository_id": REPO,
                "query": "How does Calculator divide handle zero?",
                "top_k": 5,
                "strategy": strategy,
                "enable_graph_expansion": strategy == "graph_expansion",
                "enable_mmr": False,
            }, validate=lambda status, body: (
                status == 200 and 0 < body.get("total_retrieved", 0) <= 5
                and all(c.get("chunk_id") and c.get("file_path") for c in body.get("chunks", [])),
                {"count": body.get("total_retrieved"), "intent": body.get("intent"),
                 "first": body.get("chunks", [{}])[0].get("symbol_name"),
                 "latency_ms": body.get("latency_ms")}
            ))
        interview = check("interview generate", "POST", f"/repositories/{REPO}/interview/generate",
                          json_body={"count": 3, "difficulty": "intermediate", "focus": "general"},
                          validate=lambda status, body: (
                              status == 200 and body.get("total") == 3 and all(
                                  q.get("target_files") and q.get("target_symbols")
                                  for q in body.get("questions", [])
                              ), {"total": body.get("total"), "topics": [
                                  q.get("topic") for q in body.get("questions", [])
                              ]}
                          ))
        if interview.get("questions"):
            question = interview["questions"][0]
            check("interview feedback", "POST", f"/repositories/{REPO}/interview/evaluate",
                  json_body={"question": question["question"], "user_answer":
                             f"{question['target_symbols'][0]} implements methods in the cited source.",
                             "target_files": question["target_files"],
                             "target_symbols": question["target_symbols"]},
                  validate=lambda status, body: (
                      status == 200 and body.get("citations") and
                      all(c.get("file_path") in question["target_files"] for c in body.get("citations", [])),
                      {"score": body.get("score"), "citations": [
                          {"file_path": c.get("file_path"), "start_line": c.get("start_line")}
                          for c in body.get("citations", [])
                      ]}
                  ))
        check("existing evaluation", "GET", f"/evaluation/{EVALUATION}", validate=lambda status, body: (
            status == 200 and body.get("status") == "completed" and len(body.get("metrics", [])) == 4,
            {"id": body.get("id"), "status": body.get("status"), "strategies": [
                metric.get("strategy") for metric in body.get("metrics", [])
            ]}
        ))
        check("path traversal rejected", "GET", f"/repositories/{REPO}/files/content",
              params={"path": "../../backend/.env"}, validate=lambda status, body: (
                  status in (400, 404), {"error": body.get("error")}
              ))

    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "base_url": BASE,
              "repository_id": REPO, "read_only": True, "checks": checks,
              "passed": sum(c["passed"] for c in checks), "total": len(checks)}
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{report['total']} checks passed: {OUTPUT}")
    for item in checks:
        if not item["passed"]:
            print(f"FAILED {item['name']}: {item['status_code']} {item['detail']}")


if __name__ == "__main__":
    main()
