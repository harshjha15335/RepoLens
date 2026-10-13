"""Selected-code chat uses indexed source and keeps it ahead of retrieval."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.chat import _resolve_code_context
from app.core.errors import RepositoryValidationError
from app.schemas.schemas import ChatRequest, CodeContext
from app.services.generation.service import GenerationService


def test_chat_request_accepts_optional_structured_selection():
    request = ChatRequest(
        repository_id="repo",
        question="Explain this",
        code_context={"file_path": "main.py", "start_line": 2, "end_line": 3},
    )
    assert request.code_context.file_path == "main.py"
    assert ChatRequest(repository_id="repo", question="Explain this").code_context is None
    with pytest.raises(ValidationError):
        ChatRequest(repository_id="repo", question="Explain", code_context={
            "file_path": "main.py", "start_line": 0, "end_line": 1,
        })


@pytest.mark.asyncio
async def test_selection_resolves_indexed_source_and_ignores_client_text(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("first\nactual line\nthird\n", encoding="utf-8")
    repo = SimpleNamespace(id="repo", storage_path=str(tmp_path))
    result = SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(path="main.py"))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    context = await _resolve_code_context(repo, CodeContext(
        file_path="main.py", start_line=2, end_line=3, text="forged code"
    ), db)
    assert context["content"] == "actual line\nthird"
    assert context["selected"] is True
    assert "forged" not in str(context)

    with pytest.raises(RepositoryValidationError, match="exceeds"):
        await _resolve_code_context(repo, CodeContext(
            file_path="main.py", start_line=2, end_line=8
        ), db)
    with pytest.raises(RepositoryValidationError, match="invalid"):
        await _resolve_code_context(repo, CodeContext(
            file_path="main.py", start_line=3, end_line=2
        ), db)


@pytest.mark.asyncio
async def test_selection_rejects_unindexed_or_escaping_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "secret.py").write_text("secret", encoding="utf-8")
    repo = SimpleNamespace(id="repo", storage_path=str(tmp_path))
    absent = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: None
    )))
    with pytest.raises(RepositoryValidationError, match="not indexed"):
        await _resolve_code_context(repo, CodeContext(
            file_path="main.py", start_line=1, end_line=1
        ), absent)

    indexed = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: object()
    )))
    with pytest.raises(RepositoryValidationError, match="unavailable"):
        await _resolve_code_context(repo, CodeContext(
            file_path="../secret.py", start_line=1, end_line=1
        ), indexed)


@pytest.mark.asyncio
async def test_generation_prioritizes_selection_and_validates_its_citation():
    selected = {
        "file_path": "main.py", "start_line": 10, "end_line": 11,
        "content": "selected actual source", "selected": True,
        "action": "trace",
    }
    retrieved = {
        "chunk_id": "other", "file_path": "other.py", "start_line": 1,
        "end_line": 2, "content": "retrieved context",
    }
    provider = SimpleNamespace(generate=AsyncMock(return_value="See [main.py:10-11]."))
    service = GenerationService.__new__(GenerationService)
    service.provider = provider
    service.retrieval = SimpleNamespace(search=AsyncMock(return_value={
        "chunks": [retrieved], "latency_ms": 2,
    }))
    service.settings = SimpleNamespace(context_token_budget=100, generation_max_tokens=200)

    answer = await service.generate_answer("repo", "Trace", code_context=selected,
                                          conversation_history=[{"role": "assistant", "content": "obsolete explanation"}])
    prompt = provider.generate.await_args.args[0][1]["content"]
    assert prompt.index("Selected code: main.py") < prompt.index("other.py")
    assert "selected actual source" in prompt
    assert "10 | selected actual source" in prompt
    assert "short ordered sequence" in prompt
    assert "obsolete explanation" not in prompt
    assert answer["citations"][0]["file_path"] == "main.py"
    assert answer["metadata"]["selected_code"] is True

    service.settings.context_token_budget = 1
    context = service._build_context([selected, retrieved], budget=1)
    assert "selected actual source" in context
    assert "retrieved context" not in context


@pytest.mark.asyncio
async def test_generation_exposes_retrieved_source_when_model_omits_citations():
    chunk = {
        "chunk_id": "c1", "file_path": "src/calculator.py", "start_line": 4,
        "end_line": 12, "content": "class Calculator: pass",
    }
    service = GenerationService.__new__(GenerationService)
    service.provider = SimpleNamespace(generate=AsyncMock(return_value="Calculator is a class."))
    service.retrieval = SimpleNamespace(search=AsyncMock(return_value={
        "chunks": [chunk], "latency_ms": 1,
    }))
    service.settings = SimpleNamespace(context_token_budget=100, generation_max_tokens=200)

    result = await service.generate_answer("repo", "What is Calculator?")

    assert "Retrieved source to inspect: [src/calculator.py:4-12]" in result["answer"]
    assert result["citations"][0]["file_path"] == "src/calculator.py"
