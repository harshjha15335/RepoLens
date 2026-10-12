"""Adversarial regressions for repository and evaluation inputs."""

import io
import json
import pickle
import socket
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, UploadFile

from app.api import evaluation, repositories
from app.core.config import Settings
from app.core.errors import (
    ArchiveSecurityError,
    EvaluationError,
    IndexError_,
    RepositoryValidationError,
)
from app.models.models import RepositoryStatus
from app.schemas.schemas import EvaluationRequest, GitImportRequest
from app.services.evaluation import service as evaluation_module
from app.services.indexing.service import BM25Index, IndexingService
from app.services.ingestion import service as ingestion_module
from app.services.ingestion.service import IngestionService, validate_git_url
from app.services.retrieval import service as retrieval_module
from app.services.retrieval.service import RetrievalService


@pytest.fixture
def public_dns(monkeypatch):
    def resolver(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.3", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", resolver)


@pytest.mark.parametrize("url", [
    "http://github.com/owner/repo", "git@github.com:owner/repo.git", "file:///tmp/repo",
    "ext::sh -c evil", "https://127.0.0.1/owner/repo", "https://169.254.169.254/owner/repo",
    "https://localhost/owner/repo", "https://github.com.evil.test/owner/repo",
    "https://github.com:443/owner/repo", "https://user:secret@github.com/owner/repo",
    "https://github.com./owner/repo", "https://github.com/owner/repo?token=secret",
    "https://github.com/owner/repo#fragment", "https://github.com/owner/repo/extra",
    "https://github.com/owner/../repo", "https://github.com/owner/%2e%2e",
    "https://github.com/owner/repo/", "https://github.com/owner\\repo",
    "https://github.com/owner/\trepo", "https://github.com/\nowner/repo",
])
async def test_git_rejects_noncanonical_destinations_before_creating_records(url):
    db = SimpleNamespace(add=lambda *_: pytest.fail("unsafe URL created a record"))
    with pytest.raises(RepositoryValidationError):
        await repositories.import_git_repository(GitImportRequest(url=url), BackgroundTasks(), db)


@pytest.mark.parametrize("host", ["github.com", "gitlab.com", "bitbucket.org"])
async def test_git_accepts_approved_public_https_hosts(host, public_dns):
    url = f"https://{host}/owner/repo.git"
    assert await validate_git_url(url) == url


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1", "224.0.0.1"])
async def test_git_rejects_any_private_dns_answer(address, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.3", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
    ])
    with pytest.raises(RepositoryValidationError, match="public addresses"):
        await validate_git_url("https://github.com/owner/repo")


async def test_git_fails_closed_when_dns_cannot_resolve(monkeypatch):
    def failed_resolution(*_args, **_kwargs):
        raise socket.gaierror("unavailable")

    monkeypatch.setattr(socket, "getaddrinfo", failed_resolution)
    with pytest.raises(RepositoryValidationError, match="Cannot resolve"):
        await validate_git_url("https://github.com/owner/repo")


async def test_clone_disables_redirects_helpers_external_protocols_and_submodules(tmp_path, monkeypatch, public_dns):
    settings = Settings(data_dir=str(tmp_path))
    commands = []

    async def subprocess(*args, **kwargs):
        commands.append((args, kwargs))
        return SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b"", b"")))

    monkeypatch.setattr(ingestion_module.asyncio, "create_subprocess_exec", subprocess)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.file:///secret/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    await IngestionService._clone_git("https://github.com/owner/repo", settings.repos_path / "repo" / "source", None, settings)
    args, kwargs = commands[0]
    for setting in ("protocol.allow=never", "protocol.https.allow=always", "http.followRedirects=false", "credential.helper=", "submodule.recurse=false"):
        assert setting in args
    assert "--no-recurse-submodules" in args
    assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "https"
    assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_CONFIG_COUNT" not in kwargs["env"]
    assert "HTTPS_PROXY" not in kwargs["env"]


