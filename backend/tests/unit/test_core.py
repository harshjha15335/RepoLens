"""Unit tests for core services: parsing, chunking, indexing, retrieval."""

import os
import tempfile
import zipfile
from pathlib import Path

import pytest

# ─── Path Validation Tests ──────────────────────────────────────

class TestPathValidation:
    """Tests for path traversal and security validation."""

    def test_path_traversal_detection(self):
        """Zip Slip: ../../../etc/passwd should be rejected."""
        from app.core.config import get_settings
        from app.core.errors import ArchiveSecurityError
        from app.services.ingestion.service import IngestionService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a malicious ZIP with path traversal
            zip_path = os.path.join(tmpdir, "malicious.zip")
            target_dir = Path(os.path.join(tmpdir, "target"))
            target_dir.mkdir()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../../../etc/passwd", "root:x:0:0")

            settings = get_settings()
            with pytest.raises(ArchiveSecurityError):
                IngestionService._extract_zip(zip_path, target_dir, settings)

    def test_absolute_path_detection(self):
        """Absolute paths in ZIP should be rejected."""
        from app.core.config import get_settings
        from app.core.errors import ArchiveSecurityError
        from app.services.ingestion.service import IngestionService

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "malicious.zip")
            target_dir = Path(os.path.join(tmpdir, "target"))
            target_dir.mkdir()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("/etc/passwd", "root:x:0:0")

            settings = get_settings()
            with pytest.raises(ArchiveSecurityError):
                IngestionService._extract_zip(zip_path, target_dir, settings)

    def test_safe_zip_extraction(self):
        """A valid ZIP should extract safely."""
        from app.core.config import get_settings
        from app.services.ingestion.service import IngestionService

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "safe.zip")
            target_dir = Path(os.path.join(tmpdir, "target"))
            target_dir.mkdir()

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("project/main.py", "print('hello')")
                zf.writestr("project/README.md", "# Test")

            settings = get_settings()
            IngestionService._extract_zip(zip_path, target_dir, settings)

            assert (target_dir / "main.py").exists()
            assert (target_dir / "README.md").exists()


# ─── Language Detection Tests ────────────────────────────────────

class TestLanguageDetection:
    """Tests for programming language detection."""

    def test_python_detection(self):
        from app.services.ingestion.service import IngestionService
        assert IngestionService._detect_language(Path("test.py")) == "python"

    def test_javascript_detection(self):
        from app.services.ingestion.service import IngestionService
        assert IngestionService._detect_language(Path("test.js")) == "javascript"

    def test_typescript_detection(self):
        from app.services.ingestion.service import IngestionService
        assert IngestionService._detect_language(Path("test.ts")) == "typescript"

    def test_java_detection(self):
        from app.services.ingestion.service import IngestionService
        assert IngestionService._detect_language(Path("Main.java")) == "java"

    def test_unknown_extension(self):
        from app.services.ingestion.service import IngestionService
        assert IngestionService._detect_language(Path("test.xyz")) is None


# ─── File Filtering Tests ────────────────────────────────────────

class TestFileFiltering:
    """Tests for file discovery and filtering."""

    def test_excludes_node_modules(self):
        from app.services.ingestion.service import EXCLUDED_DIRS
        assert "node_modules" in EXCLUDED_DIRS

    def test_excludes_git_dir(self):
        from app.services.ingestion.service import EXCLUDED_DIRS
        assert ".git" in EXCLUDED_DIRS

    def test_excludes_binary_extensions(self):
        from app.services.ingestion.service import BINARY_EXTENSIONS
        assert ".exe" in BINARY_EXTENSIONS
        assert ".png" in BINARY_EXTENSIONS
        assert ".zip" in BINARY_EXTENSIONS

    def test_includes_source_extensions(self):
        from app.services.ingestion.service import SUPPORTED_EXTENSIONS
        assert ".py" in SUPPORTED_EXTENSIONS
        assert ".js" in SUPPORTED_EXTENSIONS
        assert ".ts" in SUPPORTED_EXTENSIONS
        assert ".java" in SUPPORTED_EXTENSIONS

    def test_discover_files(self):
        from app.core.config import get_settings
        from app.services.ingestion.service import IngestionService

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)

            # Create test files
            (source_dir / "main.py").write_text("print('hello')")
            (source_dir / "README.md").write_text("# Test")
            (source_dir / "image.png").write_bytes(b"\x89PNG")

            # Create excluded dir
            node_modules = source_dir / "node_modules"
            node_modules.mkdir()
            (node_modules / "package.js").write_text("module.exports = {}")

            settings = get_settings()
            files = IngestionService._discover_files(source_dir, settings)

            paths = [str(f.relative_to(source_dir)) for f in files]
            assert "main.py" in paths
            assert "README.md" in paths
            assert "image.png" not in paths
            assert any("node_modules" in p for p in paths) is False


