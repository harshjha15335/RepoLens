"""Code graph service for building and querying repository relationships."""

import re
from collections import defaultdict

from app.core.logging import get_logger
from app.services.parsing.service import LANGUAGES, Parser

logger = get_logger(__name__)

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

    def _execute_query(self, content: str, language: str, query_str: str) -> list[tuple[str | None, str]]:
        """Execute a tree-sitter query and return matched nodes."""
        lang = LANGUAGES.get(language)
        if not lang:
            return []

        parser = Parser(lang)
        tree = parser.parse(content.encode("utf-8"))
        query = lang.query(query_str)
        captures = query.captures(tree.root_node)

        results = []
        capture_map = {}
        for node, tag in captures:
            if tag == "@receiver":
                capture_map[node.start_byte] = (node, "receiver")
            elif tag == "@name":
                receiver = None
                for start_byte, (node_r, tag_r) in capture_map.items():
                    if node_r.end_byte <= node.start_byte:
                        receiver = content[node_r.start_byte:node_r.end_byte]
                name = content[node.start_byte:node.end_byte]
                results.append((receiver, name))

        return results

    def _execute_query(self, content: str, language: str, query_str: str) -> list[tuple[str | None, str]]:
        """Execute a tree-sitter query and return matched nodes."""
        lang = LANGUAGES.get(language)
        if not lang:
            return []

        parser = Parser(lang)
        tree = parser.parse(content.encode("utf-8"))
        query = lang.query(query_str)
        captures = query.captures(tree.root_node)

        results = []
        capture_map = {}
        for node, tag in captures:
            if tag == "@receiver":
                capture_map[node.start_byte] = (node, "receiver")
            elif tag == "@name":
                receiver = None
                for start_byte, (node_r, tag_r) in capture_map.items():
                    if node_r.end_byte <= node.start_byte:
                        receiver = content[node_r.start_byte:node_r.end_byte]
                name = content[node.start_byte:node.end_byte]
                results.append((receiver, name))

        return results

    def _extract_import_target(self, import_stmt: str, language: str) -> str | None:
        """Extract the target name from an import statement using tree-sitter."""
        # Since we are given the statement string, we parse just that snippet
        query_map = {
            "python": "(import_from_statement name: (identifier) @name) @name",
            "javascript": "(import_statement name: (identifier) @name) @name",
            "typescript": "(import_statement name: (identifier) @name) @name",
            "java": "(import_declaration name: (identifier) @name) @name",
        }
        query = query_map.get(language)
        if not query:
            return None

        results = self._execute_query(import_stmt, language, query)
        return results[0][1] if results else None

    def _extract_calls(self, content: str, language: str) -> list[tuple[str | None, str]]:
        """Extract function/method call names from code content using tree-sitter."""
        query_map = {
            "python": "(call function: (identifier) @name) @name | (call function: (attribute attribute: (identifier) @receiver function: (identifier) @name))",
            "javascript": "(call_expression function: (identifier) @name) @name | (call_expression function: (member_expression object: (identifier) @receiver property: (identifier) @name))",
            "typescript": "(call_expression function: (identifier) @name) @name | (call_expression function: (member_expression object: (identifier) @receiver property: (identifier) @name))",
            "java": "(method_invocation name: (identifier) @name) @name | (method_invocation object: (identifier) @receiver name: (identifier) @name)",
        }
        query = query_map.get(language)
        if not query:
            return []

        return self._execute_query(content, language, query)

    def _extract_bases(self, content: str, language: str) -> list[str]:
        """Extract base/parent class names using tree-sitter."""
        query_map = {
            "python": "(class_definition superclasses: (argument_list (identifier) @base))",
            "java": "(class_declaration superclass: (type_identifier) @base)",
            "typescript": "(class_declaration superclass: (type_identifier) @base)",
            "javascript": "(class_declaration superclass: (type_identifier) @base)",
        }
        query = query_map.get(language)
        if not query:
            return []

        results = self._execute_query(content, language, query)
        return [res[1] for res in results]


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
