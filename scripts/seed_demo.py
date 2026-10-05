#!/usr/bin/env python3
"""Seed demo script for CodeMentor-RAG.

Uploads and indexes the sample calculator repository, and seeds initial
chat questions demonstrating each tutor mode.
"""

import sys
import time
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api"
REPO_DIR = Path(__file__).resolve().parent.parent / "sample-repos" / "calculator"
ZIP_PATH = Path(__file__).resolve().parent.parent / "sample-repos" / "calculator.zip"


def main():
    print("CodeMentor-RAG Demo Seeder")
    print("=" * 40)

    # 1. Check backend health
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if r.status_code != 200:
            print(f"Error: Backend health check failed with status {r.status_code}")
            sys.exit(1)
        print(" Backend is healthy and ready")
    except Exception as e:
        print(f" Error connecting to backend at {BASE_URL}: {e}")
        print("Ensure backend is running: `uvicorn app.main:app --port 8000`")
        sys.exit(1)

    # 2. Ensure ZIP exists
    if not ZIP_PATH.exists():
        import shutil
        shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", str(REPO_DIR))
        print(f" Created sample archive at {ZIP_PATH}")

    # 3. Check if repository already exists
    repos = httpx.get(f"{BASE_URL}/repositories").json().get("repositories", [])
    existing = next((r for r in repos if r["name"] == "calculator"), None)

    repo_id = None
    if existing:
        print(f" Repository 'calculator' already exists (ID: {existing['id']})")
        repo_id = existing["id"]
        status = existing["status"]
    else:
        print(" Uploading sample calculator repository...")
        with open(ZIP_PATH, "rb") as f:
            upload_resp = httpx.post(
                f"{BASE_URL}/repositories/upload",
                files={"file": ("calculator.zip", f, "application/zip")},
                timeout=30.0,
            )
        if upload_resp.status_code != 200:
            print(f" Upload failed: {upload_resp.text}")
            sys.exit(1)
        repo_data = upload_resp.json()
        repo_id = repo_data["id"]
        status = repo_data["status"]
        print(f" Upload successful! Repository ID: {repo_id}")

    # 4. Wait for indexing to complete
    if status != "ready":
        print("⏳ Waiting for repository indexing (AST parsing, FAISS embedding, graph build)...")
        for _ in range(60):
            time.sleep(1.5)
            s_resp = httpx.get(f"{BASE_URL}/repositories/{repo_id}/status").json()
            curr_status = s_resp.get("status")
            progress = s_resp.get("progress", 0)
            msg = s_resp.get("progress_message", "")
            print(f"  → Status: {curr_status} ({progress}%) - {msg}")
            if curr_status == "ready":
                print(" Repository indexing completed successfully!")
                break
            elif curr_status == "failed":
                print(f" Repository indexing failed: {s_resp.get('error_message')}")
                sys.exit(1)

    # 5. Display stats
    repo_info = httpx.get(f"{BASE_URL}/repositories/{repo_id}").json()
    stats = repo_info.get("stats", {})
    print("\n Repository Statistics:")
    print(f"  - Source Files: {stats.get('files', 0)}")
    print(f"  - AST Chunks:   {stats.get('chunks', 0)}")
    print(f"  - Symbols:      {stats.get('symbols', 0)}")
    print(f"  - Graph Nodes:  {stats.get('graph_nodes', 0)}")
    print(f"  - Graph Edges:  {stats.get('graph_edges', 0)}")

    # 6. Ask sample questions in each tutor persona
    demo_questions = [
        ("developer", "How does division handle zero, and where is the exception raised?"),
        ("architect", "Explain the architecture of the parser and calculator modules."),
    ]

    print("\n Seeding initial tutor conversations...")
    for mode, q in demo_questions:
        print(f"  [{mode.upper()}] Asking: '{q}'...")
        chat_resp = httpx.post(
            f"{BASE_URL}/chat",
            json={
                "repository_id": repo_id,
                "question": q,
                "tutor_mode": mode,
            },
            timeout=60.0,
        )
        if chat_resp.status_code == 200:
            ans_data = chat_resp.json()
            citations = ans_data.get("citations", [])
            print(f"   Answer generated with {len(citations)} source citations!")
        else:
            print(f"  ⚠️ Chat failed: {chat_resp.text}")

    print("\n Demo environment successfully seeded!")
    print(f"Open frontend at: http://localhost:3000 to start exploring.")


if __name__ == "__main__":
    main()
