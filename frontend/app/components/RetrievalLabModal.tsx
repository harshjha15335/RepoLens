"use client";

import React, { useState } from "react";
import {
  Search,
  Sliders,
  Layers,
  Sparkles,
  Clock,
  X,
  FileCode,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Cpu,
  CheckCircle2,
} from "lucide-react";
import { RetrievedChunk, Citation } from "../types";
import { api } from "../lib/api";

interface RetrievalLabModalProps {
  isOpen: boolean;
  onClose: () => void;
  repositoryId: string;
  onInspectChunk: (citation: Citation) => void;
}

export default function RetrievalLabModal({
  isOpen,
  onClose,
  repositoryId,
  onInspectChunk,
}: RetrievalLabModalProps) {
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState("hybrid_rrf");
  const [topK, setTopK] = useState(8);
  const [enableGraph, setEnableGraph] = useState(true);
  const [enableMmr, setEnableMmr] = useState(true);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<{
    query: string;
    intent?: string;
    chunks: RetrievedChunk[];
    latency_ms: number;
    strategy: string;
  } | null>(null);

  if (!isOpen) return null;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    try {
      const data = await api.searchRetrieval({
        repositoryId,
        query: query.trim(),
        strategy,
        topK,
        enableGraphExpansion: enableGraph,
        enableMmr,
      });
      setResults(data);
    } catch (err: any) {
      alert(err.message || "Retrieval search failed");
    } finally {
      setLoading(false);
    }
  };

  const strategies = [
    { id: "hybrid_rrf", label: "Hybrid RRF" },
    { id: "dense", label: "Dense FAISS" },
    { id: "bm25", label: "Lexical BM25" },
    { id: "graph_expansion", label: "Graph Expansion" },
  ];

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(10, 25, 45, 0.4)",
        backdropFilter: "blur(4px)",
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="slide-up"
        style={{
          width: "100%",
          maxWidth: 860,
          maxHeight: "88vh",
          borderRadius: 20,
          background: "#ffffff",
          border: "1px solid var(--border)",
          boxShadow: "0 24px 60px rgba(0, 0, 0, 0.15)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* ─── Header ─── */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#ffffff",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "var(--blue-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--blue)",
              }}
            >
              <Search style={{ width: 16, height: 16 }} />
            </div>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Retrieval Pipeline Lab & Inspector
              </h3>
              <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "2px 0 0" }}>
                Direct benchmark & diagnostics for dense, lexical BM25, and graph-expanded retrieval
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 6,
              borderRadius: 6,
              color: "var(--text-muted)",
              display: "flex",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        {/* ─── Query Controls ─── */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            background: "#fafafa",
          }}
        >
          <form onSubmit={handleSearch} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ position: "relative" }}>
              <Search
                style={{
                  width: 15,
                  height: 15,
                  color: "var(--text-muted)",
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />
              <input
                type="text"
                placeholder="Enter query to test retrieval (e.g. 'division by zero', 'parser tokenizer', 'operation history')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                  width: "100%",
                  height: 40,
                  background: "#ffffff",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  paddingLeft: 36,
                  paddingRight: 100,
                  fontSize: 13,
                  color: "var(--text-primary)",
                  outline: "none",
                  transition: "border-color 120ms",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--blue)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
              />
              <button
                type="submit"
                disabled={!query.trim() || loading}
                style={{
                  position: "absolute",
                  right: 5,
                  top: 5,
                  height: 30,
                  padding: "0 14px",
                  borderRadius: 8,
                  background: "var(--blue)",
                  color: "white",
                  border: "none",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: !query.trim() || loading ? "default" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  opacity: !query.trim() || loading ? 0.6 : 1,
                  boxShadow: "0 1px 4px rgba(20,115,230,0.25)",
                }}
              >
                {loading ? (
                  <RefreshCw style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} />
                ) : (
                  <ArrowRight style={{ width: 13, height: 13 }} />
                )}
                <span>Search</span>
              </button>
            </div>

            {/* Strategy Selectors */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>
                  Strategy:
                </span>
                <div style={{ display: "flex", background: "#f3f4f6", padding: 2, borderRadius: 8, border: "1px solid var(--border)" }}>
                  {strategies.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setStrategy(s.id)}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 6,
                        border: "none",
                        fontSize: 11,
                        fontWeight: strategy === s.id ? 600 : 400,
                        cursor: "pointer",
                        background: strategy === s.id ? "var(--blue)" : "transparent",
                        color: strategy === s.id ? "white" : "var(--text-secondary)",
                        transition: "all 100ms",
                      }}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer", color: "var(--text-primary)" }}>
                  <input
                    type="checkbox"
                    checked={enableMmr}
                    onChange={(e) => setEnableMmr(e.target.checked)}
                    style={{ accentColor: "var(--blue)", cursor: "pointer" }}
                  />
                  <span>MMR Diversity</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer", color: "var(--text-primary)" }}>
                  <input
                    type="checkbox"
                    checked={enableGraph}
                    onChange={(e) => setEnableGraph(e.target.checked)}
                    style={{ accentColor: "var(--blue)", cursor: "pointer" }}
                  />
                  <span>Graph 1-Hop Expansion</span>
                </label>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>Top-K:</span>
                  <select
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    style={{
                      height: 28,
                      background: "#ffffff",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      padding: "0 6px",
                      fontSize: 12,
                      color: "var(--text-primary)",
                      outline: "none",
                    }}
                  >
                    <option value={4}>4</option>
                    <option value={8}>8</option>
                    <option value={12}>12</option>
                    <option value={16}>16</option>
                  </select>
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* ─── Results Area ─── */}
        <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              <RefreshCw style={{ width: 24, height: 24, animation: "spin 1s linear infinite", color: "var(--blue)", margin: "0 auto 10px" }} />
              <span>Executing retrieval pipeline...</span>
            </div>
          ) : !results ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              <Layers style={{ width: 36, height: 36, color: "var(--border)", margin: "0 auto 10px" }} />
              <span>Type a query above to benchmark and inspect chunks in real time.</span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Meta Diagnostics */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "#f8fafc",
                  border: "1px solid var(--border)",
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", gap: 14 }}>
                  <span>
                    Strategy: <strong style={{ color: "var(--blue)" }}>{results.strategy}</strong>
                  </span>
                  {results.intent && (
                    <span>
                      Detected Intent: <strong style={{ color: "var(--text-primary)" }}>{results.intent}</strong>
                    </span>
                  )}
                  <span>
                    Retrieved: <strong>{results.chunks.length} chunks</strong>
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--green)", fontWeight: 600 }}>
                  <Clock style={{ width: 13, height: 13 }} />
                  <span>{results.latency_ms.toFixed(1)} ms</span>
                </div>
              </div>

              {/* Chunks List */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {results.chunks.map((chunk, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: 14,
                      borderRadius: 12,
                      background: "#ffffff",
                      border: "1px solid var(--border)",
                      boxShadow: "0 1px 4px rgba(0,0,0,0.03)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            fontFamily: "var(--font-mono)",
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: "var(--blue-light)",
                            color: "var(--blue)",
                          }}
                        >
                          #{idx + 1}
                        </span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>
                          {chunk.file_path}
                        </span>
                        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                          L{chunk.start_line}-{chunk.end_line}
                        </span>
                        {chunk.symbol_name && (
                          <span
                            style={{
                              fontSize: 10,
                              fontFamily: "var(--font-mono)",
                              padding: "1px 6px",
                              borderRadius: 4,
                              background: "#f3e8ff",
                              color: "#7e22ce",
                            }}
                          >
                            {chunk.symbol_name}
                          </span>
                        )}
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--green)", fontWeight: 600 }}>
                          Score: {chunk.score.toFixed(4)}
                        </span>
                        <button
                          onClick={() => {
                            onInspectChunk({
                              file_path: chunk.file_path,
                              start_line: chunk.start_line,
                              end_line: chunk.end_line,
                              symbol_name: chunk.symbol_name,
                            });
                            onClose();
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "4px 8px",
                            borderRadius: 6,
                            background: "#f3f4f6",
                            border: "1px solid var(--border)",
                            fontSize: 11,
                            fontWeight: 500,
                            color: "var(--text-primary)",
                            cursor: "pointer",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "#e5e7eb")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "#f3f4f6")}
                        >
                          <FileCode style={{ width: 12, height: 12 }} />
                          <span>View Code</span>
                        </button>
                      </div>
                    </div>

                    <pre
                      style={{
                        padding: 10,
                        borderRadius: 8,
                        background: "#fafafa",
                        border: "1px solid #f0f0f0",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        lineHeight: 1.5,
                        margin: 0,
                        overflowX: "auto",
                        color: "var(--text-primary)",
                        maxHeight: 140,
                      }}
                    >
                      <code>{chunk.content}</code>
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