async def test_oversized_upload_reads_bounded_chunks_and_cleans_staging(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path), max_upload_mb=1)
    monkeypatch.setattr(repositories, "get_settings", lambda: settings)
    upload = UploadFile(filename="large.zip", file=io.BytesIO(b"z" * (2 * 1024 * 1024)))
    original_read = upload.read
    sizes = []

    async def bounded_read(size=-1):
        assert size > 0
        sizes.append(size)
        return await original_read(size)

    upload.read = bounded_read
    db = SimpleNamespace(rollback=AsyncMock(), add=lambda *_: pytest.fail("oversized upload persisted"))
    tasks = BackgroundTasks()
    with pytest.raises(RepositoryValidationError, match="maximum upload"):
        await repositories.upload_repository(upload, tasks, db)
    assert sizes == [1024 * 1024, 1024 * 1024]
    assert list(settings.repos_path.iterdir()) == []
    assert upload.file.closed
    assert tasks.tasks == []


async def test_upload_read_failure_cleans_partial_staging(tmp_path, monkeypatch):
    settings = Settings(data_dir=str(tmp_path))
    monkeypatch.setattr(repositories, "get_settings", lambda: settings)
    upload = UploadFile(filename="broken.zip", file=io.BytesIO(b"partial"))
    upload.read = AsyncMock(side_effect=[b"partial", OSError("client disconnected")])
    db = SimpleNamespace(rollback=AsyncMock())
    with pytest.raises(OSError, match="disconnected"):
        await repositories.upload_repository(upload, BackgroundTasks(), db)
    assert list(settings.repos_path.iterdir()) == []
    assert upload.file.closed


def test_zip_containment_rejects_shared_prefix_sibling_without_symlink_privileges(tmp_path, monkeypatch):
    root = tmp_path / "source"
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("linked/secret.py", "secret = 1")
    original_resolve = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == root / "linked" / "secret.py":
            return tmp_path / "source-secret" / "secret.py"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ArchiveSecurityError, match="traversal"):
        IngestionService._extract_zip(str(archive), root, Settings(data_dir=str(tmp_path)))


def create_symlink(link: Path, target: Path, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("Creating symlinks requires OS privileges")


def test_zip_rejects_symlink_to_sibling_with_shared_prefix(tmp_path):
    root = tmp_path / "source"
    sibling = tmp_path / "source-secret"
    root.mkdir()
    sibling.mkdir()
    create_symlink(root / "linked", sibling, directory=True)
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("linked/secret.py", "secret = 1")
    with pytest.raises(ArchiveSecurityError, match="traversal"):
        IngestionService._extract_zip(str(archive), root, Settings(data_dir=str(tmp_path)))
    assert not (sibling / "secret.py").exists()


def test_zip_rejects_archived_symlinks(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        entry = zipfile.ZipInfo("link.py")
        entry.external_attr = 0o120777 << 16
        zf.writestr(entry, "../secret.py")
    with pytest.raises(ArchiveSecurityError, match="Symlink"):
        IngestionService._extract_zip(str(archive), tmp_path / "source", Settings(data_dir=str(tmp_path)))


def test_discovery_skips_file_symlink_to_shared_prefix_sibling(tmp_path):
    root = tmp_path / "source"
    sibling = tmp_path / "source-secret"
    root.mkdir()
    sibling.mkdir()
    (root / "safe.py").write_text("safe = 1")
    (sibling / "secret.py").write_text("secret = 1")
    create_symlink(root / "leak.py", sibling / "secret.py")
    assert IngestionService._discover_files(root, Settings(data_dir=str(tmp_path))) == [root / "safe.py"]


@pytest.mark.parametrize("relative", ["../secret.json", "../datasets-secret/secret.json", "default.txt"])
def test_dataset_rejects_traversal_and_wrong_type(relative, tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation_module, "DEFAULT_DATASET", tmp_path / "datasets" / "default.json")
    with pytest.raises(EvaluationError, match="bundled"):
        evaluation_module.EvaluationService._load_dataset(relative, None)


async def test_evaluation_rejects_external_path_before_queueing(tmp_path):
    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status=RepositoryStatus.READY)),
                         add=lambda *_: pytest.fail("external dataset persisted"))
    tasks = BackgroundTasks()
    with pytest.raises(EvaluationError, match="bundled"):
        await evaluation.run_evaluation(EvaluationRequest(repository_id="repo", dataset_path=str(tmp_path / "secret.json")), tasks, db)
    assert not tasks.tasks


