"""Structure-aware code chunking service."""

import hashlib
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Max chunk size in characters
MAX_CHUNK_SIZE = 2000
MIN_CHUNK_SIZE = 50
OVERLAP_LINES = 2


class ChunkingService:
    """Creates structure-aware chunks from parsed files."""

    def chunk_parsed_file(self, parsed_file: dict) -> list[dict]:
        """Create chunks from a parsed file.

        Strategy:
        1. If symbols exist, create a chunk per symbol (class, function, method)
        2. Create a file-level chunk with imports and top-level code
        3. Split oversized symbols intelligently
        4. For non-code files, use heading-aware or fixed-size chunking
        """
        file_path = parsed_file.get("file_path", "")
        language = parsed_file.get("language")
        content = parsed_file.get("content", "")
        symbols = parsed_file.get("symbols", [])
        imports = parsed_file.get("imports", [])
        content_hash = parsed_file.get("content_hash")

        if not content.strip():
            return []

        lines = content.split("\n")

        chunks = []

        if symbols and language:
            # Structure-aware chunking
            chunks = self._chunk_by_symbols(
                lines, symbols, imports, file_path, language, content_hash
            )
        else:
            # Text/config chunking
            chunks = self._chunk_text(
                content, file_path, language, content_hash
            )

        # Always add a file-level overview chunk
        file_chunk = self._create_file_overview_chunk(
            lines, imports, symbols, file_path, language, content_hash
        )
        if file_chunk:
            chunks.insert(0, file_chunk)

        return chunks

    def _chunk_by_symbols(
        self,
        lines: list[str],
        symbols: list[dict],
        imports: list[str],
        file_path: str,
        language: str,
        content_hash: str,
    ) -> list[dict]:
        """Create chunks based on code symbols (classes, functions, methods)."""
        chunks = []
        covered_lines = set()

        for symbol in symbols:
            name = symbol.get("name", "")
            sym_type = symbol.get("type", "")
            start_line = symbol.get("start_line", 1)
            end_line = symbol.get("end_line", len(lines))
            parent = symbol.get("parent")

            # Get symbol content
            chunk_lines = lines[start_line - 1:end_line]
            chunk_content = "\n".join(chunk_lines)

            if len(chunk_content) < MIN_CHUNK_SIZE:
                continue

            # Split oversized symbols
            if len(chunk_content) > MAX_CHUNK_SIZE:
                sub_chunks = self._split_large_symbol(
                    chunk_lines, name, sym_type, parent,
                    start_line, file_path, language, content_hash,
                )
                chunks.extend(sub_chunks)
            else:
                chunk = {
                    "content": chunk_content,
                    "content_hash": hashlib.sha256(
                        chunk_content.encode()
                    ).hexdigest()[:16],
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": name,
                    "symbol_type": sym_type,
                    "parent_symbol": parent,
                    "start_line": start_line,
                    "end_line": end_line,
                    "imports": imports if sym_type in ("class", "function") else [],
                    "definitions": [name],
                }
                chunks.append(chunk)

            for l in range(start_line, end_line + 1):
                covered_lines.add(l)

        # Capture uncovered code (top-level statements, etc.)
        uncovered = []
        current_start = None
        for i in range(1, len(lines) + 1):
            if i not in covered_lines:
                if current_start is None:
                    current_start = i
            else:
                if current_start is not None:
                    uncovered_content = "\n".join(
                        lines[current_start - 1:i - 1]
                    ).strip()
                    if len(uncovered_content) >= MIN_CHUNK_SIZE:
                        uncovered.append((current_start, i - 1, uncovered_content))
                    current_start = None

        if current_start is not None:
            uncovered_content = "\n".join(
                lines[current_start - 1:]
            ).strip()
            if len(uncovered_content) >= MIN_CHUNK_SIZE:
                uncovered.append((current_start, len(lines), uncovered_content))

        for start, end, content in uncovered:
            # Skip if it's just imports (already captured in file overview)
            if all(
                line.strip().startswith(("import", "from", "#", "//", "/*"))
                or not line.strip()
                for line in content.split("\n")
            ):
                continue

            chunks.append({
                "content": content,
                "content_hash": hashlib.sha256(
                    content.encode()
                ).hexdigest()[:16],
                "file_path": file_path,
                "language": language,
                "symbol_name": None,
                "symbol_type": "module",
                "parent_symbol": None,
                "start_line": start,
                "end_line": end,
                "imports": [],
                "definitions": [],
            })

        return chunks

    def _split_large_symbol(
        self,
        lines: list[str],
        name: str,
        sym_type: str,
        parent: str | None,
        base_start_line: int,
        file_path: str,
        language: str,
        content_hash: str,
    ) -> list[dict]:
        """Split a large symbol into smaller chunks intelligently."""
        chunks = []
        chunk_lines = []
        chunk_start = base_start_line
        part_index = 0

        for i, line in enumerate(lines):
            chunk_lines.append(line)
            current_content = "\n".join(chunk_lines)

            if len(current_content) >= MAX_CHUNK_SIZE:
                # Try to split at a logical boundary
                split_idx = self._find_split_point(chunk_lines)

                actual_lines = chunk_lines[:split_idx]
                remaining_lines = chunk_lines[split_idx:]

                content = "\n".join(actual_lines)
                if content.strip():
                    chunks.append({
                        "content": content,
                        "content_hash": hashlib.sha256(
                            content.encode()
                        ).hexdigest()[:16],
                        "file_path": file_path,
                        "language": language,
                        "symbol_name": f"{name} (part {part_index + 1})",
                        "symbol_type": sym_type,
                        "parent_symbol": parent,
                        "start_line": chunk_start,
                        "end_line": chunk_start + len(actual_lines) - 1,
                        "imports": [],
                        "definitions": [name] if part_index == 0 else [],
                    })
                    part_index += 1

                chunk_start = chunk_start + len(actual_lines)
                chunk_lines = remaining_lines

        # Remaining
        if chunk_lines:
            content = "\n".join(chunk_lines)
            if content.strip() and len(content) >= MIN_CHUNK_SIZE:
                chunks.append({
                    "content": content,
                    "content_hash": hashlib.sha256(
                        content.encode()
                    ).hexdigest()[:16],
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": f"{name} (part {part_index + 1})" if part_index > 0 else name,
                    "symbol_type": sym_type,
                    "parent_symbol": parent,
                    "start_line": chunk_start,
                    "end_line": chunk_start + len(chunk_lines) - 1,
                    "imports": [],
                    "definitions": [name] if part_index == 0 else [],
                })

        return chunks

    def _find_split_point(self, lines: list[str]) -> int:
        """Find a good split point in a list of lines."""
        # Try to split at empty lines or def/class boundaries
        target = len(lines) * 3 // 4  # Prefer splitting at 75%

        best = target
        best_score = 0

        for i in range(max(len(lines) // 2, 1), len(lines)):
            line = lines[i].strip()
            score = 0

            if not line:
                score = 3
            elif line.startswith(("def ", "async def ", "class ")):
                score = 5
            elif line.startswith(("#", "//", "/*")):
                score = 2
            elif line.endswith((":", "{", "}")):
                score = 1

            if score > best_score or (score == best_score and abs(i - target) < abs(best - target)):
                best = i
                best_score = score

        return max(best, len(lines) // 2)

    def _chunk_text(
        self,
        content: str,
        file_path: str,
        language: str | None,
        content_hash: str,
    ) -> list[dict]:
        """Chunk non-code files (markdown, config, etc.)."""
        chunks = []
        lines = content.split("\n")

        # For markdown, split by headings
        if file_path.endswith((".md", ".rst")):
            return self._chunk_markdown(content, file_path, language, content_hash)

        # For other text files, use fixed-size chunks
        chunk_lines = []
        chunk_start = 1

        for i, line in enumerate(lines):
            chunk_lines.append(line)
            current_content = "\n".join(chunk_lines)

            if len(current_content) >= MAX_CHUNK_SIZE:
                if current_content.strip():
                    chunks.append({
                        "content": current_content,
                        "content_hash": hashlib.sha256(
                            current_content.encode()
                        ).hexdigest()[:16],
                        "file_path": file_path,
                        "language": language,
                        "symbol_name": None,
                        "symbol_type": "text",
                        "parent_symbol": None,
                        "start_line": chunk_start,
                        "end_line": chunk_start + len(chunk_lines) - 1,
                        "imports": [],
                        "definitions": [],
                    })
                chunk_start = i + 2
                chunk_lines = []

        if chunk_lines:
            current_content = "\n".join(chunk_lines)
            if current_content.strip() and len(current_content) >= MIN_CHUNK_SIZE:
                chunks.append({
                    "content": current_content,
                    "content_hash": hashlib.sha256(
                        current_content.encode()
                    ).hexdigest()[:16],
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": None,
                    "symbol_type": "text",
                    "parent_symbol": None,
                    "start_line": chunk_start,
                    "end_line": chunk_start + len(chunk_lines) - 1,
                    "imports": [],
                    "definitions": [],
                })

        return chunks

    def _chunk_markdown(
        self,
        content: str,
        file_path: str,
        language: str | None,
        content_hash: str,
    ) -> list[dict]:
        """Chunk markdown by headings."""
        chunks = []
        lines = content.split("\n")

        current_heading = None
        current_lines = []
        current_start = 1

        for i, line in enumerate(lines):
            if line.startswith("#"):
                # Save previous section
                if current_lines:
                    section_content = "\n".join(current_lines).strip()
                    if section_content and len(section_content) >= MIN_CHUNK_SIZE:
                        chunks.append({
                            "content": section_content,
                            "content_hash": hashlib.sha256(
                                section_content.encode()
                            ).hexdigest()[:16],
                            "file_path": file_path,
                            "language": language,
                            "symbol_name": current_heading,
                            "symbol_type": "section",
                            "parent_symbol": None,
                            "start_line": current_start,
                            "end_line": current_start + len(current_lines) - 1,
                            "imports": [],
                            "definitions": [],
                        })

                current_heading = line.lstrip("#").strip()
                current_lines = [line]
                current_start = i + 1
            else:
                current_lines.append(line)

        # Last section
        if current_lines:
            section_content = "\n".join(current_lines).strip()
            if section_content and len(section_content) >= MIN_CHUNK_SIZE:
                chunks.append({
                    "content": section_content,
                    "content_hash": hashlib.sha256(
                        section_content.encode()
                    ).hexdigest()[:16],
                    "file_path": file_path,
                    "language": language,
                    "symbol_name": current_heading,
                    "symbol_type": "section",
                    "parent_symbol": None,
                    "start_line": current_start,
                    "end_line": current_start + len(current_lines) - 1,
                    "imports": [],
                    "definitions": [],
                })

        return chunks

    def _create_file_overview_chunk(
        self,
        lines: list[str],
        imports: list[str],
        symbols: list[dict],
        file_path: str,
        language: str | None,
        content_hash: str,
    ) -> dict | None:
        """Create a file-level overview chunk."""
        # Build overview from imports + symbol signatures
        overview_parts = []

        if imports:
            overview_parts.append("# Imports")
            for imp in imports[:20]:  # Limit imports
                overview_parts.append(imp)
            overview_parts.append("")

        if symbols:
            overview_parts.append("# Symbols")
            for sym in symbols:
                prefix = f"  " if sym.get("parent") else ""
                overview_parts.append(
                    f"{prefix}{sym.get('type', 'symbol')}: {sym.get('name', 'unknown')}"
                    f" (lines {sym.get('start_line', '?')}-{sym.get('end_line', '?')})"
                )

        if not overview_parts:
            # For small files, use the whole content
            content = "\n".join(lines[:50])  # First 50 lines as overview
            if len(content) < MIN_CHUNK_SIZE:
                return None
            overview_parts = [content]

        overview_content = "\n".join(overview_parts)

        definitions = [s.get("name", "") for s in symbols if s.get("name")]

        return {
            "content": overview_content,
            "content_hash": hashlib.sha256(
                overview_content.encode()
            ).hexdigest()[:16],
            "file_path": file_path,
            "language": language,
            "symbol_name": file_path.split("/")[-1],
            "symbol_type": "file",
            "parent_symbol": None,
            "start_line": 1,
            "end_line": len(lines),
            "imports": imports,
            "definitions": definitions,
        }
