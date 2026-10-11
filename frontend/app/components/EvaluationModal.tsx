"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  BarChart3,
  Play,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  X,
  Target,
  Zap,
  Check,
  TrendingUp,
  FileCheck,
  Clock,
} from "lucide-react";
import { EvaluationRun, EvaluationMetricResult } from "../types";
import { api } from "../lib/api";

interface EvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
  repositoryId: string;
}

export default function EvaluationModal({
  isOpen,
  onClose,
  repositoryId,
}: EvaluationModalProps) {
  const [running, setRunning] = useState(false);
  const [evalRun, setEvalRun] = useState<EvaluationRun | null>(null);
  const [activeStrategy, setActiveStrategy] = useState<string>("hybrid_rrf");
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRun = useRef(0);

  useEffect(() => {
    return () => {
      activeRun.current += 1;
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [repositoryId]);

  if (!isOpen) return null;

  const handleStartEvaluation = async () => {
    const runToken = ++activeRun.current;
    if (pollTimer.current) clearTimeout(pollTimer.current);
    setError(null);
    setRunning(true);
    setEvalRun(null);
    try {
      const run = await api.runEvaluation({
        repositoryId,
        strategies: ["bm25", "dense", "hybrid_rrf", "graph_expansion"],
      });
      if (activeRun.current !== runToken) return;
      setEvalRun(run);

      const startedAt = Date.now();
      const poll = async () => {
        if (activeRun.current !== runToken) return;
        if (Date.now() - startedAt > 120_000) {
          setRunning(false);
          setError("Evaluation has not finished after two minutes. Check the backend log; the job may still be running.");
          return;
        }
        try {
          const updated = await api.getEvaluation(run.id);
          if (activeRun.current !== runToken) return;
          setEvalRun(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            setRunning(false);
            if (updated.status === "failed") {
              setError(updated.error_message || "Evaluation failed. Check the backend log for details.");
            }
            if (updated.metrics && updated.metrics.length > 0) {
              setActiveStrategy(updated.metrics[0].strategy);
            }
            return;
          }
        } catch (e) {
          if (activeRun.current !== runToken) return;
          setRunning(false);
          setError(e instanceof Error ? e.message : "Could not check evaluation status");
          return;
        }
        pollTimer.current = setTimeout(poll, 1500);
      };
      pollTimer.current = setTimeout(poll, 1500);
    } catch (err: unknown) {
      if (activeRun.current !== runToken) return;
      setError(err instanceof Error ? err.message : "Failed to start evaluation");
      setRunning(false);
    }
  };

  const currentMetrics = evalRun?.metrics?.find((m) => m.strategy === activeStrategy);

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
        {/* Header */}
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
                background: "var(--green-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--green)",
              }}
            >
              <BarChart3 style={{ width: 16, height: 16 }} />
            </div>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                RAG Retrieval Evaluation Benchmarks
              </h3>
            </div>
          </div>

          <button
            type="button"
            aria-label="Close evaluation"
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

        {/* Action Controls */}
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid var(--border)",
            background: "#fafafa",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <button
            onClick={handleStartEvaluation}
            disabled={running}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 16px",
              borderRadius: 9,
              background: "var(--blue)",
              color: "white",
              border: "none",
              fontSize: 12,
              fontWeight: 600,
              cursor: running ? "default" : "pointer",
              boxShadow: "0 1px 4px rgba(20,115,230,0.25)",
              opacity: running ? 0.6 : 1,
            }}
          >
            {running ? (
              <>
                <RefreshCw style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} />
                <span>Running Benchmark...</span>
              </>
            ) : (
              <>
                <Play style={{ width: 13, height: 13, fill: "white" }} />
                <span>Run Full Evaluation</span>
              </>
            )}
          </button>
        </div>

        {/* Content Area */}
        <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
          {error && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 8,
                background: "var(--red-light)",
                border: "1px solid rgba(239, 68, 68, 0.2)",
                color: "var(--red)",
                fontSize: 12,
                marginBottom: 16,
              }}
            >
              {error}
            </div>
          )}

          {!evalRun ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              <BarChart3 style={{ width: 36, height: 36, color: "var(--border)", margin: "0 auto 10px" }} />
              <span>Click &quot;Run Full Evaluation&quot; to benchmark all retrieval strategies on this repository.</span>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Benchmark Table */}
              {running && (
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                  Evaluating each retrieval strategy. Results will appear when the run finishes.
                </div>
              )}
              <div
                style={{
                  borderRadius: 12,
                  border: "1px solid var(--border)",
                  overflow: "hidden",
                }}
              >
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "1px solid var(--border)", textAlign: "left" }}>
                      <th style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-secondary)" }}>Strategy</th>
                      <th style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-secondary)" }}>Recall@5</th>
                      <th style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-secondary)" }}>Recall@10</th>
                      <th style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-secondary)" }}>MRR</th>
                      <th style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-secondary)" }}>Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(evalRun.metrics || []).map((m: EvaluationMetricResult) => (
                      <tr
                        key={m.strategy}
                        onClick={() => setActiveStrategy(m.strategy)}
                        style={{
                          borderBottom: "1px solid var(--border)",
                          cursor: "pointer",
                          background: activeStrategy === m.strategy ? "var(--surface-selected)" : "#ffffff",
                          transition: "background 80ms",
                        }}
                      >
                        <td style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                          {m.strategy}
                        </td>
                        <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                          {(m.recall_at_5 * 100).toFixed(1)}%
                        </td>
                        <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                          {(m.recall_at_10 * 100).toFixed(1)}%
                        </td>
                        <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", color: "var(--blue)", fontWeight: 600 }}>
                          {m.mrr.toFixed(3)}
                        </td>
                        <td style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", color: "var(--green)", fontWeight: 500 }}>
                          {(m.avg_latency_ms || 0).toFixed(1)} ms
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Strategy Details */}
              {currentMetrics && (
                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "#f8fafc",
                    border: "1px solid var(--border)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <h4 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                      Diagnostic Details: <span style={{ color: "var(--blue)" }}>{currentMetrics.strategy}</span>
                    </h4>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      Queries evaluated: {currentMetrics.results?.length || 0}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                    <div style={{ padding: 10, borderRadius: 8, background: "#ffffff", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>Recall@5</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                        {(currentMetrics.recall_at_5 * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div style={{ padding: 10, borderRadius: 8, background: "#ffffff", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>Recall@10</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                        {(currentMetrics.recall_at_10 * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div style={{ padding: 10, borderRadius: 8, background: "#ffffff", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>MRR</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--blue)", fontFamily: "var(--font-mono)" }}>
                        {currentMetrics.mrr.toFixed(3)}
                      </div>
                    </div>
                    <div style={{ padding: 10, borderRadius: 8, background: "#ffffff", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>Latency</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "var(--green)", fontFamily: "var(--font-mono)" }}>
                        {(currentMetrics.avg_latency_ms || 0).toFixed(1)} ms
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
