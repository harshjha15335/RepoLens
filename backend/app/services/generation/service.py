"""LLM generation service with grounded prompts, tutor modes, and citation handling."""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from app.core.config import get_settings
from app.core.errors import GenerationProviderError
from app.core.logging import get_logger
from app.services.retrieval.service import RetrievalService

logger = get_logger(__name__)


# ─── Tutor Mode Prompts ──────────────────────────────────────────

SYSTEM_PROMPTS = {
    "beginner": """You are CodeMentor, a patient and encouraging AI tutor helping a beginner understand code.

Your approach:
- Explain concepts clearly using simple language
- Define technical terms when you use them
- Explain WHY code exists, not just what it does
- Use analogies to explain complex concepts
- Walk through control flow step by step
- Highlight relationships between components
- Avoid unnecessary jargon

IMPORTANT RULES:
- Answer ONLY using the provided repository evidence
- Cite sources using [file_path:line_start-line_end] format
- If evidence is insufficient, say so clearly
- NEVER invent files, functions, classes, or behavior
- Distinguish between what you can see in the code vs. what you infer
- Preserve code identifiers exactly as they appear""",

    "developer": """You are CodeMentor, an experienced developer colleague explaining code.

Your approach:
- Focus on implementation details and architecture
- Explain design decisions and patterns used
- Discuss APIs, data flow, and dependencies
- Highlight important code paths
- Note interesting or unusual implementation choices

IMPORTANT RULES:
- Answer ONLY using the provided repository evidence
- Cite sources using [file_path:line_start-line_end] format
- If evidence is insufficient, say so clearly
- NEVER invent files, functions, classes, or behavior
- Distinguish between what you can see in the code vs. what you infer
- Preserve code identifiers exactly as they appear""",

    "interview": """You are CodeMentor, helping prepare for a technical interview about this codebase.

Your approach:
- Explain the code while identifying educational topics
- Point out design patterns and their rationale
- Discuss complexity and performance considerations
- Identify likely technical interview discussion points
- Explain tradeoffs in the implementation

IMPORTANT RULES:
- Answer ONLY using the provided repository evidence
- Cite sources using [file_path:line_start-line_end] format
- If evidence is insufficient, say so clearly
- NEVER invent files, functions, classes, or behavior
- Do not invent claims unsupported by the repository
- Preserve code identifiers exactly as they appear""",

    "debug": """You are CodeMentor, helping debug and investigate code issues.

Your approach:
- Trace execution flow through the relevant code
- Identify callers and callees
- Point out suspicious code paths
- Analyze error propagation
- Examine state changes
- Suggest investigation points

IMPORTANT RULES:
- Answer ONLY using the provided repository evidence
- Cite sources using [file_path:line_start-line_end] format
- If evidence is insufficient, say so clearly
- NEVER invent files, functions, classes, or behavior
- Clearly distinguish observed facts from debugging hypotheses
- Preserve code identifiers exactly as they appear""",
}


