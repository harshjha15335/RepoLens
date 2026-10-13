"""Hybrid retrieval service with RRF, graph expansion, MMR, and reranking."""

import re
import time

import numpy as np
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import IndexError_
from app.core.logging import get_logger
from app.models.models import Chunk, GraphEdge, GraphNode
from app.services.artifact_store import ensure_index
from app.services.embeddings.service import EmbeddingService
from app.services.indexing.service import IndexingService
from app.services.reranking.service import RerankingService

logger = get_logger(__name__)


class QueryAnalyzer:
    """Lightweight query analysis for intent detection and routing."""

    INTENT_PATTERNS = {
        "REPOSITORY_OVERVIEW": [
            r"what does this (?:repo|repository|project|codebase) do",
            r"overview",
            r"describe (?:this|the) (?:repo|repository|project)",
            r"what is this",
        ],
        "SYMBOL_LOOKUP": [
            r"where is (\w+) (?:defined|declared|implemented|used)",
            r"find (\w+)",
            r"locate (\w+)",
            r"show me (\w+)",
        ],
        "ARCHITECTURE": [
            r"architecture",
            r"structure",
            r"how is .* organized",
            r"design pattern",
            r"component",
        ],
        "CALL_FLOW": [
            r"what calls",
            r"who calls",
            r"call(?:s|ed by|ers)",
            r"what happens (?:when|after|before)",
            r"flow",
            r"lifecycle",
            r"request.*lifecycle",
        ],
        "DEPENDENCY": [
            r"depend(?:s|encies|ency)",
            r"import(?:s|ed)",
            r"require(?:s|d)",
            r"what (?:does|files) .* (?:use|need|require)",
        ],
        "DEBUGGING": [
            r"debug",
            r"error",
            r"exception",
            r"bug",
            r"fix",
            r"issue",
            r"wrong",
            r"fail",
            r"crash",
        ],
        "IMPLEMENTATION_EXPLANATION": [
            r"explain",
            r"how does .* work",
            r"what does .* do",
            r"walk.* through",
            r"line by line",
        ],
        "DOCUMENTATION": [
            r"document",
            r"readme",
            r"usage",
            r"example",
            r"how to use",
        ],
    }

    @classmethod
    def analyze(cls, query: str) -> dict:
        """Analyze query to determine intent and extract key terms."""
        query_lower = query.lower().strip()

        # Detect intent
        intent = "GENERAL_CODE_QUESTION"
        for intent_type, patterns in cls.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    intent = intent_type
                    break
            if intent != "GENERAL_CODE_QUESTION":
                break

        # Extract potential symbol names (CamelCase or specific identifiers)
        symbols = re.findall(r'\b[A-Z][a-zA-Z0-9]*(?:[A-Z][a-z]+)+\b', query)
        symbols += re.findall(r'\b[a-z_][a-zA-Z0-9_]*\b', query)

        # Filter common English words
        common_words = {
            "how", "does", "what", "where", "when", "why", "this", "that",
            "the", "is", "are", "was", "were", "been", "being", "have",
            "has", "had", "do", "did", "will", "would", "could", "should",
            "can", "may", "might", "shall", "about", "explain", "tell",
            "show", "find", "work", "works", "use", "used", "using",
            "implemented", "defined", "called", "calls", "happens",
            "after", "before", "with", "from", "into",
        }
        symbols = [s for s in symbols if s.lower() not in common_words and len(s) > 2]

        return {
            "intent": intent,
            "symbols": symbols[:5],
            "emphasize_lexical": intent in ("SYMBOL_LOOKUP", "DEPENDENCY"),
            "emphasize_semantic": intent in (
                "REPOSITORY_OVERVIEW", "ARCHITECTURE",
                "IMPLEMENTATION_EXPLANATION",
            ),
            "use_graph": intent in (
                "CALL_FLOW", "DEPENDENCY", "ARCHITECTURE",
                "DEBUGGING",
            ),
        }