# ─── Parser Tests ────────────────────────────────────────────────

class TestParserService:
    """Tests for the code parsing service."""

    def test_parse_python_file(self):
        from app.services.parsing.service import ParserService

        parser = ParserService()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            test_file = source_dir / "test.py"
            test_file.write_text("""
import os
from pathlib import Path

class MyClass:
    def my_method(self):
        pass

def my_function():
    return 42
""")
            result = parser.parse_file(test_file, source_dir)

            assert result is not None
            assert result["language"] == "python"
            assert len(result["symbols"]) >= 2  # class and function at minimum
            assert len(result["imports"]) >= 1

            # Check symbol names
            symbol_names = [s["name"] for s in result["symbols"]]
            assert "MyClass" in symbol_names
            assert "my_function" in symbol_names

    def test_parse_javascript_file(self):
        from app.services.parsing.service import ParserService

        parser = ParserService()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            test_file = source_dir / "test.js"
            test_file.write_text("""
function greet(name) {
    return 'Hello ' + name;
}

class UserService {
    constructor() {
        this.users = [];
    }
}
""")
            result = parser.parse_file(test_file, source_dir)

            assert result is not None
            assert result["language"] == "javascript"
            assert len(result["symbols"]) >= 2

    def test_parse_empty_file(self):
        from app.services.parsing.service import ParserService

        parser = ParserService()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir)
            test_file = source_dir / "empty.py"
            test_file.write_text("")

            result = parser.parse_file(test_file, source_dir)
            assert result is None


# ─── Chunking Tests ──────────────────────────────────────────────

class TestChunkingService:
    """Tests for the code chunking service."""

    def test_chunk_parsed_file_with_symbols(self):
        from app.services.chunking.service import ChunkingService

        chunker = ChunkingService()
        parsed = {
            "file_path": "test.py",
            "language": "python",
            "content": """import os

class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def main():
    calc = Calculator()
    print(calc.add(1, 2))
""",
            "symbols": [
                {"name": "Calculator", "type": "class", "start_line": 3, "end_line": 8, "parent": None,
                 "content": "class Calculator:\n    def add(self, a, b):\n        return a + b\n\n    def subtract(self, a, b):\n        return a - b"},
                {"name": "add", "type": "method", "start_line": 4, "end_line": 5, "parent": "Calculator",
                 "content": "    def add(self, a, b):\n        return a + b"},
                {"name": "subtract", "type": "method", "start_line": 7, "end_line": 8, "parent": "Calculator",
                 "content": "    def subtract(self, a, b):\n        return a - b"},
                {"name": "main", "type": "function", "start_line": 10, "end_line": 12, "parent": None,
                 "content": "def main():\n    calc = Calculator()\n    print(calc.add(1, 2))"},
            ],
            "imports": ["import os"],
            "content_hash": "abc123",
        }

        chunks = chunker.chunk_parsed_file(parsed)

        assert len(chunks) >= 3  # file overview + symbols
        # Check file overview exists
        file_chunks = [c for c in chunks if c["symbol_type"] == "file"]
        assert len(file_chunks) >= 1

        # Check symbol chunks exist
        symbol_names = [c["symbol_name"] for c in chunks if c.get("symbol_name")]
        assert "Calculator" in symbol_names or any("Calculator" in str(s) for s in symbol_names)

    def test_chunk_has_metadata(self):
        from app.services.chunking.service import ChunkingService

        chunker = ChunkingService()
        parsed = {
            "file_path": "test.py",
            "language": "python",
            "content": "def hello():\n    return 'world'\n",
            "symbols": [
                {"name": "hello", "type": "function", "start_line": 1, "end_line": 2,
                 "parent": None, "content": "def hello():\n    return 'world'"},
            ],
            "imports": [],
            "content_hash": "def123",
        }

        chunks = chunker.chunk_parsed_file(parsed)

        for chunk in chunks:
            assert "file_path" in chunk
            assert "content" in chunk
            assert "content_hash" in chunk
            assert "language" in chunk