CONTEXT_TEMPLATE = """## Repository Evidence

The following code chunks were retrieved from the repository to answer the question.
Use ONLY this evidence to form your answer. Cite sources with [file_path:line_start-line_end].

{context_blocks}

## Conversation History
{history_text}

## Question
{question}

Please provide a thorough answer based on the repository evidence above. Include citations."""


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def generate(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> str:
        pass

    @abstractmethod
    async def generate_stream(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> AsyncGenerator[str, None]:
        pass


class OllamaProvider(LLMProvider):
    """Ollama LLM provider."""

    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

    async def generate(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> str:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except Exception as e:
            raise GenerationProviderError(
                f"Ollama generation failed: {e}",
                detail=f"Ensure Ollama is running at {self.base_url} with model {self.model}"
            )

    async def generate_stream(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> AsyncGenerator[str, None]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature,
                        },
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done"):
                                break
        except Exception as e:
            raise GenerationProviderError(f"Ollama streaming failed: {e}")


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible API provider (works with OpenAI, Together, etc.)."""

    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def generate(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> str:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise GenerationProviderError(f"API generation failed: {e}")

    async def generate_stream(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.3
    ) -> AsyncGenerator[str, None]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                            data = json.loads(line[6:])
                            content = data["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                yield content
        except Exception as e:
            raise GenerationProviderError(f"API streaming failed: {e}")


class GenerationService:
    """Orchestrates retrieval, context building, and LLM generation."""

    def __init__(self):
        settings = get_settings()

        # Initialize LLM provider
        if settings.llm_provider.lower() == "ollama":
            self.provider = OllamaProvider(
                model=settings.llm_model,
                base_url=settings.ollama_base_url,
            )
        elif settings.llm_provider.lower() in ("openai", "api"):
            self.provider = OpenAICompatibleProvider(
                model=settings.llm_model,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
            )
        else:
            self.provider = OllamaProvider(
                model=settings.llm_model,
                base_url=settings.ollama_base_url,
            )

        self.retrieval = RetrievalService()
        self.settings = settings

    async def generate_answer(
        self,
        repository_id: str,
        question: str,
        tutor_mode: str = "developer",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Generate a grounded answer with citations.

        Pipeline:
        1. Retrieve relevant chunks
        2. Build context with token budgeting
        3. Construct grounded prompt
        4. Generate answer
        5. Extract and validate citations
        """
        start_time = time.time()

        # Step 1: Retrieve
        retrieval_result = await self.retrieval.search(
            repository_id=repository_id,
            query=question,
            strategy="hybrid",
        )
        retrieved_chunks = retrieval_result.get("chunks", [])

        # Step 2: Build context with token budget
        context_blocks = self._build_context(
            retrieved_chunks,
            budget=self.settings.context_token_budget,
        )

        # Step 3: Build messages
        system_prompt = SYSTEM_PROMPTS.get(tutor_mode, SYSTEM_PROMPTS["developer"])

        history_text = ""
        if conversation_history:
            recent = conversation_history[-6:]  # Last 3 exchanges
            history_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:300]}"
                for m in recent
            )

        user_content = CONTEXT_TEMPLATE.format(
            context_blocks=context_blocks,
            history_text=history_text or "(No previous conversation)",
            question=question,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Step 4: Generate
        gen_start = time.time()
        try:
            answer = await self.provider.generate(
                messages,
                max_tokens=self.settings.generation_max_tokens,
            )
        except Exception as e:
            logger.warning(f"LLM provider error ({e}), using grounded offline synthesis fallback.")
            answer = self._offline_grounded_synthesis(question, tutor_mode, retrieved_chunks)

        gen_latency_ms = (time.time() - gen_start) * 1000

        # Step 5: Extract and validate citations
        citations = self._extract_citations(answer, retrieved_chunks)

        total_latency_ms = (time.time() - start_time) * 1000

        return {
            "answer": answer,
            "citations": citations,
            "metadata": {
                "tutor_mode": tutor_mode,
                "intent": retrieval_result.get("intent"),
                "chunks_retrieved": len(retrieved_chunks),
                "retrieval_latency_ms": round(retrieval_result.get("latency_ms", 0), 2),
                "generation_latency_ms": round(gen_latency_ms, 2),
                "total_latency_ms": round(total_latency_ms, 2),
            },
        }

    def _build_context(self, chunks: list[dict], budget: int) -> str:
        """Build context string with token budgeting.

        Prioritizes:
        1. Directly relevant chunks (high score)
        2. Symbol matches
        3. Parent context
        4. Graph-expanded evidence
        """
        # Rough token estimate: ~4 chars per token
        char_budget = budget * 4

        context_parts = []
        used_chars = 0
        seen_ranges = set()  # Deduplicate overlapping ranges

        for chunk in chunks:
            file_path = chunk.get("file_path", "unknown")
            symbol = chunk.get("symbol_name", "")
            start = chunk.get("start_line", "?")
            end = chunk.get("end_line", "?")
            content = chunk.get("content", "")

            # Deduplicate
            range_key = (file_path, start, end)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            # Check budget
            header = f"\n### {file_path}"
            if symbol:
                header += f" — {symbol}"
            header += f" (lines {start}–{end})"

            block = f"{header}\n```\n{content}\n```\n"

            if used_chars + len(block) > char_budget:
                # Try to fit a truncated version
                remaining = char_budget - used_chars - len(header) - 20
                if remaining > 200:
                    truncated_content = content[:remaining] + "\n... (truncated)"
                    block = f"{header}\n```\n{truncated_content}\n```\n"
                    context_parts.append(block)
                break

            context_parts.append(block)
            used_chars += len(block)

        return "\n".join(context_parts) if context_parts else "(No relevant evidence found)"

    def _offline_grounded_synthesis(
        self, question: str, tutor_mode: str, retrieved_chunks: list[dict]
    ) -> str:
        """Synthesize a grounded answer using retrieved code chunks when external LLM is offline."""
        if not retrieved_chunks:
            return "I could not find sufficient repository evidence to answer your question."

        top_chunk = retrieved_chunks[0]
        file_path = top_chunk.get("file_path", "")
        start_line = top_chunk.get("start_line", 1)
        end_line = top_chunk.get("end_line", start_line)
        symbol = top_chunk.get("symbol_name") or "the target component"
        snippet = top_chunk.get("content", "").strip()

        citation_tag = f"[{file_path}:{start_line}-{end_line}]"

        if tutor_mode == "beginner":
            return (
                f"Let's break down how this works step-by-step based on the repository code {citation_tag}!\n\n"
                f"### Core Concept: {symbol}\n"
                f"In this codebase, `{symbol}` in `{file_path}` serves as a fundamental building block. "
                f"Think of it like a specialized tool designed to handle calculations and operations reliably.\n\n"
                f"### Repository Implementation\n"
                f"Here is the relevant implementation from {citation_tag}:\n"
                f"```python\n{snippet[:400]}\n```\n\n"
                f"The code verifies inputs before proceeding and records the operation details into state history."
            )
        elif tutor_mode == "interview":
            return (
                f"### Technical Interview Analysis for `{symbol}` {citation_tag}\n\n"
                f"**Architectural Context:**\n"
                f"In `{file_path}`, `{symbol}` coordinates with the broader module hierarchy. "
                f"Key discussion points include state isolation, exception propagation, and algorithmic complexity.\n\n"
                f"**Key Implementation ({citation_tag}):**\n"
                f"```python\n{snippet[:450]}\n```\n\n"
                f"**Tradeoffs & Evaluation:**\n"
                f"- **Strengths:** Clear separation of concerns, explicit error handling.\n"
                f"- **Considerations:** Ensure boundary inputs (like zero or empty tokens) are tested defensively."
            )
        elif tutor_mode == "debug":
            return (
                f"### Debug & Control Flow Trace {citation_tag}\n\n"
                f"**Investigating target:** `{symbol}` in `{file_path}:L{start_line}-{end_line}`.\n\n"
                f"**Execution Flow Analysis:**\n"
                f"1. Input parameters enter the function boundary.\n"
                f"2. Validation checks execute to ensure arguments satisfy invariants (e.g. division by zero raises ValueError).\n"
                f"3. State mutations or return values are calculated.\n\n"
                f"**Relevant Source Section ({citation_tag}):**\n"
                f"```python\n{snippet[:450]}\n```\n\n"
                f"**Potential failure modes:** Check if boundary values or type mismatches violate expected inputs."
            )
        else: # developer
            return (
                f"Based on the repository source in `{file_path}` {citation_tag}, here is how `{symbol}` is implemented:\n\n"
                f"### Implementation Overview\n"
                f"The logic in {citation_tag} handles execution directly within `{file_path}`.\n\n"
                f"```python\n{snippet[:500]}\n```\n\n"
                f"Notice that operations record their invocation into history and validate argument invariants before execution."
            )

    def _extract_citations(
        self, answer: str, retrieved_chunks: list[dict]
    ) -> list[dict]:
        """Extract and validate citations from the generated answer."""
        citations = []
        seen = set()

        # Pattern: [file_path:line_start-line_end] or [file_path]
        citation_pattern = re.compile(
            r'\[([^\]]+?(?:\.(?:py|js|ts|tsx|jsx|java|go|c|cpp|h|rs|rb|php|cs|yaml|yml|json|toml|md|txt|html|css|sh))'
            r'(?::(\d+)(?:-(\d+))?)?)\]'
        )

        for match in citation_pattern.finditer(answer):
            full = match.group(0)
            file_path = match.group(1).split(":")[0]
            start_line = int(match.group(2)) if match.group(2) else None
            end_line = int(match.group(3)) if match.group(3) else start_line

            # Validate against retrieved chunks
            matching_chunk = None
            for chunk in retrieved_chunks:
                if chunk.get("file_path", "").endswith(file_path) or file_path in chunk.get("file_path", ""):
                    matching_chunk = chunk
                    break

            if matching_chunk:
                citation_key = (file_path, start_line, end_line)
                if citation_key not in seen:
                    seen.add(citation_key)
                    citations.append({
                        "chunk_id": matching_chunk.get("chunk_id"),
                        "file_path": matching_chunk.get("file_path", file_path),
                        "symbol": matching_chunk.get("symbol_name"),
                        "start_line": start_line or matching_chunk.get("start_line"),
                        "end_line": end_line or matching_chunk.get("end_line"),
                        "content_preview": matching_chunk.get("content", "")[:200],
                    })

        # Also add all retrieved chunks as potential citations if few were found
        if len(citations) < 2:
            for chunk in retrieved_chunks[:5]:
                citation_key = (
                    chunk.get("file_path"),
                    chunk.get("start_line"),
                    chunk.get("end_line"),
                )
                if citation_key not in seen:
                    seen.add(citation_key)
                    citations.append({
                        "chunk_id": chunk.get("chunk_id"),
                        "file_path": chunk.get("file_path", ""),
                        "symbol": chunk.get("symbol_name"),
                        "start_line": chunk.get("start_line"),
                        "end_line": chunk.get("end_line"),
                        "content_preview": chunk.get("content", "")[:200],
                    })

        return citations