class RetrievalService:
    """Hybrid retrieval pipeline with RRF, graph expansion, MMR."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.indexing_service = IndexingService()
        self.settings = get_settings()

    async def search(
        self,
        repository_id: str,
        query: str,
        top_k: int | None = None,
        strategy: str = "hybrid",
        enable_graph_expansion: bool = True,
        enable_mmr: bool | None = None,
        enable_reranking: bool | None = None,
    ) -> dict:
        """Execute the full retrieval pipeline.

        Pipeline:
        1. Query analysis
        2. Dense retrieval (FAISS)
        3. BM25 retrieval
        4. RRF fusion (for hybrid)
        5. Graph expansion (small-to-big)
        6. MMR diversification
        7. Optional reranking
        """
        start_time = time.time()
        if strategy == "graph_expansion":
            enable_graph_expansion = True
            strategy = "hybrid"
        settings = self.settings

        if top_k is None:
            top_k = settings.final_top_k
        if enable_mmr is None:
            enable_mmr = settings.mmr_enabled
        if enable_reranking is None:
            enable_reranking = settings.rerank_enabled

        # Step 1: Analyze query
        query_info = QueryAnalyzer.analyze(query)
        logger.info(f"Query intent: {query_info['intent']}, symbols: {query_info['symbols']}")

        # Load chunks from database
        factory = get_session_factory()
        async with factory() as db:
            await ensure_index(db, repository_id)
            result = await db.execute(
                select(Chunk)
                .where(Chunk.repository_id == repository_id)
                .order_by(Chunk.chunk_index)
            )
            db_chunks = result.scalars().all()

        if not db_chunks:
            return {
                "intent": query_info["intent"],
                "chunks": [],
                "latency_ms": 0,
            }

        chunk_list = [
            {
                "chunk_id": c.id,
                "file_path": c.file_path,
                "symbol_name": c.symbol_name,
                "symbol_type": c.symbol_type,
                "content": c.content,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "parent_symbol": c.parent_symbol,
                "language": c.language,
                "imports": c.imports or [],
                "definitions": c.definitions or [],
            }
            for c in db_chunks
        ]

        # Step 2-4: Retrieve based on strategy
        if strategy == "dense":
            ranked = await self._dense_search(repository_id, query, settings.dense_top_k)
        elif strategy == "bm25":
            ranked = self._bm25_search(repository_id, query, settings.bm25_top_k)
        else:
            # Hybrid: Dense + BM25 + RRF
            dense_results = await self._dense_search(
                repository_id, query, settings.dense_top_k
            )
            bm25_results = self._bm25_search(
                repository_id, query, settings.bm25_top_k
            )

            # Adjust weights based on query analysis
            rrf_k = settings.rrf_k
            ranked = self._rrf_fusion(
                dense_results, bm25_results,
                k=rrf_k,
                dense_weight=0.4 if query_info["emphasize_lexical"] else 0.6,
            )

        # Map indices to chunks
        retrieved_chunks = []
        for idx, score in ranked[:top_k * 2]:  # Get extra for expansion/MMR
            if idx < len(chunk_list):
                chunk = chunk_list[idx].copy()
                chunk["score"] = score
                chunk["source"] = strategy
                retrieved_chunks.append(chunk)

        # Step 5: Graph expansion (small-to-big retrieval)
        if enable_graph_expansion:
            retrieved_chunks = await self._expand_with_graph(
                repository_id, retrieved_chunks, chunk_list, top_k
            )

        # Step 6: MMR diversification
        if enable_mmr and len(retrieved_chunks) > top_k:
            retrieved_chunks = await self._apply_mmr(
                query, retrieved_chunks, top_k,
                lambda_param=settings.mmr_lambda,
            )

        # Step 7: Optional reranking
        if enable_reranking:
            try:
                reranker = RerankingService()
                retrieved_chunks = await reranker.rerank(query, retrieved_chunks, top_k)
            except Exception as e:
                logger.warning(f"Reranking failed, using original order: {e}")

        # Limit to top_k and add ranks
        final_chunks = retrieved_chunks[:top_k]
        for i, chunk in enumerate(final_chunks):
            chunk["rank"] = i + 1

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "intent": query_info["intent"],
            "chunks": final_chunks,
            "latency_ms": round(elapsed_ms, 2),
        }

    async def _dense_search(
        self, repository_id: str, query: str, top_k: int
    ) -> list[tuple[int, float]]:
        """Search using FAISS dense index."""
        try:
            faiss_index = self.indexing_service.load_faiss_index(repository_id)
            if faiss_index is None:
                return []

            indexed_metadata = self.indexing_service.load_embedding_metadata(repository_id)
            query_embedding = await self.embedding_service.embed_query(query)
            # Query encoding can activate a fallback, so compare its resolved provider.
            query_metadata = self.embedding_service.metadata
            if (query_metadata != indexed_metadata
                    or len(query_embedding) != indexed_metadata["dimension"]
                    or faiss_index.d != indexed_metadata["dimension"]):
                raise IndexError_(
                    "Dense index embedding provider or model has changed. "
                    "Reindex this repository with the current embedding provider."
                )
            query_vector = np.array([query_embedding], dtype=np.float32)

            scores, indices = faiss_index.search(query_vector, min(top_k, faiss_index.ntotal))

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0:
                    results.append((int(idx), float(score)))

            return results

        except IndexError_:
            raise
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    def _bm25_search(
        self, repository_id: str, query: str, top_k: int
    ) -> list[tuple[int, float]]:
        """Search using BM25 lexical index."""
        try:
            bm25_index = self.indexing_service.load_bm25_index(repository_id)
            if bm25_index is None:
                return []

            return bm25_index.search(query, top_k)

        except IndexError_:
            raise
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def _rrf_fusion(
        self,
        dense_results: list[tuple[int, float]],
        bm25_results: list[tuple[int, float]],
        k: int = 60,
        dense_weight: float = 0.6,
    ) -> list[tuple[int, float]]:
        """Reciprocal Rank Fusion combining dense and BM25 results.

        RRF(d) = Σ weight_i / (k + rank_i(d))
        """
        scores: dict[int, float] = {}

        bm25_weight = 1.0 - dense_weight

        for rank, (idx, _) in enumerate(dense_results):
            scores[idx] = scores.get(idx, 0) + dense_weight / (k + rank + 1)

        for rank, (idx, _) in enumerate(bm25_results):
            scores[idx] = scores.get(idx, 0) + bm25_weight / (k + rank + 1)

        # Sort by fused score
        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return fused

    async def _expand_with_graph(
        self,
        repository_id: str,
        retrieved_chunks: list[dict],
        all_chunks: list[dict],
        top_k: int,
    ) -> list[dict]:
        """Expand retrieved results using code graph relationships.

        Implements small-to-big retrieval:
        - If a method is retrieved, also consider its parent class
        - If a function is retrieved, also consider its callers/callees
        - Add relevant imports and containing file context
        """
        if not retrieved_chunks:
            return retrieved_chunks

        factory = get_session_factory()
        async with factory() as db:
            # Get graph nodes for retrieved symbols
            retrieved_symbols = set()
            retrieved_files = set()
            for chunk in retrieved_chunks:
                if chunk.get("symbol_name"):
                    retrieved_symbols.add(chunk["symbol_name"])
                if chunk.get("file_path"):
                    retrieved_files.add(chunk["file_path"])

            # Find related nodes via graph edges
            expanded_symbols = set()

            # Query graph for related symbols
            nodes_result = await db.execute(
                select(GraphNode).where(
                    GraphNode.repository_id == repository_id,
                    GraphNode.name.in_(list(retrieved_symbols)) if retrieved_symbols else GraphNode.name == ""
                )
            )
            nodes = nodes_result.scalars().all()

            node_ids = [n.id for n in nodes]

            if node_ids:
                # Get connected edges
                edges_result = await db.execute(
                    select(GraphEdge).where(
                        GraphEdge.repository_id == repository_id,
                        (GraphEdge.source_id.in_(node_ids)) | (GraphEdge.target_id.in_(node_ids))
                    )
                )
                edges = edges_result.scalars().all()

                # Find connected node IDs
                connected_ids = set()
                for edge in edges:
                    if edge.relationship_type in ("CONTAINS", "CALLS", "INHERITS", "IMPORTS"):
                        connected_ids.add(edge.source_id)
                        connected_ids.add(edge.target_id)

                connected_ids -= set(node_ids)

                if connected_ids:
                    connected_result = await db.execute(
                        select(GraphNode).where(
                            GraphNode.id.in_(list(connected_ids))
                        )
                    )
                    connected_nodes = connected_result.scalars().all()
                    for node in connected_nodes:
                        expanded_symbols.add(node.name)

        # Add expansion chunks (without duplicating existing results)
        existing_ids = {c["chunk_id"] for c in retrieved_chunks}

        expansion_chunks = []
        for chunk in all_chunks:
            if chunk["chunk_id"] in existing_ids:
                continue

            # Include if symbol matches expanded set
            if chunk.get("symbol_name") in expanded_symbols:
                chunk_copy = chunk.copy()
                chunk_copy["score"] = 0.3  # Lower score for expanded
                chunk_copy["source"] = "graph_expansion"
                expansion_chunks.append(chunk_copy)
                existing_ids.add(chunk["chunk_id"])

            # Include parent class/file for retrieved methods
            elif chunk.get("symbol_type") == "class":
                for rc in retrieved_chunks:
                    if (rc.get("parent_symbol") == chunk.get("symbol_name")
                            and rc.get("file_path") == chunk.get("file_path")):
                        chunk_copy = chunk.copy()
                        chunk_copy["score"] = 0.35
                        chunk_copy["source"] = "parent_expansion"
                        expansion_chunks.append(chunk_copy)
                        existing_ids.add(chunk["chunk_id"])
                        break

        # Give a bounded number of connected symbols a slot in the returned
        # top_k. Appending every expansion after 2 * top_k ranked hits made
        # graph expansion invisible whenever the base retrieval was full.
        pivot = max(1, top_k // 2)
        expansion_budget = max(1, top_k // 3)
        result = (
            retrieved_chunks[:pivot]
            + expansion_chunks[:expansion_budget]
            + retrieved_chunks[pivot:]
            + expansion_chunks[expansion_budget:]
        )
        return result

    async def _apply_mmr(
        self,
        query: str,
        chunks: list[dict],
        top_k: int,
        lambda_param: float = 0.7,
    ) -> list[dict]:
        """Apply Maximal Marginal Relevance for diversification.

        MMR = λ * sim(q, d) - (1-λ) * max(sim(d, d_selected))

        Uses a simplified text overlap metric when embeddings aren't readily available.
        """
        if len(chunks) <= top_k:
            return chunks

        selected = [chunks[0]]
        remaining = list(chunks[1:])

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_score = float("-inf")

            for i, candidate in enumerate(remaining):
                # Relevance score (original retrieval score)
                relevance = candidate.get("score", 0)

                # Diversity: max similarity with already selected
                max_sim = 0
                for sel in selected:
                    sim = self._text_similarity(candidate, sel)
                    max_sim = max(max_sim, sim)

                # MMR score
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _text_similarity(self, chunk_a: dict, chunk_b: dict) -> float:
        """Simple text overlap similarity between chunks."""
        # File-level overlap
        if chunk_a.get("file_path") == chunk_b.get("file_path"):
            # Same file — check line overlap
            a_start = chunk_a.get("start_line", 0)
            a_end = chunk_a.get("end_line", 0)
            b_start = chunk_b.get("start_line", 0)
            b_end = chunk_b.get("end_line", 0)

            if a_start and a_end and b_start and b_end:
                overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
                total = max(a_end - a_start, b_end - b_start, 1)
                return overlap / total

            return 0.5  # Same file but can't determine overlap

        return 0.0
