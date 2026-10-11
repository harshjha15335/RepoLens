"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  FileCode,
  Copy,
  Check,
  X,
  Download,
  Sparkles,
  Bug,
  Network,
  Send,
  Code2,
  Layers,
  Settings,
  ChevronDown,
} from "lucide-react";
import { FileContent, CodeContextAttachment, TutorMode } from "../types";

interface CodeViewerProps {
  repoName?: string;
  repoStatus?: string;
  fileContent: FileContent | null;
  loading: boolean;
  highlightRange?: { start: number; end: number; symbol?: string | null };
  openTabs: string[];
  activeFilePath?: string;
  onSelectTab: (path: string) => void;
  onCloseTab: (path: string) => void;
  onAttachContext?: (context: CodeContextAttachment, actionPrompt?: string, mode?: TutorMode) => Promise<boolean>;
  chatLoading?: boolean;
  fontSize?: number;
  onSendMessage?: (question: string) => Promise<boolean>;
  isRepoReady?: boolean;
  centerView?: "code" | "graph" | "retrieval" | "evaluation";
  onCenterViewChange?: (view: "code" | "graph" | "retrieval" | "evaluation") => void;
  onOpenSettings?: () => void;
  onOpenLab?: () => void;
  onOpenEvaluation?: () => void;
}

// Syntax highlighting rules matching the reference colorful IDE screenshot
function highlightSyntax(line: string, language?: string | null): React.ReactNode {
  if (!line) return " ";

  const rules: [RegExp, string][] = [
    // Comments (# or //)
    [/(#.*$|\/\/.*$)/gm, 'var(--syntax-comment)'],
    // Strings (double quotes, single quotes, template literals)
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g, 'var(--syntax-string)'],
    // Keywords (magenta / pink)
    [/\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|in|not|and|or|is|True|False|None|self|async|await|yield|raise|break|continue|pass|lambda|global|nonlocal|function|const|let|var|export|default|interface|type|extends|implements|new|this|super|constructor|public|private|protected|static|readonly|abstract|enum|namespace)\b/g, 'var(--syntax-keyword)'],
    // Function calls / definitions (purple)
    [/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g, 'var(--syntax-function)'],
    // Numbers (orange)
    [/\b(\d+\.?\d*)\b/g, 'var(--syntax-number)'],
    // Decorators (@something)
    [/(@\w+)/g, 'var(--syntax-keyword)'],
  ];

  const spans: { start: number; end: number; color: string }[] = [];

  for (const [regex, color] of rules) {
    let m;
    regex.lastIndex = 0;
    while ((m = regex.exec(line)) !== null) {
      const group = m[1] || m[0];
      const start = m.index + (m[0].indexOf(group));
      spans.push({ start, end: start + group.length, color });
    }
  }

  if (spans.length === 0) return line;

  // Filter overlapping spans
  spans.sort((a, b) => a.start - b.start);
  const usedSpans: { start: number; end: number; color: string }[] = [];
  for (const s of spans) {
    const overlap = usedSpans.some(
      (u) => (s.start >= u.start && s.start < u.end) || (s.end > u.start && s.end <= u.end)
    );
    if (!overlap) usedSpans.push(s);
  }

  const parts: React.ReactNode[] = [];
  let lastEnd = 0;

  for (const span of usedSpans) {
    if (span.start > lastEnd) {
      parts.push(line.slice(lastEnd, span.start));
    }
    parts.push(
      <span key={span.start} style={{ color: span.color }}>
        {line.slice(span.start, span.end)}
      </span>
    );
    lastEnd = span.end;
  }
  if (lastEnd < line.length) {
    parts.push(line.slice(lastEnd));
  }

  return parts.length > 0 ? parts : line;
}

