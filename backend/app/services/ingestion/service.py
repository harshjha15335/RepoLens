"""Repository ingestion service — orchestrates the full pipeline."""

import asyncio
import hashlib
import ipaddress
import os
import re
import shutil
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import ArchiveSecurityError, RepositoryValidationError
from app.core.logging import get_logger
from app.models.models import (
    Chunk,
    GraphEdge,
    GraphNode,
    Repository,
    RepositoryFile,
    RepositoryStatus,
)
from app.services.chunking.service import ChunkingService
from app.services.embeddings.service import EmbeddingService
from app.services.graph.service import GraphService
from app.services.indexing.service import IndexingService
from app.services.parsing.service import ParserService

logger = get_logger(__name__)
GIT_HOSTS = frozenset({"github.com", "gitlab.com", "bitbucket.org"})
GIT_SECURITY_CONFIG = (
    "protocol.allow=never", "protocol.https.allow=always", "http.followRedirects=false",
    "credential.helper=", "core.hooksPath=" + os.devnull, "submodule.recurse=false",
    "http.proxy=", "http.extraHeader=", "http.sslVerify=true",
)


async def validate_git_url(url: str) -> str:
    """Accept canonical public HTTPS repository URLs before invoking Git.

    DNS is checked again by the worker. Git performs its own connection lookup,
    so deployment egress controls remain necessary against DNS rebinding.
    """
    url = url.strip()
    try:
        parsed = urlsplit(url)
        valid = (
            all(32 < ord(char) < 127 for char in url)
            and parsed.scheme == "https" and parsed.hostname in GIT_HOSTS
            and parsed.netloc == parsed.hostname and not parsed.query and not parsed.fragment
            and re.fullmatch(r"/[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", parsed.path)
        )
    except ValueError:
        valid = False
    if not valid:
        raise RepositoryValidationError(
            "Use a canonical HTTPS owner/repository URL on github.com, gitlab.com, or bitbucket.org"
        )
    if parsed.path.rsplit("/", 1)[-1].removesuffix(".git") in ("", ".", ".."):
        raise RepositoryValidationError("Invalid Git repository path")
    try:
        addresses = await asyncio.wait_for(
            asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM),
            timeout=10,
        )
        if not addresses or any(
            not ipaddress.ip_address(address[4][0]).is_global
            or ipaddress.ip_address(address[4][0]).is_multicast
            for address in addresses
        ):
            raise RepositoryValidationError("Git host must resolve only to public addresses")
    except (OSError, ValueError, asyncio.TimeoutError) as exc:
        raise RepositoryValidationError("Cannot resolve Git host to public addresses") from exc
    return url

# File extensions to process
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".cc",
    ".h", ".hpp", ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".kt",
    ".scala", ".r", ".R", ".m", ".mm", ".lua", ".pl", ".pm",
    ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".graphql", ".gql",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".svg",
    ".md", ".rst", ".txt",
    ".dockerfile", ".dockerignore",
    ".gitignore", ".editorconfig",
    ".env.example",
}

# Documentation file names
DOC_FILES = {
    "readme.md", "readme.rst", "readme.txt", "readme",
    "changelog.md", "changelog.txt", "changes.md",
    "contributing.md", "license", "license.md", "license.txt",
}

# Package manifest files
MANIFEST_FILES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "cargo.toml", "go.mod", "go.sum", "pom.xml", "build.gradle",
    "gemfile", "requirements.txt", "pipfile", "composer.json",
    "makefile", "cmakelists.txt",
}

# Directories to exclude
EXCLUDED_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".tox",
    ".eggs", "*.egg-info", ".cache", ".gradle", ".idea", ".vscode",
    "vendor", "target", "bin", "obj", "out",
    ".terraform", ".serverless",
    "coverage", "htmlcov", ".nyc_output",
}

# Binary extensions to skip
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".o", ".a", ".lib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pyc", ".pyo", ".class", ".jar",
    ".sqlite", ".db",
    ".lock",
}


