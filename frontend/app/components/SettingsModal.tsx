"use client";

import React, { useState } from "react";
import {
  Settings,
  X,
  Moon,
  Sun,
  Cpu,
  Layers,
  ShieldCheck,
  Code2,
  Sliders,
  Check,
} from "lucide-react";
import { Theme, TutorMode } from "../types";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: Theme;
  onToggleTheme: () => void;
  defaultTutorMode: TutorMode;
  onSetDefaultTutorMode: (mode: TutorMode) => void;
  fontSize: number;
  onSetFontSize: (size: number) => void;
}

export default function SettingsModal({
  isOpen,
  onClose,
  theme,
  onToggleTheme,
  defaultTutorMode,
  onSetDefaultTutorMode,
  fontSize,
  onSetFontSize,
}: SettingsModalProps) {
  const [tab, setTab] = useState<"general" | "ai" | "retrieval" | "privacy">("general");

  if (!isOpen) return null;

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
          maxWidth: 540,
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
                background: "var(--blue-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--blue)",
              }}
            >
              <Settings style={{ width: 16, height: 16 }} />
            </div>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Settings & Preferences
              </h3>
              <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "2px 0 0" }}>
                Configure CodeMentor-RAG environment
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
          >
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        {/* Tab Buttons */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid var(--border)",
            background: "#fafafa",
            padding: "6px 12px",
            gap: 6,
          }}
        >
          {[
            { id: "general", label: "General & Display" },
            { id: "ai", label: "AI & Providers" },
            { id: "retrieval", label: "Retrieval" },
            { id: "privacy", label: "Privacy & Sandbox" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as any)}
              style={{
                flex: 1,
                padding: "6px 8px",
                borderRadius: 8,
                border: "none",
                fontSize: 11,
                fontWeight: tab === t.id ? 600 : 500,
                cursor: "pointer",
                background: tab === t.id ? "#ffffff" : "transparent",
                color: tab === t.id ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === t.id ? "0 1px 3px rgba(0,0,0,0.06)" : "none",
                transition: "all 100ms",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
          {tab === "general" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Font Size */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", display: "block" }}>
                    Editor Font Size
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    Controls font size in the center Code Viewer
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <button
                    onClick={() => onSetFontSize(Math.max(11, fontSize - 1))}
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      background: "#f3f4f6",
                      border: "1px solid var(--border)",
                      cursor: "pointer",
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    -
                  </button>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, minWidth: 28, textAlign: "center" }}>
                    {fontSize}px
                  </span>
                  <button
                    onClick={() => onSetFontSize(Math.min(20, fontSize + 1))}
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      background: "#f3f4f6",
                      border: "1px solid var(--border)",
                      cursor: "pointer",
                      fontSize: 14,
                      fontWeight: 600,
                    }}
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Default Tutor Mode */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", display: "block" }}>
                    Default Tutor Mode
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    Initial prompt framing for answering codebase questions
                  </span>
                </div>
                <select
                  value={defaultTutorMode}
                  onChange={(e) => onSetDefaultTutorMode(e.target.value as any)}
                  style={{
                    height: 32,
                    background: "#ffffff",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "0 10px",
                    fontSize: 12,
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                >
                  <option value="beginner">Beginner</option>
                  <option value="developer">Developer</option>
                  <option value="interview">Interview</option>
                  <option value="debug">Debug</option>
                </select>
              </div>
            </div>
          )}

          {tab === "ai" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 12 }}>
              <div style={{ padding: 12, borderRadius: 10, background: "#f8fafc", border: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: 2 }}>
                  Active LLM Provider
                </span>
                <span style={{ color: "var(--text-secondary)" }}>
                  Gemini API / Groq / OpenAI (configured via backend .env)
                </span>
              </div>
              <div style={{ padding: 12, borderRadius: 10, background: "#f8fafc", border: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: 2 }}>
                  Embeddings Provider
                </span>
                <span style={{ color: "var(--text-secondary)" }}>
                  Local FastEmbed / Sentence-Transformers (all-MiniLM-L6-v2)
                </span>
              </div>
            </div>
          )}

          {tab === "retrieval" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
              <div style={{ padding: 12, borderRadius: 10, background: "#f8fafc", border: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: 2 }}>
                  Hybrid Fusion Strategy
                </span>
                <span style={{ color: "var(--text-secondary)" }}>
                  Reciprocal Rank Fusion (RRF) with k=60 combining FAISS cosine and Rank-BM25
                </span>
              </div>
              <div style={{ padding: 12, borderRadius: 10, background: "#f8fafc", border: "1px solid var(--border)" }}>
                <span style={{ fontWeight: 600, color: "var(--text-primary)", display: "block", marginBottom: 2 }}>
                  Knowledge Graph Expansion
                </span>
                <span style={{ color: "var(--text-secondary)" }}>
                  1-hop and 2-hop symbol traversals for caller/callee and inheritance chains
                </span>
              </div>
            </div>
          )}

          {tab === "privacy" && (
            <div style={{ padding: 14, borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", fontSize: 12, color: "#166534" }}>
              <span style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                Local Sandboxed Execution
              </span>
              Uploaded repositories are analyzed locally within your workspace storage. No proprietary source code is stored on external third-party database servers.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
