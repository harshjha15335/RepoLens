"""Code parsing service using Tree-sitter for structure-aware analysis."""

import hashlib
import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Try importing tree-sitter
try:
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_java
    import tree_sitter_c
    import tree_sitter_cpp
    import tree_sitter_go
    from tree_sitter import Language, Parser

    TREE_SITTER_AVAILABLE = True

    # Initialize languages
    LANGUAGES = {}
    LANGUAGE_MODULES = {
        "python": tree_sitter_python,
        "javascript": tree_sitter_javascript,
        "typescript": tree_sitter_typescript,
        "java": tree_sitter_java,
        "c": tree_sitter_c,
        "cpp": tree_sitter_cpp,
        "go": tree_sitter_go,
    }

    for lang_name, module in LANGUAGE_MODULES.items():
        try:
            LANGUAGES[lang_name] = Language(module.language())
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter language {lang_name}: {e}")

except ImportError:
    TREE_SITTER_AVAILABLE = False
    LANGUAGES = {}
    logger.warning("Tree-sitter not available, falling back to regex parsing")


# Extension to language mapping
EXT_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".go": "go",
}

# Tree-sitter node types for symbol extraction by language
SYMBOL_QUERIES = {
    "python": {
        "class": ["class_definition"],
        "function": ["function_definition"],
        "import": ["import_statement", "import_from_statement"],
    },
    "javascript": {
        "class": ["class_declaration"],
        "function": ["function_declaration", "arrow_function", "method_definition"],
        "import": ["import_statement"],
        "export": ["export_statement"],
    },
    "typescript": {
        "class": ["class_declaration"],
        "function": ["function_declaration", "arrow_function", "method_definition"],
        "interface": ["interface_declaration"],
        "import": ["import_statement"],
        "export": ["export_statement"],
    },
    "java": {
        "class": ["class_declaration"],
        "function": ["method_declaration", "constructor_declaration"],
        "interface": ["interface_declaration"],
        "import": ["import_declaration"],
    },
    "c": {
        "function": ["function_definition"],
        "import": ["preproc_include"],
    },
    "cpp": {
        "class": ["class_specifier"],
        "function": ["function_definition"],
        "import": ["preproc_include"],
    },
    "go": {
        "function": ["function_declaration", "method_declaration"],
        "import": ["import_declaration"],
    },
}