class IngestionService:
    """Orchestrates the full repository ingestion pipeline."""

    @staticmethod
    async def run_ingestion(
        repository_id: str,
        source: str,
        source_type: str,
        branch: str | None = None,
    ):
        """Run the complete ingestion pipeline as a background task."""
        factory = get_session_factory()
        settings = get_settings()

        async with factory() as db:
            try:
                repo = await db.get(Repository, repository_id)
                if not repo:
                    logger.error(f"Repository {repository_id} not found")
                    return

                repo_dir = Path(repo.storage_path)
                source_dir = repo_dir / "source"

                # Step 1: Extract/Clone
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.DISCOVERING, 5,
                    "Extracting repository..."
                )

                if source_type == "zip":
                    IngestionService._extract_zip(source, source_dir, settings)
                elif source_type == "git":
                    await IngestionService._clone_git(source, source_dir, branch, settings)
                else:
                    # Re-use existing source directory for reindex
                    if not source_dir.exists():
                        raise RepositoryValidationError("Source directory not found")

                # Step 2: Discover files
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.DISCOVERING, 10,
                    "Discovering files..."
                )

                files = IngestionService._discover_files(source_dir, settings)
                logger.info(f"Discovered {len(files)} files in {repo.name}")

                if not files:
                    raise RepositoryValidationError("No processable files found in repository")

                # Save file records
                await IngestionService._save_file_records(db, repo, files, source_dir)
                repo.file_count = len(files)
                await db.commit()

                # Step 3: Parse files
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.PARSING, 20,
                    f"Parsing {len(files)} files..."
                )

                parser = ParserService()
                parsed_files = []
                for i, file_path in enumerate(files):
                    try:
                        result = parser.parse_file(file_path, source_dir)
                        if result:
                            parsed_files.append(result)
                    except Exception as e:
                        logger.warning(f"Failed to parse {file_path}: {e}")

                    if i % 50 == 0:
                        progress = 20 + int((i / len(files)) * 15)
                        await IngestionService._update_status(
                            db, repo, RepositoryStatus.PARSING, progress,
                            f"Parsing files... ({i}/{len(files)})"
                        )

                logger.info(f"Parsed {len(parsed_files)} files successfully")

                # Step 4: Chunk
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.CHUNKING, 40,
                    "Creating code chunks..."
                )

                chunker = ChunkingService()
                all_chunks = []
                for pf in parsed_files:
                    chunks = chunker.chunk_parsed_file(pf)
                    all_chunks.extend(chunks)

                logger.info(f"Created {len(all_chunks)} chunks")

                # Save chunks to DB
                await IngestionService._save_chunks(db, repo, all_chunks)
                repo.chunk_count = len(all_chunks)

                # Count symbols
                symbol_names = set()
                for c in all_chunks:
                    if c.get("symbol_name"):
                        symbol_names.add(c["symbol_name"])
                repo.symbol_count = len(symbol_names)
                await db.commit()

                # Step 5: Build graph
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.BUILDING_GRAPH, 55,
                    "Building code graph..."
                )

                graph_service = GraphService()
                graph_data = graph_service.build_graph(parsed_files, repository_id)
                await IngestionService._save_graph(db, repo, graph_data)
                repo.graph_node_count = len(graph_data.get("nodes", []))
                repo.graph_edge_count = len(graph_data.get("edges", []))
                await db.commit()

                logger.info(
                    f"Graph: {repo.graph_node_count} nodes, {repo.graph_edge_count} edges"
                )

                # Step 6: Generate embeddings
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.EMBEDDING, 65,
                    "Generating embeddings..."
                )

                embedding_service = EmbeddingService()
                texts = [c.get("content", "") for c in all_chunks]
                embeddings = await embedding_service.embed_documents(texts)

                logger.info(f"Generated {len(embeddings)} embeddings")

                # Step 7: Build indexes
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.INDEXING, 80,
                    "Building search indexes..."
                )

                indexing_service = IndexingService()
                await indexing_service.build_indexes(
                    repository_id=repository_id,
                    chunks=all_chunks,
                    embeddings=embeddings,
                    embedding_metadata=embedding_service.metadata,
                )

                # Update FAISS index mappings in DB
                chunk_records = (await db.execute(
                    select(Chunk).where(Chunk.repository_id == repository_id).order_by(Chunk.chunk_index)
                )).scalars().all()

                for i, chunk_record in enumerate(chunk_records):
                    chunk_record.faiss_index = i
                await db.commit()

                # Detect languages
                languages = set()
                for pf in parsed_files:
                    if pf.get("language"):
                        languages.add(pf["language"])
                repo.languages = sorted(languages)

                # Mark as ready
                from datetime import datetime, timezone
                await IngestionService._update_status(
                    db, repo, RepositoryStatus.READY, 100,
                    "Repository indexed successfully"
                )
                repo.indexed_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    f"Ingestion complete for {repo.name}: "
                    f"{repo.file_count} files, {repo.chunk_count} chunks, "
                    f"{repo.symbol_count} symbols"
                )

            except Exception as e:
                logger.exception(f"Ingestion failed for {repository_id}: {e}")
                try:
                    repo = await db.get(Repository, repository_id)
                    if repo:
                        repo.status = RepositoryStatus.FAILED
                        repo.error_message = str(e)[:500]
                        await db.commit()
                except Exception:
                    logger.exception("Failed to update repository status to FAILED")

    @staticmethod
    async def _update_status(
        db: AsyncSession,
        repo: Repository,
        status: RepositoryStatus,
        progress: int,
        message: str,
    ):
        """Update repository ingestion status."""
        repo.status = status
        repo.progress = progress
        repo.progress_message = message
        await db.commit()

    @staticmethod
    def _extract_zip(zip_path: str, target_dir: Path, settings):
        """Securely extract a ZIP archive."""
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Security checks
            total_size = 0
            file_count = 0

            for info in zf.infolist():
                # Check for path traversal (Zip Slip)
                member_path = Path(info.filename)
                if member_path.is_absolute():
                    raise ArchiveSecurityError(
                        f"Absolute path in archive: {info.filename}"
                    )

                # Normalize and check for traversal
                resolved = (target_dir / info.filename).resolve()
                if not resolved.is_relative_to(target_dir.resolve()):
                    raise ArchiveSecurityError(
                        f"Path traversal detected: {info.filename}"
                    )

                # Check for dangerous filenames
                parts = Path(info.filename).parts
                for part in parts:
                    if part in ("..", "~") or part.startswith(".."):
                        raise ArchiveSecurityError(
                            f"Dangerous path component: {info.filename}"
                        )

                # Check for symlinks
                if info.external_attr >> 16 & 0o120000 == 0o120000:
                    raise ArchiveSecurityError(
                        f"Symlink in archive: {info.filename}"
                    )

                total_size += info.file_size
                if not info.is_dir():
                    file_count += 1

                # Decompression bomb check
                if total_size > settings.max_extracted_bytes:
                    raise ArchiveSecurityError(
                        f"Extracted size exceeds {settings.max_extracted_mb}MB limit"
                    )

                if file_count > settings.max_repository_files:
                    raise ArchiveSecurityError(
                        f"Archive contains more than {settings.max_repository_files} files"
                    )

            # Extract safely
            zf.extractall(target_dir)

        # If the ZIP contains a single top-level directory, flatten it
        contents = list(target_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            inner = contents[0]
            temp_dir = target_dir.parent / f"{target_dir.name}_temp"
            shutil.move(str(inner), str(temp_dir))
            shutil.rmtree(str(target_dir))
            shutil.move(str(temp_dir), str(target_dir))

    @staticmethod
    async def _clone_git(url: str, target_dir: Path, branch: str | None, settings):
        """Clone or refresh the application-owned checkout on its selected branch."""
        target_dir = target_dir.resolve()
        if not target_dir.is_relative_to(settings.repos_path.resolve()):
            raise RepositoryValidationError("Git checkout must be inside repository storage")
        url = await validate_git_url(url)
        if branch is not None and (not branch.strip() or branch.startswith("-") or "\x00" in branch):
            raise RepositoryValidationError("Invalid Git branch")
        target_dir.mkdir(parents=True, exist_ok=True)

        # Ignore inherited Git configuration and prevent helpers/protocols from
        # expanding a validated URL into a different transport or destination.
        git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        git_env.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "https",
        })
        for key in tuple(git_env):
            if key.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
                git_env.pop(key)
        config_args = [arg for setting in GIT_SECURITY_CONFIG for arg in ("-c", setting)]

        async def run_git(*args: str) -> str:
            proc = await asyncio.create_subprocess_exec(
                "git", *config_args, *args, env=git_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RepositoryValidationError("Git operation timed out (300s limit)")
            if proc.returncode != 0:
                raise RepositoryValidationError(
                    f"Git operation failed: {stderr.decode(errors='replace')[:300]}"
                )
            return stdout.decode(errors="replace").strip()

        if (target_dir / ".git").is_dir():
            selected_branch = branch or await run_git(
                "-C", str(target_dir), "symbolic-ref", "--short", "HEAD"
            )
            await run_git("-C", str(target_dir), "fetch", "--depth", "1", "--", url, selected_branch)
            await run_git("-C", str(target_dir), "checkout", "-B", selected_branch, "FETCH_HEAD")
            await run_git("-C", str(target_dir), "reset", "--hard", "FETCH_HEAD")
        else:
            args = ["clone", "--depth", "1", "--no-recurse-submodules"]
            if branch:
                args.extend(["--branch", branch])
            await run_git(*args, "--", url, str(target_dir))

    @staticmethod
    def _discover_files(source_dir: Path, settings) -> list[Path]:
        """Discover processable files in the repository."""
        files = []
        source_root = source_dir.resolve()

        for root, dirs, filenames in os.walk(source_dir):
            # Filter excluded directories in-place
            dirs[:] = [
                d for d in dirs
                if d.lower() not in EXCLUDED_DIRS
                and not d.startswith(".")
                and not d.endswith(".egg-info")
                and not (Path(root) / d).is_symlink()
                and (Path(root) / d).resolve().is_relative_to(source_root)
            ]

            for filename in filenames:
                file_path = Path(root) / filename
                rel_path = file_path.relative_to(source_dir)

                # Skip binary files
                ext = file_path.suffix.lower()
                if ext in BINARY_EXTENSIONS:
                    continue

                # Check if file is a known type
                is_supported = (
                    ext in SUPPORTED_EXTENSIONS
                    or filename.lower() in DOC_FILES
                    or filename.lower() in MANIFEST_FILES
                    or filename.lower().startswith("dockerfile")
                    or filename.lower() == "makefile"
                )

                if not is_supported:
                    continue

                # Check file size
                try:
                    size = file_path.stat().st_size
                    if size > settings.max_file_bytes:
                        logger.debug(f"Skipping large file: {rel_path} ({size} bytes)")
                        continue
                    if size == 0:
                        continue
                except OSError:
                    continue

                # Verify it's not a symlink escaping the repo
                try:
                    resolved = file_path.resolve()
                    if not resolved.is_relative_to(source_root):
                        logger.warning(f"Symlink escape detected: {rel_path}")
                        continue
                except (OSError, ValueError):
                    continue

                files.append(file_path)
                if len(files) > settings.max_repository_files:
                    raise RepositoryValidationError("Repository contains too many processable files")

        return sorted(files)

    @staticmethod
    async def _save_file_records(
        db: AsyncSession,
        repo: Repository,
        files: list[Path],
        source_dir: Path,
    ):
        """Replace file and chunk records for this repository before reindexing."""
        # Chunks reference files. Delete both in the same transaction as the
        # replacement file rows so a retry cannot accumulate duplicate paths.
        await db.execute(delete(Chunk).where(Chunk.repository_id == repo.id))
        await db.execute(delete(RepositoryFile).where(RepositoryFile.repository_id == repo.id))
        for file_path in files:
            rel_path = str(file_path.relative_to(source_dir))
            content_hash = None
            try:
                content = file_path.read_bytes()
                content_hash = hashlib.sha256(content).hexdigest()[:16]
            except Exception:
                pass

            lang = IngestionService._detect_language(file_path)

            file_record = RepositoryFile(
                repository_id=repo.id,
                path=rel_path,
                language=lang,
                size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                content_hash=content_hash,
            )
            db.add(file_record)

    @staticmethod
    def _detect_language(file_path: Path) -> str | None:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".R": "r",
            ".lua": "lua",
            ".pl": "perl",
            ".sh": "bash",
            ".bash": "bash",
            ".sql": "sql",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".md": "markdown",
            ".rst": "rst",
        }
        ext = file_path.suffix.lower()
        return ext_map.get(ext)

    @staticmethod
    async def _save_chunks(
        db: AsyncSession,
        repo: Repository,
        chunks: list[dict],
    ):
        """Save chunk records to database."""
        # Get file ID mapping
        result = await db.execute(
            select(RepositoryFile).where(RepositoryFile.repository_id == repo.id)
        )
        file_records = {f.path: f for f in result.scalars().all()}

        for i, chunk_data in enumerate(chunks):
            file_path = chunk_data.get("file_path", "")
            file_record = file_records.get(file_path)

            chunk = Chunk(
                repository_id=repo.id,
                file_id=file_record.id if file_record else None,
                chunk_index=i,
                content=chunk_data.get("content", ""),
                content_hash=chunk_data.get("content_hash"),
                file_path=file_path,
                language=chunk_data.get("language"),
                symbol_name=chunk_data.get("symbol_name"),
                symbol_type=chunk_data.get("symbol_type"),
                parent_symbol=chunk_data.get("parent_symbol"),
                start_line=chunk_data.get("start_line"),
                end_line=chunk_data.get("end_line"),
                imports=chunk_data.get("imports", []),
                definitions=chunk_data.get("definitions", []),
            )
            db.add(chunk)

            # Update file record
            if file_record:
                file_record.chunk_count = (file_record.chunk_count or 0) + 1
                if chunk_data.get("symbol_name"):
                    file_record.symbol_count = (file_record.symbol_count or 0) + 1
                file_record.is_parsed = True

    @staticmethod
    async def _save_graph(
        db: AsyncSession,
        repo: Repository,
        graph_data: dict,
    ):
        """Save graph nodes and edges to database."""
        # Clear existing graph data
        from sqlalchemy import delete
        await db.execute(
            delete(GraphEdge).where(GraphEdge.repository_id == repo.id)
        )
        await db.execute(
            delete(GraphNode).where(GraphNode.repository_id == repo.id)
        )

        node_id_map = {}
        for node_data in graph_data.get("nodes", []):
            node = GraphNode(
                repository_id=repo.id,
                node_type=node_data.get("type", "unknown"),
                name=node_data.get("name", ""),
                qualified_name=node_data.get("qualified_name"),
                file_path=node_data.get("file_path"),
                start_line=node_data.get("start_line"),
                end_line=node_data.get("end_line"),
                metadata_=node_data.get("metadata", {}),
            )
            db.add(node)
            await db.flush()
            node_id_map[node_data.get("id", "")] = node.id

        for edge_data in graph_data.get("edges", []):
            source_id = node_id_map.get(edge_data.get("source"))
            target_id = node_id_map.get(edge_data.get("target"))
            if source_id and target_id:
                edge = GraphEdge(
                    repository_id=repo.id,
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=edge_data.get("type", "UNKNOWN"),
                    metadata_=edge_data.get("metadata", {}),
                )
                db.add(edge)
