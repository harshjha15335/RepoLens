"""Persist the small files needed to reconstruct an ephemeral repository checkout.

The authoritative database is also the artifact store on Postgres. SQLite keeps
the existing disk-only behavior for local development.
"""

import asyncio
import io
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RepositoryValidationError
from app.models.models import Repository, RepositoryArtifact, generate_uuid

SOURCE_ZIP = "source_zip"
SOURCE_TREE = "source_tree"
SEARCH_INDEX = "search_index"
GIT_METADATA = "git_metadata"
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
_restore_locks: dict[tuple[str, str], asyncio.Lock] = {}


def enabled(db: AsyncSession) -> bool:
    """Only hosted Postgres instances need durable copies of local artifacts."""
    get_bind = getattr(db, "get_bind", None)
    return get_bind is not None and get_bind().dialect.name == "postgresql"


async def save_bytes(db: AsyncSession, repository_id: str, kind: str, payload: bytes):
    if not enabled(db):
        return
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise RepositoryValidationError("Repository artifact exceeds the 64 MB persistence limit")
    record = await db.get(RepositoryArtifact, (repository_id, kind))
    if record is None:
        db.add(RepositoryArtifact(repository_id=repository_id, kind=kind, payload=payload))
    else:
        record.payload = payload
        record.revision = generate_uuid()


async def save_file(db: AsyncSession, repository_id: str, kind: str, path: Path):
    if enabled(db):
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise RepositoryValidationError("Repository artifact exceeds the 64 MB persistence limit")
        await save_bytes(db, repository_id, kind, path.read_bytes())


async def delete(db: AsyncSession, repository_id: str, kind: str):
    if enabled(db):
        record = await db.get(RepositoryArtifact, (repository_id, kind))
        if record is not None:
            await db.delete(record)


def _archive_files(root: Path, files: list[Path]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            file.resolve().relative_to(root.resolve())
            relative = file.relative_to(root)
            with file.open("rb") as source, archive.open(relative.as_posix(), "w") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if output.tell() > MAX_ARTIFACT_BYTES:
                raise RepositoryValidationError("Repository source exceeds the 64 MB persistence limit")
    return output.getvalue()


async def save_source_tree(db: AsyncSession, repository_id: str, root: Path, files: list[Path]):
    if enabled(db):
        await save_bytes(db, repository_id, SOURCE_TREE, _archive_files(root, files))


async def save_index(db: AsyncSession, repository_id: str):
    if enabled(db):
        root = get_settings().indexes_path / repository_id
        files = [root / name for name in ("faiss.index", "bm25.index", "metadata.json", "chunk_mapping.json")]
        await save_bytes(db, repository_id, SEARCH_INDEX, _archive_files(root, [p for p in files if p.is_file()]))


def _restore_archive(payload: bytes, root: Path, max_file_bytes: int):
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        total = 0
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (info.is_dir() or path.is_absolute() or ".." in path.parts
                    or "\\" in info.filename or info.file_size > max_file_bytes
                    or info.external_attr >> 16 & 0o120000 == 0o120000):
                raise RepositoryValidationError("Stored repository artifact has an invalid file path")
            target = (root / info.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise RepositoryValidationError("Stored repository artifact escapes its directory")
            total += info.file_size
            if total > get_settings().max_extracted_bytes:
                raise RepositoryValidationError("Stored repository artifact exceeds extraction limits")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


async def ensure_source(db: AsyncSession, repository: Repository):
    """Hydrate source files on the instance serving this particular request."""
    if not enabled(db):
        return
    root = get_settings().repos_path / repository.id
    repository.storage_path = str(root)
    marker = root / "source" / ".repolens-restored"
    revision = await db.scalar(select(RepositoryArtifact.revision).where(
        RepositoryArtifact.repository_id == repository.id,
        RepositoryArtifact.kind == SOURCE_TREE,
    ))
    if revision is None or (marker.exists() and marker.read_text(encoding="ascii") == revision):
        return
    async with _restore_locks.setdefault((repository.id, SOURCE_TREE), asyncio.Lock()):
        if marker.exists() and marker.read_text(encoding="ascii") == revision:
            return
        artifact = await db.get(RepositoryArtifact, (repository.id, SOURCE_TREE))
        if artifact is None:
            return
        if (root / "source").exists():
            shutil.rmtree(root / "source")
        _restore_archive(artifact.payload, root / "source", get_settings().max_file_bytes)
        marker.write_text(artifact.revision, encoding="ascii")


async def ensure_upload(db: AsyncSession, repository: Repository):
    if not enabled(db):
        return
    root = get_settings().repos_path / repository.id
    repository.storage_path = str(root)
    path = root / "source.zip"
    if path.is_file():
        return
    artifact = await db.get(RepositoryArtifact, (repository.id, SOURCE_ZIP))
    if artifact is not None:
        root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact.payload)


async def ensure_git_metadata(db: AsyncSession, repository: Repository):
    if not enabled(db):
        return
    root = get_settings().repos_path / repository.id
    repository.storage_path = str(root)
    path = root / "source.json"
    if path.is_file():
        return
    artifact = await db.get(RepositoryArtifact, (repository.id, GIT_METADATA))
    if artifact is not None:
        root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact.payload)


async def ensure_index(db: AsyncSession, repository_id: str):
    if not enabled(db):
        return
    root = get_settings().indexes_path / repository_id
    marker = root / ".repolens-restored"
    revision = await db.scalar(select(RepositoryArtifact.revision).where(
        RepositoryArtifact.repository_id == repository_id,
        RepositoryArtifact.kind == SEARCH_INDEX,
    ))
    if revision is None or (marker.exists() and marker.read_text(encoding="ascii") == revision):
        return
    async with _restore_locks.setdefault((repository_id, SEARCH_INDEX), asyncio.Lock()):
        if marker.exists() and marker.read_text(encoding="ascii") == revision:
            return
        artifact = await db.get(RepositoryArtifact, (repository_id, SEARCH_INDEX))
        if artifact is None:
            return
        if root.exists():
            shutil.rmtree(root)
        _restore_archive(artifact.payload, root, MAX_ARTIFACT_BYTES)
        marker.write_text(artifact.revision, encoding="ascii")