class ParserService:
    """Parses source code files to extract structural information."""

    def parse_file(self, file_path: Path, source_dir: Path) -> dict | None:
        """Parse a source file and extract structural information.

        Returns a dict with:
        - file_path: relative path
        - language: detected language
        - content: file content
        - symbols: list of extracted symbols
        - imports: list of imports
        - content_hash: hash of content
        """
        try:
            rel_path = str(file_path.relative_to(source_dir))
            content = file_path.read_text(encoding="utf-8", errors="replace")

            if not content.strip():
                return None

            language = self._detect_language(file_path)
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            result = {
                "file_path": rel_path,
                "language": language,
                "content": content,
                "content_hash": content_hash,
                "symbols": [],
                "imports": [],
                "exports": [],
            }

            if language and TREE_SITTER_AVAILABLE and language in LANGUAGES:
                self._parse_with_tree_sitter(content, language, result)
            elif language in ("python", "javascript", "typescript"):
                self._parse_with_regex(content, language, result)
            else:
                # Non-code files (markdown, config, etc.)
                self._parse_text_file(content, file_path, result)

            return result

        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")
            return None

    def _detect_language(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        return EXT_TO_LANGUAGE.get(file_path.suffix.lower())

    def _parse_with_tree_sitter(self, content: str, language: str, result: dict):
        """Parse file using tree-sitter for accurate AST-based extraction."""
        lang = LANGUAGES.get(language)
        if not lang:
            return

        parser = Parser(lang)
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node

        symbols = []
        imports = []

        self._walk_tree(root, content, language, symbols, imports, parent_name=None)

        result["symbols"] = symbols
        result["imports"] = imports

    def _walk_tree(
        self,
        node,
        content: str,
        language: str,
        symbols: list,
        imports: list,
        parent_name: str | None,
        depth: int = 0,
    ):
        """Walk the AST tree extracting symbols."""
        queries = SYMBOL_QUERIES.get(language, {})

        node_type = node.type

        # Check if this is an import
        import_types = queries.get("import", [])
        if node_type in import_types:
            import_text = content[node.start_byte:node.end_byte].strip()
            imports.append(import_text)

        # Check if this is a class/function/method
        is_class = node_type in queries.get("class", [])
        is_function = node_type in queries.get("function", [])
        is_interface = node_type in queries.get("interface", [])

        if is_class or is_function or is_interface:
            name = self._extract_name(node, content, language)
            symbol_type = "class" if is_class else ("interface" if is_interface else "function")

            # If inside a class, it's a method
            if parent_name and is_function:
                symbol_type = "method"

            symbol = {
                "name": name,
                "type": symbol_type,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                "parent": parent_name,
                "content": content[node.start_byte:node.end_byte],
            }
            symbols.append(symbol)

            # Recurse into class to find methods
            if is_class:
                for child in node.children:
                    self._walk_tree(
                        child, content, language, symbols, imports,
                        parent_name=name, depth=depth + 1,
                    )
                return

        # Continue walking
        for child in node.children:
            self._walk_tree(
                child, content, language, symbols, imports,
                parent_name=parent_name, depth=depth + 1,
            )

    def _extract_name(self, node, content: str, language: str) -> str:
        """Extract the name from an AST node."""
        # Look for identifier child
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier", "type_identifier"):
                return content[child.start_byte:child.end_byte]

        # Fallback: first word after keyword
        text = content[node.start_byte:node.end_byte].split("\n")[0]
        parts = text.split()
        if len(parts) > 1:
            name = parts[1].split("(")[0].split(":")[0].split("{")[0]
            return name.strip()

        return "<anonymous>"

    def _parse_with_regex(self, content: str, language: str, result: dict):
        """Fallback regex-based parsing for when tree-sitter is unavailable."""
        lines = content.split("\n")
        symbols = []
        imports = []

        if language == "python":
            class_pattern = re.compile(r"^class\s+(\w+)")
            func_pattern = re.compile(r"^(\s*)def\s+(\w+)")
            import_pattern = re.compile(r"^(?:from\s+\S+\s+)?import\s+")

            current_class = None
            class_indent = 0

            for i, line in enumerate(lines):
                # Imports
                if import_pattern.match(line):
                    imports.append(line.strip())
                    continue

                # Classes
                m = class_pattern.match(line)
                if m:
                    current_class = m.group(1)
                    class_indent = len(line) - len(line.lstrip())
                    symbols.append({
                        "name": current_class,
                        "type": "class",
                        "start_line": i + 1,
                        "end_line": i + 1,  # Will be updated
                        "parent": None,
                        "content": line,
                    })
                    continue

                # Functions/Methods
                m = func_pattern.match(line)
                if m:
                    indent = len(m.group(1))
                    name = m.group(2)

                    if current_class and indent > class_indent:
                        sym_type = "method"
                        parent = current_class
                    else:
                        sym_type = "function"
                        parent = None
                        if indent <= class_indent:
                            current_class = None

                    symbols.append({
                        "name": name,
                        "type": sym_type,
                        "start_line": i + 1,
                        "end_line": i + 1,
                        "parent": parent,
                        "content": line,
                    })

        elif language in ("javascript", "typescript"):
            class_pattern = re.compile(r"(?:export\s+)?class\s+(\w+)")
            func_pattern = re.compile(
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
                r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\("
            )
            import_pattern = re.compile(r"^import\s+")

            for i, line in enumerate(lines):
                if import_pattern.match(line.strip()):
                    imports.append(line.strip())
                    continue

                m = class_pattern.search(line)
                if m:
                    symbols.append({
                        "name": m.group(1),
                        "type": "class",
                        "start_line": i + 1,
                        "end_line": i + 1,
                        "parent": None,
                        "content": line,
                    })
                    continue

                m = func_pattern.search(line)
                if m:
                    name = m.group(1) or m.group(2)
                    if name:
                        symbols.append({
                            "name": name,
                            "type": "function",
                            "start_line": i + 1,
                            "end_line": i + 1,
                            "parent": None,
                            "content": line,
                        })

        # Update end lines by finding the next symbol
        for i, sym in enumerate(symbols):
            if i + 1 < len(symbols):
                sym["end_line"] = symbols[i + 1]["start_line"] - 1
            else:
                sym["end_line"] = len(lines)

        result["symbols"] = symbols
        result["imports"] = imports

    def _parse_text_file(self, content: str, file_path: Path, result: dict):
        """Parse non-code files (markdown, config, etc.)."""
        # For markdown, extract headings as symbols
        if file_path.suffix.lower() in (".md", ".rst"):
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    level = len(line) - len(line.lstrip("#"))
                    title = line.lstrip("#").strip()
                    if title:
                        result["symbols"].append({
                            "name": title,
                            "type": f"heading_h{level}",
                            "start_line": i + 1,
                            "end_line": i + 1,
                            "parent": None,
                            "content": line,
                        })