# ─── BM25 Tokenization Tests ────────────────────────────────────

class TestBM25Tokenization:
    """Tests for code-aware BM25 tokenization."""

    def test_camel_case_splitting(self):
        from app.services.indexing.service import BM25Index

        bm25 = BM25Index()
        tokens = bm25._split_tokens("getUserProfile")

        assert "getuserprofile" in tokens
        assert "get" in tokens
        assert "user" in tokens
        assert "profile" in tokens

    def test_snake_case_splitting(self):
        from app.services.indexing.service import BM25Index

        bm25 = BM25Index()
        tokens = bm25._split_tokens("get_user_profile")

        assert "get_user_profile" in tokens
        assert "get" in tokens
        assert "user" in tokens
        assert "profile" in tokens

    def test_class_name_splitting(self):
        from app.services.indexing.service import BM25Index

        bm25 = BM25Index()
        tokens = bm25._split_tokens("UserProfileService")

        assert "userprofileservice" in tokens
        assert "user" in tokens
        assert "profile" in tokens
        assert "service" in tokens


# ─── RRF Tests ───────────────────────────────────────────────────

class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion."""

    def test_rrf_basic(self):
        from app.services.retrieval.service import RetrievalService

        service = RetrievalService()

        dense = [(0, 0.9), (1, 0.8), (2, 0.7)]
        bm25 = [(1, 5.0), (0, 3.0), (3, 2.0)]

        fused = service._rrf_fusion(dense, bm25, k=60)

        # Document 0 and 1 should be in top results (both in dense and bm25)
        top_ids = [idx for idx, _ in fused[:3]]
        assert 0 in top_ids
        assert 1 in top_ids

    def test_rrf_single_source(self):
        from app.services.retrieval.service import RetrievalService

        service = RetrievalService()

        dense = [(0, 0.9), (1, 0.8)]
        bm25 = []

        fused = service._rrf_fusion(dense, bm25, k=60)

        assert len(fused) == 2
        assert fused[0][0] == 0  # First from dense should still be first


# ─── MMR Tests ───────────────────────────────────────────────────

class TestMMR:
    """Tests for Maximal Marginal Relevance."""

    @pytest.mark.asyncio
    async def test_mmr_reduces_redundancy(self):
        from app.services.retrieval.service import RetrievalService

        service = RetrievalService()

        chunks = [
            {"file_path": "a.py", "start_line": 1, "end_line": 10, "score": 0.9},
            {"file_path": "a.py", "start_line": 5, "end_line": 15, "score": 0.85},  # Overlaps with first
            {"file_path": "b.py", "start_line": 1, "end_line": 10, "score": 0.8},
            {"file_path": "c.py", "start_line": 1, "end_line": 10, "score": 0.75},
        ]

        result = await service._apply_mmr("test query", chunks, top_k=3, lambda_param=0.7)

        # Should prefer diverse results
        files = [c["file_path"] for c in result]
        assert len(set(files)) >= 2  # Should have at least 2 different files


# ─── Query Analysis Tests ────────────────────────────────────────

class TestQueryAnalysis:
    """Tests for query intent detection."""

    def test_symbol_lookup_intent(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("Where is UserService defined?")
        assert result["intent"] == "SYMBOL_LOOKUP"

    def test_architecture_intent(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("Explain the architecture of this project")
        assert result["intent"] == "ARCHITECTURE"

    def test_call_flow_intent(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("What calls validateToken?")
        assert result["intent"] == "CALL_FLOW"

    def test_debug_intent(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("Help me debug this error")
        assert result["intent"] == "DEBUGGING"

    def test_overview_intent(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("What does this repository do?")
        assert result["intent"] == "REPOSITORY_OVERVIEW"

    def test_symbol_extraction(self):
        from app.services.retrieval.service import QueryAnalyzer

        result = QueryAnalyzer.analyze("Where is UserProfileService defined?")
        assert "UserProfileService" in result["symbols"]


# ─── Graph Tests ─────────────────────────────────────────────────

class TestGraphService:
    """Tests for the code graph service."""

    def test_build_graph_with_symbols(self):
        from app.services.graph.service import GraphService

        graph = GraphService()
        parsed_files = [
            {
                "file_path": "main.py",
                "language": "python",
                "content": "class Foo:\n    def bar(self): pass\ndef baz(): pass",
                "symbols": [
                    {"name": "Foo", "type": "class", "start_line": 1, "end_line": 2, "parent": None},
                    {"name": "bar", "type": "method", "start_line": 2, "end_line": 2, "parent": "Foo"},
                    {"name": "baz", "type": "function", "start_line": 3, "end_line": 3, "parent": None},
                ],
                "imports": [],
            }
        ]

        result = graph.build_graph(parsed_files, "test-repo")

        assert len(result["nodes"]) >= 3  # file + class + function + method
        assert len(result["edges"]) >= 2  # CONTAINS edges

        # Check relationship types
        edge_types = {e["type"] for e in result["edges"]}
        assert "CONTAINS" in edge_types

    def test_inheritance_detection(self):
        from app.services.graph.service import GraphService

        graph = GraphService()
        parsed_files = [
            {
                "file_path": "models.py",
                "language": "python",
                "content": "class Base:\n    pass\nclass Child(Base):\n    pass",
                "symbols": [
                    {"name": "Base", "type": "class", "start_line": 1, "end_line": 2,
                     "parent": None, "content": "class Base:\n    pass"},
                    {"name": "Child", "type": "class", "start_line": 3, "end_line": 4,
                     "parent": None, "content": "class Child(Base):\n    pass"},
                ],
                "imports": [],
            }
        ]

        result = graph.build_graph(parsed_files, "test-repo")

        inherits_edges = [e for e in result["edges"] if e["type"] == "INHERITS"]
        assert len(inherits_edges) >= 1


# ─── Citation Validation Tests ───────────────────────────────────

class TestCitationExtraction:
    """Tests for citation extraction and validation."""

    def test_extract_file_line_citations(self):
        from app.services.generation.service import GenerationService

        service = GenerationService.__new__(GenerationService)

        answer = "The function is defined in [main.py:10-20] and used in [utils.py:5-15]."
        chunks = [
            {"chunk_id": "c1", "file_path": "main.py", "symbol_name": "func", "start_line": 10, "end_line": 20, "content": "test"},
            {"chunk_id": "c2", "file_path": "utils.py", "symbol_name": "helper", "start_line": 5, "end_line": 15, "content": "test"},
        ]

        citations = service._extract_citations(answer, chunks)

        assert len(citations) >= 2
        file_paths = [c["file_path"] for c in citations]
        assert "main.py" in file_paths
        assert "utils.py" in file_paths

    def test_no_hallucinated_citations(self):
        from app.services.generation.service import GenerationService

        service = GenerationService.__new__(GenerationService)

        answer = "The code uses [nonexistent.py:1-10]."
        chunks = [
            {"chunk_id": "c1", "file_path": "main.py", "symbol_name": "func", "start_line": 10, "end_line": 20, "content": "test"},
        ]

        citations = service._extract_citations(answer, chunks)

        # Should not include hallucinated file, but should include fallback chunks
        for c in citations:
            assert c["file_path"] != "nonexistent.py"


# ─── Configuration Tests ────────────────────────────────────────

class TestConfiguration:
    """Tests for configuration loading."""

    @pytest.fixture
    def default_settings(self, monkeypatch):
        from app.core.config import Settings

        for field in Settings.model_fields.values():
            if field.alias:
                monkeypatch.delenv(field.alias, raising=False)
        return Settings(_env_file=None)

    def test_default_settings(self, default_settings):
        settings = default_settings
        assert settings.app_env == "development"
        assert settings.max_upload_mb == 500
        assert settings.dense_top_k == 20
        assert settings.bm25_top_k == 20
        assert settings.rrf_k == 60

    def test_max_upload_bytes(self, default_settings):
        settings = default_settings
        assert settings.max_upload_bytes == 500 * 1024 * 1024

    def test_embedding_config(self, default_settings):
        settings = default_settings
        assert settings.embedding_provider == "sentence-transformers"
        assert settings.embedding_model == "all-MiniLM-L6-v2"