export default function CodeViewer({
  repoName,
  repoStatus,
  fileContent,
  loading,
  highlightRange,
  openTabs,
  activeFilePath,
  onSelectTab,
  onCloseTab,
  onAttachContext,
  chatLoading = false,
  fontSize = 14,
  onSendMessage,
  isRepoReady,
  centerView = "code",
  onCenterViewChange,
  onOpenSettings,
  onOpenLab,
  onOpenEvaluation,
}: CodeViewerProps) {
  const [copied, setCopied] = useState(false);
  const [selectionRange, setSelectionRange] = useState<{ start: number; end: number; text: string; filePath: string } | null>(null);
  const [askInput, setAskInput] = useState("");
  const [layersMenuOpen, setLayersMenuOpen] = useState(false);
  const lineRefs = useRef<{ [line: number]: HTMLDivElement | null }>({});
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to highlighted line range
  useEffect(() => {
    if (highlightRange && highlightRange.start && lineRefs.current[highlightRange.start]) {
      lineRefs.current[highlightRange.start]?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [highlightRange, fileContent]);

  const handleCopy = async () => {
    if (!fileContent) return;
    try {
      await navigator.clipboard.writeText(fileContent.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert("Could not copy the file. Check clipboard access and try again.");
    }
  };

  const handleDownload = () => {
    if (!fileContent) return;
    const blob = new Blob([fileContent.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (activeFilePath || fileContent.path).split(/[\\/]/).pop() || "source.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleMouseUp = () => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !fileContent) {
      setSelectionRange(null);
      return;
    }
    const selectedLine = (node: Node | null) => {
      const element = node instanceof Element ? node : node?.parentElement;
      const line = element?.closest<HTMLElement>("[data-source-line]");
      return line && containerRef.current?.contains(line) ? Number(line.dataset.sourceLine) : null;
    };
    const anchorLine = selectedLine(sel.anchorNode);
    const focusLine = selectedLine(sel.focusNode);
    if (!anchorLine || !focusLine || !sel.toString().trim()) {
      setSelectionRange(null);
      return;
    }
    const start = Math.min(anchorLine, focusLine);
    const end = Math.max(anchorLine, focusLine);
    const text = fileContent.content.split("\n").slice(start - 1, end).join("\n");
    setSelectionRange({ start, end, text, filePath: fileContent.path });
  };

  const handleAskSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!askInput.trim() || !onSendMessage || chatLoading || !isRepoReady) return;
    const question = askInput.trim();
    if (selectionRange && selectionRange.filePath === fileContent?.path && onAttachContext) {
      void onAttachContext({
        file_path: selectionRange.filePath,
        start_line: selectionRange.start,
        end_line: selectionRange.end,
        text: selectionRange.text,
      }, question).then((sent) => {
        if (sent) setAskInput((current) => current === question ? "" : current);
      });
      setSelectionRange(null);
    } else {
      void onSendMessage(question).then((sent) => {
        if (sent) setAskInput((current) => current === question ? "" : current);
      });
    }
  };

  const lines = fileContent?.content ? fileContent.content.split("\n") : [];
  const isReady = repoStatus?.toLowerCase() === "ready";
  const isFailed = repoStatus?.toLowerCase() === "failed";
  const isIndexing = !isReady && !isFailed && repoStatus != null;

  return (
    <div
      ref={containerRef}
      onMouseUp={handleMouseUp}
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        background: "var(--surface)",
        overflow: "hidden",
        position: "relative",
        userSelect: "text",
        height: "100%",
      }}
    >
      {/* ─── 1. CENTER HEADER (MATCHING REFERENCE HOME PAGE / CODING TOOLBAR) ─── */}
      <div
        style={{
          height: 48,
          borderBottom: "1px solid var(--border)",
          padding: "0 18px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
          background: "var(--surface)",
        }}
      >
        {/* Left: Home Page / Repo Name */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
            {repoName || "Home Page"}
          </span>
        </div>

        {/* Center: Segmented Control Toolbar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            background: "#f3f4f6",
            border: "1px solid var(--border)",
            borderRadius: 999,
            padding: "3px 5px",
          }}
        >
          {/* </> icon */}
          <button
            onClick={() => onCenterViewChange && onCenterViewChange("code")}
            title="Code Viewer"
            style={{
              padding: "4px 8px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              color: centerView === "code" ? "var(--text-primary)" : "var(--text-muted)",
              transition: "all 120ms",
            }}
          >
            <Code2 style={{ width: 14, height: 14 }} />
          </button>

          {/* </> Coding vivid blue pill */}
          <button
            onClick={() => onCenterViewChange && onCenterViewChange("code")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 14px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 600,
              background: centerView === "code" ? "var(--blue)" : "transparent",
              color: centerView === "code" ? "white" : "var(--text-secondary)",
              boxShadow: centerView === "code" ? "0 2px 6px rgba(20,115,230,0.3)" : "none",
              transition: "all 120ms",
            }}
          >
            <Code2 style={{ width: 13, height: 13 }} />
            <span>Coding</span>
          </button>

          {/* Layers icon (Code Intelligence) */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setLayersMenuOpen(!layersMenuOpen)}
              title="Code Intelligence & Layers"
              style={{
                padding: "4px 8px",
                borderRadius: 999,
                border: "none",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: centerView === "graph" ? "var(--surface-selected)" : "transparent",
                color: centerView === "graph" ? "var(--blue)" : "var(--text-secondary)",
                transition: "all 120ms",
              }}
            >
              <Layers style={{ width: 14, height: 14 }} />
            </button>

            {layersMenuOpen && (
              <>
                <div
                  style={{ position: "fixed", inset: 0, zIndex: 60 }}
                  onClick={() => setLayersMenuOpen(false)}
                />
                <div
                  style={{
                    position: "absolute",
                    top: "100%",
                    left: "50%",
                    transform: "translateX(-50%)",
                    marginTop: 8,
                    width: 200,
                    background: "var(--surface)",
                    borderRadius: 12,
                    border: "1px solid var(--border)",
                    boxShadow: "0 12px 36px rgba(0,0,0,0.12)",
                    padding: 4,
                    zIndex: 61,
                  }}
                >
                  <button
                    onClick={() => {
                      setLayersMenuOpen(false);
                      onCenterViewChange && onCenterViewChange("graph");
                    }}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      border: "none",
                      background: centerView === "graph" ? "var(--surface-selected)" : "transparent",
                      borderRadius: 8,
                      cursor: "pointer",
                      fontSize: 12,
                      color: "var(--text-primary)",
                      textAlign: "left",
                    }}
                  >
                    <Network style={{ width: 14, height: 14, color: "var(--blue)" }} />
                    <span>Knowledge Graph</span>
                  </button>

                  <button
                    onClick={() => {
                      setLayersMenuOpen(false);
                      onOpenLab && onOpenLab();
                    }}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      border: "none",
                      background: "transparent",
                      borderRadius: 8,
                      cursor: "pointer",
                      fontSize: 12,
                      color: "var(--text-primary)",
                      textAlign: "left",
                    }}
                  >
                    <Layers style={{ width: 14, height: 14, color: "var(--syntax-variable)" }} />
                    <span>Retrieval Inspector</span>
                  </button>

                  <button
                    onClick={() => {
                      setLayersMenuOpen(false);
                      onOpenEvaluation && onOpenEvaluation();
                    }}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      border: "none",
                      background: "transparent",
                      borderRadius: 8,
                      cursor: "pointer",
                      fontSize: 12,
                      color: "var(--text-primary)",
                      textAlign: "left",
                    }}
                  >
                    <Sparkles style={{ width: 14, height: 14, color: "var(--orange)" }} />
                    <span>Evaluation Lab</span>
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Settings icon */}
          <button
            onClick={onOpenSettings}
            title="Settings"
            style={{
              padding: "4px 8px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              color: "var(--text-secondary)",
              transition: "all 120ms",
            }}
          >
            <Settings style={{ width: 14, height: 14 }} />
          </button>
        </div>

        {/* Right: Status dot */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--text-secondary)" }}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: isReady ? "var(--green)" : isIndexing ? "var(--orange)" : isFailed ? "var(--red)" : "var(--text-muted)",
              display: "inline-block",
            }}
            className={isIndexing ? "pulse-ring" : ""}
          />
          <span>
            {isReady ? "Ready" : isIndexing ? "Indexing..." : isFailed ? "Failed" : "Idle"}
          </span>
        </div>
      </div>

      {/* ─── 2. FILE TAB BAR ─── */}
      <div
        style={{
          height: 44,
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          padding: "0 14px",
          overflow: "hidden",
          flexShrink: 0,
          background: "var(--surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", flex: 1, overflow: "hidden" }}>
          {openTabs.length === 0 ? (
            <div style={{ fontSize: 12, color: "var(--text-muted)" }}>No tabs open</div>
          ) : (
            openTabs.map((tabPath) => {
              const isActive = tabPath === activeFilePath;
              const tabName = tabPath.split("/").pop() || tabPath;
              return (
                <div
                  key={tabPath}
                  onClick={() => onSelectTab(tabPath)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "0 12px",
                    height: 44,
                    fontSize: 13,
                    fontWeight: isActive ? 500 : 400,
                    color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                    borderBottom: isActive ? "2px solid var(--blue)" : "2px solid transparent",
                    cursor: "pointer",
                    transition: "all 100ms",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  <span>{tabName}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onCloseTab(tabPath);
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      display: "flex",
                      padding: 2,
                      borderRadius: 4,
                      color: "var(--text-muted)",
                      transition: "color 80ms",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                    onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                  >
                    <X style={{ width: 12, height: 12 }} />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* File Actions on Right (Code icon, Copy, Download) */}
        {fileContent && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <button
              onClick={handleCopy}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: 12,
                color: "var(--text-secondary)",
                padding: "4px 6px",
                borderRadius: 6,
                transition: "all 80ms",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
              title="Copy code"
            >
              {copied ? (
                <Check style={{ width: 14, height: 14, color: "var(--green)" }} />
              ) : (
                <Copy style={{ width: 14, height: 14 }} />
              )}
            </button>

            <button
              onClick={handleDownload}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 500,
                color: "var(--text-primary)",
                padding: "4px 6px",
                borderRadius: 6,
                transition: "all 80ms",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--blue)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
              title="Download file"
            >
              <Download style={{ width: 14, height: 14 }} />
              <span>Download</span>
            </button>
          </div>
        )}
      </div>

      {/* ─── 3. SELECTION ACTION BAR ─── */}
      {selectionRange && selectionRange.filePath === fileContent?.path && onAttachContext && (
        <div
          className="fade-in"
          onMouseDown={(event) => event.preventDefault()}
          onMouseUp={(event) => event.stopPropagation()}
          style={{
            position: "absolute",
            top: 102,
            right: 20,
            zIndex: 30,
            padding: 4,
            borderRadius: 12,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-floating)",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <span
            style={{
              fontSize: 11,
              fontFamily: "var(--font-mono)",
              color: "var(--text-muted)",
              padding: "0 8px",
            }}
          >
            L{selectionRange.start}-L{selectionRange.end}
          </span>
          {[
            {
              label: "Explain",
              icon: Sparkles,
              prompt: `Explain lines ${selectionRange.start}-${selectionRange.end} in ${fileContent?.path}.`,
            },
            {
              label: "Debug",
              icon: Bug,
              prompt: `Debug potential issues in lines ${selectionRange.start}-${selectionRange.end} of ${fileContent?.path}.`,
            },
            {
              label: "Trace",
              icon: Network,
              prompt: `Trace execution connections for lines ${selectionRange.start}-${selectionRange.end} in ${fileContent?.path}.`,
            },
          ].map(({ label, icon: Icon, prompt }) => (
            <button
              key={label}
              disabled={chatLoading || !isReady}
              onClick={() => {
                if (fileContent) {
                  onAttachContext(
                    {
                      file_path: fileContent.path,
                      start_line: selectionRange.start,
                      end_line: selectionRange.end,
                      text: selectionRange.text,
                      action: label === "Explain" ? "explain" : label === "Debug" ? "debug" : "trace",
                    },
                    prompt,
                    label === "Explain" ? undefined : "debug"
                  );
                }
                setSelectionRange(null);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "5px 10px",
                borderRadius: 8,
                fontSize: 11,
                fontWeight: 500,
                cursor: chatLoading || !isReady ? "not-allowed" : "pointer",
                opacity: chatLoading || !isReady ? 0.5 : 1,
                background: label === "Explain" ? "var(--blue)" : "var(--surface-hover)",
                color: label === "Explain" ? "white" : "var(--text-primary)",
                border: label === "Explain" ? "none" : "1px solid var(--border)",
                transition: "all 100ms",
              }}
            >
              <Icon style={{ width: 12, height: 12 }} />
              {label}
            </button>
          ))}
        </div>
      )}

      {/* ─── 4. CODE VIEWER PANE ─── */}
      {loading ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              border: "2px solid var(--blue)",
              borderTopColor: "transparent",
              borderRadius: "50%",
            }}
            className="spinner"
          />
          <p style={{ fontSize: 12, marginTop: 12 }}>Loading source file...</p>
        </div>
      ) : !fileContent ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-muted)",
            textAlign: "center",
            padding: 32,
          }}
        >
          <FileCode style={{ width: 44, height: 44, color: "var(--border)", marginBottom: 12 }} />
          <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-secondary)", margin: "0 0 6px" }}>
            No File Selected
          </h3>
          <p style={{ fontSize: 12, maxWidth: 320, lineHeight: 1.5 }}>
            Select a file from the explorer on the left or click a citation chip to view source code.
          </p>
        </div>
      ) : (
        <div
          style={{
            flex: 1,
            overflow: "auto",
            fontFamily: "var(--font-mono)",
            fontSize,
            lineHeight: 1.8,
            padding: "12px 0 80px 0",
          }}
        >
          <div style={{ minWidth: "fit-content" }}>
            {lines.map((line, index) => {
              const lineNumber = index + 1;
              const isHighlighted =
                highlightRange &&
                lineNumber >= highlightRange.start &&
                lineNumber <= highlightRange.end;

              return (
                <div
                  key={lineNumber}
                  data-source-line={lineNumber}
                  ref={(el) => {
                    lineRefs.current[lineNumber] = el;
                  }}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    transition: "background 120ms",
                    background: isHighlighted ? "rgba(20, 115, 230, 0.08)" : "transparent",
                    borderLeft: isHighlighted ? "3px solid var(--blue)" : "3px solid transparent",
                  }}
                  className={isHighlighted ? "citation-highlight-pulse" : ""}
                >
                  {/* Line Number */}
                  <span
                    style={{
                      width: 52,
                      textAlign: "right",
                      paddingRight: 18,
                      flexShrink: 0,
                      userSelect: "none",
                      color: isHighlighted ? "var(--blue)" : "#a8a8a8",
                      fontWeight: isHighlighted ? 600 : 400,
                    }}
                  >
                    {lineNumber}
                  </span>

                  {/* Code Line Content */}
                  <span
                    style={{
                      paddingLeft: 8,
                      paddingRight: 32,
                      whiteSpace: "pre",
                      color: "var(--text-primary)",
                    }}
                  >
                    {highlightSyntax(line, fileContent.language)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── 5. FLOATING AI COMPOSER (MATCHING REFERENCE "Ask a follow-up...") ─── */}
      <div
        style={{
          position: "absolute",
          bottom: 18,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 25,
          width: "min(440px, calc(100% - 36px))",
        }}
      >
        <form
          onSubmit={handleAskSubmit}
          style={{
            display: "flex",
            alignItems: "center",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 999,
            padding: "4px 5px 4px 18px",
            boxShadow: "0 10px 30px rgba(20, 30, 50, 0.10)",
            transition: "border-color 150ms",
          }}
        >
          <input
            type="text"
            value={askInput}
            onChange={(e) => setAskInput(e.target.value)}
            disabled={!isRepoReady || chatLoading}
            placeholder={
              chatLoading
                ? "Waiting for response..."
                : !isRepoReady
                ? "Waiting for indexing..."
                : selectionRange
                ? `Ask about L${selectionRange.start}-${selectionRange.end}...`
                : "Ask a follow-up..."
            }
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: 13,
              color: "var(--text-primary)",
              fontFamily: "var(--font-sans)",
            }}
          />
          <button
            type="submit"
            disabled={!askInput.trim() || !isRepoReady || chatLoading}
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: askInput.trim() ? "var(--blue)" : "#e5e7eb",
              border: "none",
              cursor: askInput.trim() ? "pointer" : "default",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "background 120ms",
            }}
          >
            <Send style={{ width: 12, height: 12, color: askInput.trim() ? "white" : "#9ca3af" }} />
          </button>
        </form>
      </div>
    </div>
  );
}