def test_dataset_rejects_symlink_escape(tmp_path, monkeypatch):
    approved = tmp_path / "datasets"
    approved.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text("{}")
    create_symlink(approved / "secret.json", secret)
    monkeypatch.setattr(evaluation_module, "DEFAULT_DATASET", approved / "default.json")
    with pytest.raises(EvaluationError, match="bundled"):
        evaluation_module.EvaluationService._load_dataset("secret.json", None)


def test_bm25_json_roundtrip_preserves_search_results(tmp_path):
    index = BM25Index()
    index.build([{"content": "def computeTotal(value): return value", "content_hash": "c1"},
                 {"content": "def get_name(): return name", "content_hash": "c2"}])
    path = tmp_path / "bm25.index"
    index.save(str(path))
    assert json.loads(path.read_text())["version"] == 1
    loaded = BM25Index.load(str(path))
    assert loaded.search("compute total") == index.search("compute total")
    assert loaded.chunk_ids == ["c1", "c2"]


def test_bm25_never_executes_legacy_pickle(tmp_path):
    marker = tmp_path / "executed"

    class Exploit:
        def __reduce__(self):
            return (Path.write_text, (marker, "unsafe"))

    path = tmp_path / "bm25.index"
    path.write_bytes(pickle.dumps(Exploit()))
    with pytest.raises(IndexError_, match="Reindex"):
        BM25Index.load(str(path))
    assert not marker.exists()


@pytest.mark.parametrize("change", [
    {"version": 2}, {"version": True}, {"k1": -1}, {"k1": 10 ** 400},
    {"b": float("nan")}, {"documents": {"bad": []}},
    {"documents": [{"chunk_id": 1, "tokens": ["term"]}]},
    {"documents": [{"chunk_id": "c1", "tokens": [1]}]},
])
def test_bm25_validates_artifact_schema(change, tmp_path):
    data = {"version": 1, "k1": 1.5, "b": 0.75, "documents": []} | change
    path = tmp_path / "bm25.index"
    path.write_text(json.dumps(data))
    with pytest.raises(IndexError_, match="Reindex"):
        BM25Index.load(str(path))


def test_legacy_bm25_error_remains_actionable_at_retrieval(monkeypatch):
    retrieval = RetrievalService.__new__(RetrievalService)
    retrieval.indexing_service = IndexingService()
    monkeypatch.setattr(retrieval.indexing_service, "load_bm25_index", lambda *_: BM25Index.load("missing"))
    with pytest.raises(IndexError_, match="Reindex"):
        retrieval._bm25_search("repo", "question", 5)


async def test_explicit_graph_strategy_enables_expansion_when_toggle_is_false(monkeypatch):
    chunk = SimpleNamespace(id="c1", file_path="safe.py", symbol_name="caller", symbol_type="function",
                            content="def caller(): pass", start_line=1, end_line=1, parent_symbol=None,
                            language="python", imports=[], definitions=[])

    @asynccontextmanager
    async def session():
        yield SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [chunk]))))

    monkeypatch.setattr(retrieval_module, "get_session_factory", lambda: session)
    retrieval = RetrievalService()
    monkeypatch.setattr(retrieval, "_dense_search", AsyncMock(return_value=[]))
    monkeypatch.setattr(retrieval, "_bm25_search", lambda *_: [(0, 1.0)])
    expansion = AsyncMock(side_effect=lambda _repo, chunks, _all, _k: chunks)
    monkeypatch.setattr(retrieval, "_expand_with_graph", expansion)
    await retrieval.search("repo", "Explain caller", strategy="graph_expansion", enable_graph_expansion=False,
                           enable_mmr=False, enable_reranking=False)
    expansion.assert_awaited_once()
