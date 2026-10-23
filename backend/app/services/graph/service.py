"""Code graph service for building and querying repository relationships."""

import re
from collections import defaultdict

from app.core.logging import get_logger

logger = get_logger(__name__)


class GraphService:
    """Builds and queries a lightweight code graph."""

    def build_graph(self, parsed_files: list[dict], repository_id: str) -> dict:
        """Build a code graph from parsed files.

        Creates nodes (file, class, function, method) and edges
        (CONTAINS, IMPORTS, CALLS, INHERITS).
        """
        nodes = []
        edges = []
        node_map = {}  # qualified_name -> node_id
        symbols_by_name = defaultdict(list)

        # Phase 1: Create nodes
        for pf in parsed_files:
            file_path = pf.get("file_path", "")
            language = pf.get("language", "")

            # File node
            file_node_id = f"file:{file_path}"
            nodes.append({
                "id": file_node_id,
                "type": "file",
                "name": file_path.split("/")[-1],
                "qualified_name": file_path,
                "file_path": file_path,
                "start_line": 1,
                "end_line": len(pf.get("content", "").split("\n")),
                "metadata": {"language": language},
            })
            node_map[file_path] = file_node_id

            # Symbol nodes
            for sym in pf.get("symbols", []):
                sym_name = sym.get("name", "")
                sym_type = sym.get("type", "")
                parent = sym.get("parent")

                if sym_type in ("class", "function", "method", "interface"):
                    if parent:
                        qualified = f"{file_path}:{parent}.{sym_name}"
                    else:
                        qualified = f"{file_path}:{sym_name}"

                    node_id = f"{sym_type}:{qualified}"
                    nodes.append({
                        "id": node_id,
                        "type": sym_type,
                        "name": sym_name,
                        "qualified_name": qualified,
                        "file_path": file_path,
                        "start_line": sym.get("start_line"),
                        "end_line": sym.get("end_line"),
                        "metadata": {"language": language, "parent": parent},
                    })
                    node_map[qualified] = node_id
                    symbols_by_name[sym_name].append({
                        "id": node_id,
                        "file_path": file_path,
                        "parent": parent,
                        "type": sym_type,
                    })

                    # CONTAINS edge: file -> symbol or class -> method
                    if parent and f"{file_path}:{parent}" in node_map:
                        edges.append({
                            "source": node_map[f"{file_path}:{parent}"],
                            "target": node_id,
                            "type": "CONTAINS",
                        })
                    else:
                        edges.append({
                            "source": file_node_id,
                            "target": node_id,
                            "type": "CONTAINS",
                        })

        # Phase 2: Extract relationships
        def resolve_symbol(name: str, file_path: str, parent: str | None = None,
                           receiver: str | None = None, type_: str | None = None) -> str | None:
            candidates = [
                node for node in symbols_by_name.get(name, [])
                if type_ is None or node["type"] == type_
            ]
            if receiver in ("self", "this"):
                owned = [n for n in candidates if n["file_path"] == file_path and n["parent"] == parent]
                return owned[0]["id"] if len(owned) == 1 else None
            if receiver:
                return None  # The receiver's type is not known statically.
            same_parent = [n for n in candidates if n["file_path"] == file_path and n["parent"] == parent]
            if len(same_parent) == 1:
                return same_parent[0]["id"]
            same_file = [n for n in candidates if n["file_path"] == file_path and n["parent"] is None]
            if len(same_file) == 1:
                return same_file[0]["id"]
            return candidates[0]["id"] if len(candidates) == 1 else None

        for pf in parsed_files:
            file_path = pf.get("file_path", "")
            language = pf.get("language", "")
            file_node_id = f"file:{file_path}"

            # IMPORTS edges
            for imp in pf.get("imports", []):
                imported = self._extract_import_target(imp, language)
                if imported:
                    # Try to find matching file/symbol
                    target_id = resolve_symbol(imported, file_path)
                    if target_id:
                        edges.append({
                            "source": file_node_id,
                            "target": target_id,
                            "type": "IMPORTS",
                            "metadata": {"import_statement": imp},
                        })

            # CALLS edges (best effort from static analysis)
            for sym in pf.get("symbols", []):
                if sym.get("type") not in ("function", "method"):
                    continue
                sym_content = sym.get("content", "")
                sym_name = sym.get("name", "")

                if sym.get("parent"):
                    caller_qualified = f"{file_path}:{sym.get('parent')}.{sym_name}"
                else:
                    caller_qualified = f"{file_path}:{sym_name}"

                caller_id = node_map.get(caller_qualified)
                if not caller_id:
                    continue

                # Find function calls in the symbol body
                calls = self._extract_calls(sym_content, language)
                for receiver, call_name in calls:
                    if call_name == sym_name:  # Skip self-recursion
                        continue
                    # Try to find the called symbol
                    target_id = resolve_symbol(call_name, file_path, sym.get("parent"), receiver)
                    if target_id and target_id != caller_id:
                        edges.append({
                            "source": caller_id,
                            "target": target_id,
                            "type": "CALLS",
                        })

            # INHERITS edges
            for sym in pf.get("symbols", []):
                if sym.get("type") != "class":
                    continue

                bases = self._extract_bases(sym.get("content", ""), language)
                sym_qualified = f"{file_path}:{sym.get('name', '')}"
                sym_id = node_map.get(sym_qualified)

                if not sym_id:
                    continue

                for base in bases:
                    base_id = resolve_symbol(base, file_path, type_="class")
                    if base_id:
                        edges.append({
                            "source": sym_id,
                            "target": base_id,
                            "type": "INHERITS",
                        })

        # Deduplicate edges
        seen = set()
        unique_edges = []
        for edge in edges:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in seen:
                seen.add(key)
                unique_edges.append(edge)

        logger.info(f"Graph built: {len(nodes)} nodes, {len(unique_edges)} edges")

        return {
            "nodes": nodes,
            "edges": unique_edges,
        }

    def _extract_import_target(self, import_stmt: str, language: str) -> str | None:
        """Extract the target name from an import statement."""
        if language == "python":
            # from module import name
            m = re.search(r"from\s+(\S+)\s+import\s+(\S+)", import_stmt)
            if m:
                return m.group(2).split(",")[0].strip()
            # import module
            m = re.search(r"import\s+(\S+)", import_stmt)
            if m:
                return m.group(1).split(",")[0].split(".")[-1].strip()

        elif language in ("javascript", "typescript"):
            # import { Name } from 'module'
            m = re.search(r"import\s+\{?\s*(\w+)", import_stmt)
            if m:
                return m.group(1)
            # import Name from 'module'
            m = re.search(r"import\s+(\w+)", import_stmt)
            if m:
                return m.group(1)

        elif language == "java":
            m = re.search(r"import\s+[\w.]+\.(\w+)", import_stmt)
            if m:
                return m.group(1)

        return None

    def _extract_calls(self, content: str, language: str) -> list[tuple[str | None, str]]:
        """Extract function/method call names from code content."""
        # Simple regex-based call extraction
        # Matches functionName(, self.method(, and obj.method(.
        calls = set()
        pattern = re.compile(r'(?<![.\w])(?:(\w+)\s*\.\s*)?(\w+)\s*\(', re.MULTILINE)

        for m in pattern.finditer(content):
            receiver, name = m.groups()
            # Filter out language keywords and builtins
            if name not in _KEYWORDS and len(name) > 1:
                calls.add((receiver, name))

        return list(calls)

    def _extract_bases(self, content: str, language: str) -> list[str]:
        """Extract base/parent class names."""
        bases = []

        if language == "python":
            m = re.search(r"class\s+\w+\s*\(([^)]+)\)", content)
            if m:
                for base in m.group(1).split(","):
                    base = base.strip()
                    if base and base not in ("object", "ABC"):
                        bases.append(base)

        elif language in ("java", "typescript", "javascript"):
            m = re.search(r"extends\s+(\w+)", content)
            if m:
                bases.append(m.group(1))
            m = re.search(r"implements\s+([\w,\s]+)", content)
            if m:
                for impl in m.group(1).split(","):
                    bases.append(impl.strip())

        return bases


# Common keywords to filter from call extraction
_KEYWORDS = {
    "if", "else", "elif", "for", "while", "return", "def", "class",
    "import", "from", "try", "except", "finally", "with", "as",
    "yield", "raise", "pass", "break", "continue", "lambda",
    "and", "or", "not", "is", "in", "True", "False", "None",
    "var", "let", "const", "function", "new", "this", "super",
    "void", "int", "float", "string", "bool", "null", "undefined",
    "switch", "case", "default", "throw", "catch",
    "public", "private", "protected", "static", "final",
    "print", "len", "range", "list", "dict", "set", "str",
    "isinstance", "type", "hasattr", "getattr", "setattr",
    "console", "require", "module", "exports",
}
