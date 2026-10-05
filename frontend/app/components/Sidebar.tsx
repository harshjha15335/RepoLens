"use client";

import React, { useState, useMemo } from "react";
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  Search,
  ChevronRight,
  ChevronDown,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { FileInfo, SymbolInfo, ChatSession, Repository, ActiveActivityView } from "../types";

interface SidebarProps {
  currentRepo: Repository | null;
  files: FileInfo[];
  symbols: SymbolInfo[];
  sessions: ChatSession[];
  currentSessionId?: string;
  selectedFilePath?: string;
  activeView: ActiveActivityView | "sessions";
  onSelectFile: (path: string) => void;
  onSelectSymbol: (symbol: SymbolInfo) => void;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onAskQuery: (q: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  width?: number;
}

interface TreeNode {
  name: string;
  path: string;
  isFile: boolean;
  fileInfo?: FileInfo;
  children: { [name: string]: TreeNode };
}

export default function Sidebar({
  currentRepo,
  files,
  symbols,
  selectedFilePath,
  onSelectFile,
  onSelectSymbol,
  onAskQuery,
  collapsed,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<{ [path: string]: boolean }>({
    "": true,
  });

  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  // Build tree structure from files
  const fileTree = useMemo(() => {
    const root: TreeNode = { name: "root", path: "", isFile: false, children: {} };

    const filteredFiles = searchQuery.trim()
      ? files.filter((f) => f.path.toLowerCase().includes(searchQuery.toLowerCase()))
      : files;

    filteredFiles.forEach((file) => {
      const parts = file.path.split("/");
      let current = root;

      parts.forEach((part, index) => {
        const isFile = index === parts.length - 1;
        const currentPath = parts.slice(0, index + 1).join("/");

        if (!current.children[part]) {
          current.children[part] = {
            name: part,
            path: currentPath,
            isFile,
            fileInfo: isFile ? file : undefined,
            children: {},
          };
        }
        current = current.children[part];
      });
    });

    return root;
  }, [files, searchQuery]);

  // Filtered symbols for search
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return { files: [], symbols: [] };
    const q = searchQuery.toLowerCase().trim();
    return {
      files: files.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 10),
      symbols: symbols
        .filter((s) => s.name.toLowerCase().includes(q) || s.file_path.toLowerCase().includes(q))
        .slice(0, 15),
    };
  }, [files, symbols, searchQuery]);

  if (collapsed) return null;

  const getFileIcon = (name: string) => {
    if (name.endsWith(".py"))
      return <FileCode style={{ width: 14, height: 14, color: "#e5a00d", flexShrink: 0 }} />;
    if (name.endsWith(".ts") || name.endsWith(".tsx"))
      return <FileCode style={{ width: 14, height: 14, color: "#3178c6", flexShrink: 0 }} />;
    if (name.endsWith(".js") || name.endsWith(".jsx"))
      return <FileCode style={{ width: 14, height: 14, color: "#f0db4f", flexShrink: 0 }} />;
    if (name.endsWith(".md"))
      return <FileText style={{ width: 14, height: 14, color: "#707070", flexShrink: 0 }} />;
    return <FileCode style={{ width: 14, height: 14, color: "var(--text-muted)", flexShrink: 0 }} />;
  };

  const renderTree = (node: TreeNode, depth = 0): React.ReactNode => {
    const isExpanded = expandedFolders[node.path] ?? depth < 2;

    return (
      <div key={node.path || "root"}>
        {node.path !== "" && (
          <div
            onClick={() => {
              if (node.isFile) onSelectFile(node.path);
              else toggleFolder(node.path);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "5px 8px",
              paddingLeft: `${depth * 14 + 8}px`,
              borderRadius: "var(--radius-row)",
              cursor: "pointer",
              fontSize: 13,
              userSelect: "none",
              transition: "background 80ms",
              background:
                node.isFile && selectedFilePath === node.path ? "#f6f6f6" : "transparent",
              color:
                node.isFile && selectedFilePath === node.path
                  ? "var(--text-primary)"
                  : "var(--text-primary)",
            }}
            onMouseEnter={(e) => {
              if (!(node.isFile && selectedFilePath === node.path))
                e.currentTarget.style.background = "var(--surface-hover)";
            }}
            onMouseLeave={(e) => {
              if (!(node.isFile && selectedFilePath === node.path))
                e.currentTarget.style.background = "transparent";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, overflow: "hidden" }}>
              {!node.isFile && (
                <span style={{ display: "flex", alignItems: "center", color: "var(--text-muted)", flexShrink: 0 }}>
                  {isExpanded ? (
                    <ChevronDown style={{ width: 13, height: 13 }} />
                  ) : (
                    <ChevronRight style={{ width: 13, height: 13 }} />
                  )}
                </span>
              )}
              {node.isFile ? (
                getFileIcon(node.name)
              ) : isExpanded ? (
                <FolderOpen style={{ width: 14, height: 14, color: "#9ca3af", flexShrink: 0 }} />
              ) : (
                <Folder style={{ width: 14, height: 14, color: "#9ca3af", flexShrink: 0 }} />
              )}
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  fontWeight: node.isFile && selectedFilePath === node.path ? 500 : 400,
                  color: node.isFile && selectedFilePath === node.path ? "var(--text-primary)" : "#4b5563",
                  fontSize: 13,
                }}
              >
                {node.name}
              </span>
            </div>
          </div>
        )}

        {(!node.path || isExpanded) &&
          Object.values(node.children)
            .sort((a, b) => {
              if (a.isFile === b.isFile) return a.name.localeCompare(b.name);
              return a.isFile ? 1 : -1;
            })
            .map((child) => renderTree(child, node.path === "" ? 0 : depth + 1))}
      </div>
    );
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--surface)",
        overflow: "hidden",
      }}
    >
      {/* ─── Search Code Input ─── */}
      <div style={{ padding: "14px 14px 10px 14px" }}>
        <div style={{ position: "relative" }}>
          <Search
            style={{
              width: 14,
              height: 14,
              color: "var(--text-muted)",
              position: "absolute",
              left: 11,
              top: "50%",
              transform: "translateY(-50%)",
            }}
          />
          <input
            type="text"
            placeholder="Search Code"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              height: 38,
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-control)",
              paddingLeft: 34,
              paddingRight: 10,
              fontSize: 13,
              color: "var(--text-primary)",
              background: "var(--surface)",
              outline: "none",
              transition: "border-color 120ms",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--blue)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
          />
        </div>
      </div>

      {/* ─── File Tree / Filtered Results ─── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 6px 12px 6px" }}>
        {searchQuery.trim() ? (
          <div style={{ padding: "0 4px" }}>
            {/* Ask AI prompt shortcut */}
            <div
              onClick={() => onAskQuery(searchQuery)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                margin: "4px 0 10px",
                borderRadius: "var(--radius-row)",
                background: "var(--blue-light)",
                cursor: "pointer",
                fontSize: 12,
                color: "var(--blue)",
                fontWeight: 500,
                transition: "background 100ms",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden" }}>
                <Sparkles style={{ width: 13, height: 13, flexShrink: 0 }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  Ask: &quot;{searchQuery}&quot;
                </span>
              </div>
              <ArrowRight style={{ width: 12, height: 12, flexShrink: 0 }} />
            </div>

            {/* File matches */}
            {searchResults.files.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    color: "var(--text-muted)",
                    letterSpacing: "0.05em",
                    padding: "4px 0",
                    marginBottom: 2,
                  }}
                >
                  Files ({searchResults.files.length})
                </div>
                {searchResults.files.map((f) => (
                  <div
                    key={f.id || f.path}
                    onClick={() => onSelectFile(f.path)}
                    style={{
                      padding: "6px 8px",
                      borderRadius: "var(--radius-row)",
                      cursor: "pointer",
                      fontSize: 12,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      color: "var(--text-primary)",
                      transition: "background 80ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <FileCode style={{ width: 13, height: 13, color: "var(--text-muted)", flexShrink: 0 }} />
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {f.path}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Symbol matches */}
            {searchResults.symbols.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    color: "var(--text-muted)",
                    letterSpacing: "0.05em",
                    padding: "4px 0",
                    marginBottom: 2,
                  }}
                >
                  Symbols ({searchResults.symbols.length})
                </div>
                {searchResults.symbols.map((s) => (
                  <div
                    key={`${s.file_path}-${s.name}-${s.start_line}`}
                    onClick={() => onSelectSymbol(s)}
                    style={{
                      padding: "6px 8px",
                      borderRadius: "var(--radius-row)",
                      cursor: "pointer",
                      fontSize: 12,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      transition: "background 80ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          padding: "1px 4px",
                          borderRadius: 3,
                          background: "#eef2ff",
                          color: "#4f46e5",
                          flexShrink: 0,
                        }}
                      >
                        {s.symbol_type?.[0] || "f"}
                      </span>
                      <span style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {s.name}
                      </span>
                    </div>
                    <span style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>
                      L{s.start_line}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : files.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", fontSize: 12, color: "var(--text-muted)" }}>
            {currentRepo ? "No files indexed yet" : "Select a repository to explore files"}
          </div>
        ) : (
          renderTree(fileTree)
        )}
      </div>
    </div>
  );
}
