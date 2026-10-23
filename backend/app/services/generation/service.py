"""LLM generation service with grounded prompts, tutor modes, and citation handling."""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.core.config import get_settings
from app.core.errors import GenerationProviderError
from app.core.logging import get_logger
from app.services.retrieval.service import RetrievalService

logger = get_logger(__name__)


# ─── Tutor Mode Prompts ──────────────────────────────────────────

SYSTEM_PROMPTS = {
    "beginner": """You are CodeMentor in BEGINNER MODE, a clear and patient AI tutor helping someone learn to code.

STRUCTURE YOUR ANSWER IN THESE 3 DISTINCT SECTIONS:
1. Concept and Analogy: Explain the high-level idea using a simple real-world analogy. Keep it welcoming and jargon-free.
2. Step-by-Step Breakdown: Explain what the code does step-by-step in clear, easy-to-follow bullet points.
3. Jargon Buster: Define any technical terms used (such as "method", "class", "precedence", or "recursion") in plain language.

RULES:
- Do NOT use emojis or icons anywhere in your response.
- Answer ONLY using the provided repository evidence.
- Cite sources using [file_path:line_start-line_end] format.
- Keep explanations intuitive, friendly, and accessible to newcomers.
- NEVER invent files, functions, or behavior.""",

    "developer": """You are CodeMentor in DEVELOPER MODE, a senior software engineer conducting a technical code review.

STRUCTURE YOUR ANSWER IN THESE 3 DISTINCT SECTIONS:
1. Architecture and Data Flow: Concise, precise technical summary of components, function signatures, inputs, and outputs.
2. Implementation and Abstractions: Detail design patterns, state mutations, and internal call chains.
3. Engineering Notes: Note modularity, conventions, dependencies, and code hygiene observed in the repository.

RULES:
- Do NOT use emojis or icons anywhere in your response.
- Answer ONLY using the provided repository evidence.
- Cite sources using [file_path:line_start-line_end] format.
- Be direct, professional, and dense with technical insight.
- NEVER invent files, functions, or behavior.""",

    "interview": """You are CodeMentor in INTERVIEW MODE, an expert technical interviewer preparing a candidate for system design and coding interviews.

STRUCTURE YOUR ANSWER IN THESE 4 DISTINCT SECTIONS:
1. The 30-Second Elevator Pitch: How to succinctly explain this code and its purpose to an interviewer.
2. Design Trade-offs and Decisions: Why this approach was chosen versus alternatives (e.g., recursive descent vs regex, OOP inheritance vs composition).
3. Time and Space Complexity: Big-O analysis (O(1), O(n), etc.) for primary operations with justification.
4. Top Interview Questions: 2-3 tough questions an interviewer would ask about this code and how to answer them.

RULES:
- Do NOT use emojis or icons anywhere in your response.
- Answer ONLY using the provided repository evidence.
- Cite sources using [file_path:line_start-line_end] format.
- Highlight architectural trade-offs, scalability, and complexity.
- NEVER invent files, functions, or behavior.""",

    "debug": """You are CodeMentor in DEBUG MODE, a site-reliability and defensive engineering specialist hunting for bugs, regressions, and failure modes.

STRUCTURE YOUR ANSWER IN THESE 3 DISTINCT SECTIONS:
1. Edge Cases and Failure Points: Identify unhandled inputs, missing validations, boundary conditions (e.g. division by zero, empty inputs, malformed types, overflow).
2. State Mutation and Invariants: Trace how state (such as history, caches, or last results) changes and where corruption could occur.
3. Defensive Fixes and Tests to Add: Concrete unit test cases and defensive coding patterns to make this code bulletproof.

RULES:
- Do NOT use emojis or icons anywhere in your response.
- Answer ONLY using the provided repository evidence.
- Cite sources using [file_path:line_start-line_end] format.
- Distinguish verified code facts from potential failure hypotheses.
- NEVER invent files, functions, or behavior.""",
}


