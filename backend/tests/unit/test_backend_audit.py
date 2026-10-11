"""Regressions for source parsing, call edges, and offline answers."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import repositories
from app.core import database
from app.core.config import Settings
from app.models.models import Chunk, EvaluationRun, GraphEdge, GraphNode, Repository, RepositoryFile
from app.services.generation.service import GenerationService
from app.services.graph.service import GraphService
from app.services.parsing.service import LANGUAGES, ParserService
from app.services.retrieval import service as retrieval_module


def test_typescript_and_tsx_use_tree_sitter(tmp_path: Path):
    assert "typescript" in LANGUAGES
    assert "tsx" in LANGUAGES

    source = tmp_path / "example.ts"
    source.write_text("export class Service { run() { return 1; } }", encoding="utf-8")
    result = ParserService().parse_file(source, tmp_path)
    assert any(symbol["name"] == "Service" for symbol in result["symbols"])

    source = tmp_path / "example.tsx"
    source.write_text("export function Widget() { return <div />; }", encoding="utf-8")
    result = ParserService().parse_file(source, tmp_path)
    assert any(symbol["name"] == "Widget" for symbol in result["symbols"])


def test_call_edges_resolve_methods_within_own_class():
    files = [
        {
            "file_path": "one.py",
            "language": "python",
            "content": "",
            "imports": [],
            "symbols": [
                {"name": "One", "type": "class", "content": "class One:\n def go(self): self.record()", "parent": None},
                {"name": "go", "type": "method", "content": "def go(self):\n self.record()", "parent": "One"},
                {"name": "record", "type": "method", "content": "def record(self):\n pass", "parent": "One"},
            ],
        },
        {
            "file_path": "two.py",
            "language": "python",
            "content": "",
            "imports": [],
            "symbols": [
                {"name": "Two", "type": "class", "content": "class Two:\n def record(self): pass", "parent": None},
                {"name": "record", "type": "method", "content": "def record(self):\n pass", "parent": "Two"},
            ],
        },
    ]
    graph = GraphService().build_graph(files, "repo")
    calls = {(edge["source"], edge["target"]) for edge in graph["edges"] if edge["type"] == "CALLS"}
    assert calls == {("method:one.py:One.go", "method:one.py:One.record")}


def test_offline_answer_only_reports_retrieved_evidence():
    service = GenerationService.__new__(GenerationService)
    chunks = [{
        "chunk_id": "c1", "file_path": "math.py", "symbol_name": "square",
        "start_line": 1, "end_line": 2, "content": "def square(x):\n    return x * x",
    }]
    answer = service._offline_grounded_synthesis("What does square do?", "beginner", chunks)
    assert "[math.py:1-2]" in answer
    assert "def square(x)" in answer
    assert "history" not in answer
    assert "division" not in answer
    assert service._extract_citations(answer, chunks)[0]["file_path"] == "math.py"
    assert not service._extract_citations("See [math.py:999-1000]", chunks)


@pytest.mark.asyncio
async def test_repository_delete_cascades_graph_and_evaluation(tmp_path: Path, monkeypatch):
    await database.close_db()
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'audit.db').as_posix()}",
    )
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(repositories, "get_settings", lambda: settings)
    try:
        await database.init_db()
        factory = database.get_session_factory()
        async with factory() as db:
            repo = Repository(name="sample", source_type="git")
            db.add(repo)
            await db.flush()
            source = GraphNode(repository_id=repo.id, node_type="class", name="A")
            target = GraphNode(repository_id=repo.id, node_type="class", name="B")
            db.add_all([source, target])
            await db.flush()
            db.add(GraphEdge(repository_id=repo.id, source_id=source.id,
                             target_id=target.id, relationship_type="INHERITS"))
            db.add(EvaluationRun(repository_id=repo.id, strategy="hybrid"))
            await db.commit()
            await repositories.delete_repository(repo.id, db)
            async with factory() as verification:
                assert await verification.get(Repository, repo.id) is None
            for table in (GraphNode, GraphEdge, EvaluationRun):
                count = await db.scalar(select(func.count()).select_from(table))
                assert count == 0
    finally:
        await database.close_db()


@pytest.mark.asyncio
async def test_interview_feedback_uses_question_target_source():
    source = SimpleNamespace(file_path="calculator.py", start_line=4, end_line=12,
                             symbol_name="Calculator (part 1)", chunk_index=0,
                             content="class Calculator:\n    def divide(self, value): return value / 2")
    unrelated = SimpleNamespace(file_path="calculator.py", start_line=1, end_line=2,
                                symbol_name=None, content="import unrelated")
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [unrelated, source]))
    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(id="repo")),
                         execute=AsyncMock(return_value=result))
    feedback = await repositories.evaluate_interview_answer("repo", {
        "question": "Explain Calculator", "user_answer": "Calculator implements divide",
        "target_symbols": ["Calculator"], "target_files": ["calculator.py"],
    }, db)
    assert len(feedback["citations"]) == 1
    assert feedback["citations"][0]["start_line"] == 4
    assert "divide" in feedback["what_was_correct"]
    assert "unrelated" not in feedback["grounded_explanation"]


@pytest.mark.asyncio
async def test_requested_graph_expansion_promotes_a_connected_symbol(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retrieval.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(retrieval_module, "get_session_factory", lambda: factory)
    async with engine.begin() as connection:
        await connection.run_sync(database.Base.metadata.create_all)
    try:
        async with factory() as db:
            repo = Repository(name="graph", source_type="zip")
            db.add(repo)
            await db.flush()
            source_file = RepositoryFile(repository_id=repo.id, path="graph.py")
            db.add(source_file)
            await db.flush()
            for index, name in enumerate(("caller", "filler_one", "filler_two", "callee")):
                db.add(Chunk(repository_id=repo.id, file_id=source_file.id,
                             chunk_index=index, file_path="graph.py", symbol_name=name,
                             symbol_type="function", content=f"def {name}(): pass",
                             start_line=index + 1, end_line=index + 1))
            caller = GraphNode(repository_id=repo.id, node_type="function", name="caller")
            callee = GraphNode(repository_id=repo.id, node_type="function", name="callee")
            db.add_all([caller, callee])
            await db.flush()
            db.add(GraphEdge(repository_id=repo.id, source_id=caller.id,
                             target_id=callee.id, relationship_type="CALLS"))
            await db.commit()

        retrieval = retrieval_module.RetrievalService()
        monkeypatch.setattr(retrieval, "_bm25_search", lambda *_: [(0, 3.0), (1, 2.0), (2, 1.0)])
        base = await retrieval.search(repo.id, "Explain caller", top_k=2, strategy="bm25",
                                      enable_graph_expansion=False, enable_mmr=False)
        expanded = await retrieval.search(repo.id, "Explain caller", top_k=2, strategy="bm25",
                                          enable_graph_expansion=True, enable_mmr=False)
        assert [chunk["symbol_name"] for chunk in base["chunks"]] == ["caller", "filler_one"]
        assert [chunk["symbol_name"] for chunk in expanded["chunks"]] == ["caller", "callee"]
        assert expanded["chunks"][1]["source"] == "graph_expansion"
    finally:
        await engine.dispose()