CONTEXT_TEMPLATE = """## Repository Evidence

The selected code, when present, is the primary evidence for the question.
Other code chunks were retrieved from the repository for related context.
Use ONLY this evidence to form your answer. Cite sources with [file_path:line_start-line_end].

{context_blocks}

## Conversation History
{history_text}

## Question
{question}

Answer directly using the repository evidence above. Include citations."""


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
            async with httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=10.0)) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature,
                            "num_thread": 8,
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
            async with httpx.AsyncClient(timeout=240) as client:
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
                            "num_thread": 8,
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
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "RepoLens",
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
                msg = data["choices"][0]["message"]
                return msg.get("content") or msg.get("reasoning") or ""
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
        provider_name = settings.llm_provider.lower()
        if provider_name == "groq":
            base_url = settings.llm_base_url or "https://api.groq.com/openai/v1"
            model = settings.llm_model if settings.llm_model not in ("llama3.1:8b", "qwen2.5-coder:latest") else "llama-3.3-70b-versatile"
            self.provider = OpenAICompatibleProvider(
                model=model,
                base_url=base_url,
                api_key=settings.llm_api_key,
            )
        elif provider_name == "openrouter":
            base_url = settings.llm_base_url or "https://openrouter.ai/api/v1"
            model = settings.llm_model if settings.llm_model not in ("llama3.1:8b", "qwen2.5-coder:latest") else "meta-llama/llama-3.3-70b-instruct:free"
            self.provider = OpenAICompatibleProvider(
                model=model,
                base_url=base_url,
                api_key=settings.llm_api_key,
            )
        elif provider_name in ("openai", "api"):
            base_url = settings.llm_base_url or "https://api.openai.com/v1"
            model = settings.llm_model if settings.llm_model not in ("llama3.1:8b", "qwen2.5-coder:latest") else "gpt-4o-mini"
            self.provider = OpenAICompatibleProvider(
                model=model,
                base_url=base_url,
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
        code_context: dict | None = None,
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

        # Step 1: Retrieve (fast path if code already selected)
        retrieval_result = await self.retrieval.search(
            repository_id=repository_id,
            query=question,
            strategy="hybrid",
            top_k=3 if code_context else None,
            enable_graph_expansion=not bool(code_context),
            enable_mmr=False,
        )
        retrieved_chunks = retrieval_result.get("chunks", [])
        evidence_chunks = ([code_context] if code_context else []) + retrieved_chunks

        # Step 2: Build context with token budget
        context_blocks = self._build_context(
            evidence_chunks,
            budget=self.settings.context_token_budget,
        )

        # Step 3: Build messages
        system_prompt = SYSTEM_PROMPTS.get(tutor_mode, SYSTEM_PROMPTS["developer"])

        history_text = ""
        if conversation_history and not code_context:
            recent = conversation_history[-6:]  # Last 3 exchanges
            history_text = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:300]}"
                for m in recent
            )

        mode_instructions = {
            "beginner": "Format your response strictly using the BEGINNER MODE sections: 1. Concept and Analogy, 2. Step-by-Step Breakdown, 3. Jargon Buster.",
            "developer": "Format your response strictly using the DEVELOPER MODE sections: 1. Architecture and Data Flow, 2. Implementation and Abstractions, 3. Engineering Notes.",
            "interview": "Format your response strictly using the INTERVIEW MODE sections: 1. The 30-Second Elevator Pitch, 2. Design Trade-offs and Decisions, 3. Time and Space Complexity, 4. Top Interview Questions.",
            "debug": "Format your response strictly using the DEBUG MODE sections: 1. Edge Cases and Failure Points, 2. State Mutation and Invariants, 3. Defensive Fixes and Tests to Add.",
        }
        mode_instruction = mode_instructions.get(tutor_mode, mode_instructions["developer"])

        user_content = CONTEXT_TEMPLATE.format(
            context_blocks=context_blocks,
            history_text=history_text or "(No previous conversation)",
            question=question,
        )
        if code_context:
            action_instructions = {
                "explain": "Explain what these selected lines do and why their state or return values matter.",
                "debug": "Check for defects in these selected lines. If none is supported by the source, say that; distinguish possible risks from verified bugs.",
                "trace": "Trace execution in these selected lines as a short ordered sequence. Name calls shown in the selected source; if there are no calls, explicitly say so. Do not replace the trace with a general explanation.",
            }
            user_content += (
                "\nAnswer the question about the Selected code section first. "
                "Cite the exact source lines that support each claim."
            )
            user_content += "\n" + action_instructions.get(code_context.get("action"), "")

        user_content += f"\n\n{mode_instruction}\nBe clear and concise. Do NOT use any emojis or icons. Always cite line numbers with [file_path:start-end]."

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
            if not answer or not answer.strip():
                raise GenerationProviderError("The generation provider returned an empty answer")
        except Exception as e:
            logger.warning(f"LLM provider error ({e}), using grounded offline synthesis fallback.")
            answer = self._offline_grounded_synthesis(question, tutor_mode, evidence_chunks)

        # Strip all emojis and pictographs from the answer
        answer = re.sub(
            r'[𐀀-􏿿]|[☀-➿]|[⌀-⏿]|[⭐-⭕]|[︎️]',
            '',
            answer,
        )
        answer = re.sub(r'[ 	]+', ' ', answer)

        gen_latency_ms = (time.time() - gen_start) * 1000

        # Step 5: Extract and validate citations
        citations = self._extract_citations(answer, evidence_chunks)
        if not citations:
            # A model can answer from context yet omit the citation syntax. Show
            # the retrieved source explicitly so the user can inspect it, without
            # presenting the reference as proof of every claim in the answer.
            for chunk in evidence_chunks:
                file_path = chunk.get("file_path")
                start_line = chunk.get("start_line")
                end_line = chunk.get("end_line")
                if not file_path or not isinstance(start_line, int) or not isinstance(end_line, int):
                    continue
                reference = f"[{file_path}:{start_line}-{end_line}]"
                source_citations = self._extract_citations(reference, evidence_chunks)
                if source_citations:
                    answer = f"{answer.rstrip()}\n\nRetrieved source to inspect: {reference}"
                    citations = source_citations
                    break

        total_latency_ms = (time.time() - start_time) * 1000

        return {
            "answer": answer,
            "citations": citations,
            "metadata": {
                "tutor_mode": tutor_mode,
                "intent": retrieval_result.get("intent"),
                "chunks_retrieved": len(retrieved_chunks),
                "selected_code": bool(code_context),
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
            if chunk.get("selected") and isinstance(start, int):
                content = "\n".join(f"{start + offset} | {line}" for offset, line in enumerate(content.split("\n")))

            # Deduplicate
            range_key = (file_path, start, end)
            if range_key in seen_ranges:
                continue
            seen_ranges.add(range_key)

            # Check budget
            header = f"\n### {'Selected code: ' if chunk.get('selected') else ''}{file_path}"
            if symbol:
                header += f" — {symbol}"
            header += f" (lines {start}–{end})"

            block = f"{header}\n```\n{content}\n```\n"

            if used_chars + len(block) > char_budget:
                if chunk.get("selected"):
                    # The exact selection takes precedence over the retrieval budget.
                    context_parts.append(block)
                    used_chars += len(block)
                    continue
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
        """Show relevant evidence without inferring behavior when the LLM is unavailable."""
        if not retrieved_chunks:
            return "I could not find sufficient repository evidence to answer your question."
        introductions = {
            "beginner": "Here are the closest source excerpts. Read them from top to bottom to see what the code actually does:",
            "developer": "Here are the closest implementation excerpts for your question:",
            "interview": "Use these source excerpts to build an interview answer, citing the behavior you can verify:",
            "debug": "Start investigating with these source excerpts. Check the conditions and return paths shown here:",
        }
        parts = [
            "The language model is unavailable, so I cannot reliably interpret the full behavior from these excerpts alone.",
            introductions.get(tutor_mode, introductions["developer"]),
        ]
        for chunk in retrieved_chunks[:2]:
            file_path = chunk.get("file_path", "")
            start_line = chunk.get("start_line", 1)
            end_line = chunk.get("end_line", start_line)
            symbol = chunk.get("symbol_name")
            snippet = (chunk.get("content") or "").strip()[:700]
            if not file_path or not snippet:
                continue
            label = f"`{symbol}`" if symbol else "Source"
            parts.append(
                f"{label} [{file_path}:{start_line}-{end_line}]\n```text\n{snippet}\n```"
            )
        return "\n\n".join(parts)

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
            file_path = match.group(1).split(":")[0]
            start_line = int(match.group(2)) if match.group(2) else None
            end_line = int(match.group(3)) if match.group(3) else start_line

            # Validate against retrieved chunks
            matching_chunk = None
            for chunk in retrieved_chunks:
                actual_path = chunk.get("file_path", "").replace("\\", "/")
                cited_path = file_path.replace("\\", "/")
                if actual_path == cited_path or actual_path.endswith("/" + cited_path):
                    if start_line is not None and not (
                        chunk.get("start_line", 0) <= start_line <= end_line <= chunk.get("end_line", 0)
                    ):
                        continue
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

        return citations
