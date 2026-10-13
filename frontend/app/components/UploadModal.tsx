"use client";

import React, { useState } from "react";
import {
  Upload,
  GitBranch,
  FolderArchive,
  PlayCircle,
  X,
  RefreshCw,
} from "lucide-react";
import { Repository } from "../types";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadZip: (file: File) => Promise<Repository>;
  onImportGit: (url: string, branch?: string) => Promise<Repository>;
  onLoadSample: () => void;
}

export default function UploadModal({
  isOpen,
  onClose,
  onUploadZip,
  onImportGit,
  onLoadSample,
}: UploadModalProps) {
  const [tab, setTab] = useState<"zip" | "git" | "sample">("zip");
  const [file, setFile] = useState<File | null>(null);
  const [gitUrl, setGitUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleZipSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      await onUploadZip(file);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload ZIP repository");
    } finally {
      setLoading(false);
    }
  };

  const handleGitSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitUrl.trim()) return;
    setError(null);
    setLoading(true);
    try {
      await onImportGit(gitUrl.trim(), branch.trim() || undefined);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to import Git repository");
    } finally {
      setLoading(false);
    }
  };

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
          maxWidth: 500,
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
              <Upload style={{ width: 16, height: 16 }} />
            </div>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                Import Repository
              </h3>
            </div>
          </div>
          <button
            type="button"
            aria-label="Close repository import"
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

        {/* Tab Switcher */}
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
            { id: "zip", label: "Upload ZIP", icon: FolderArchive },
            { id: "git", label: "Git Repository", icon: GitBranch },
            { id: "sample", label: "Sample Demo", icon: PlayCircle },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id as "zip" | "git" | "sample")}
              style={{
                flex: 1,
                padding: "6px 8px",
                borderRadius: 8,
                border: "none",
                fontSize: 11,
                fontWeight: tab === id ? 600 : 500,
                cursor: "pointer",
                background: tab === id ? "#ffffff" : "transparent",
                color: tab === id ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === id ? "0 1px 3px rgba(0,0,0,0.06)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 5,
                transition: "all 100ms",
              }}
            >
              <Icon style={{ width: 13, height: 13 }} />
              <span>{label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ padding: 20 }}>
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

          {tab === "zip" && (
            <form onSubmit={handleZipSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div
                style={{
                  border: "2px dashed var(--border)",
                  borderRadius: 12,
                  padding: 24,
                  textAlign: "center",
                  background: "#fafafa",
                  cursor: "pointer",
                }}
                onClick={() => document.getElementById("zip-input")?.click()}
              >
                <FolderArchive style={{ width: 36, height: 36, color: "var(--blue)", margin: "0 auto 8px" }} />
                <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)", margin: "0 0 4px" }}>
                  {file ? file.name : "Click to select a ZIP archive"}
                </p>
                <p style={{ fontSize: 11, color: "var(--text-muted)", margin: 0 }}>
                  Supports up to 50MB codebases with full tree-sitter AST parsing
                </p>
                <input
                  id="zip-input"
                  type="file"
                  accept=".zip"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  style={{ display: "none" }}
                />
              </div>

              <button
                type="submit"
                disabled={!file || loading}
                style={{
                  padding: "9px 16px",
                  borderRadius: 10,
                  background: "var(--blue)",
                  color: "white",
                  border: "none",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: !file || loading ? "default" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  opacity: !file || loading ? 0.6 : 1,
                  boxShadow: "0 1px 4px rgba(20,115,230,0.25)",
                }}
              >
                {loading && <RefreshCw style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />}
                <span>{loading ? "Uploading & Ingesting..." : "Start Ingestion"}</span>
              </button>
            </form>
          )}

          {tab === "git" && (
            <form onSubmit={handleGitSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", display: "block", marginBottom: 6 }}>
                  Repository HTTPS URL
                </label>
                <input
                  type="text"
                  placeholder="https://github.com/owner/repository.git"
                  value={gitUrl}
                  onChange={(e) => setGitUrl(e.target.value)}
                  style={{
                    width: "100%",
                    height: 38,
                    background: "#ffffff",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "0 12px",
                    fontSize: 13,
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 500, color: "var(--text-primary)", display: "block", marginBottom: 6 }}>
                  Branch (optional)
                </label>
                <input
                  type="text"
                  placeholder="Auto-detect default branch"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  style={{
                    width: "100%",
                    height: 38,
                    background: "#ffffff",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "0 12px",
                    fontSize: 13,
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={!gitUrl.trim() || loading}
                style={{
                  padding: "9px 16px",
                  borderRadius: 10,
                  background: "var(--blue)",
                  color: "white",
                  border: "none",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: !gitUrl.trim() || loading ? "default" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                  opacity: !gitUrl.trim() || loading ? 0.6 : 1,
                  boxShadow: "0 1px 4px rgba(20,115,230,0.25)",
                }}
              >
                {loading && <RefreshCw style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />}
                <span>{loading ? "Cloning & Indexing..." : "Clone & Index"}</span>
              </button>
            </form>
          )}

          {tab === "sample" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14, textAlign: "center", padding: "10px 0" }}>
              <PlayCircle style={{ width: 44, height: 44, color: "var(--blue)", margin: "0 auto" }} />
              <div>
                <h4 style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", margin: "0 0 4px" }}>
                  Sample Python Calculator Codebase
                </h4>
              </div>

              <button
                onClick={() => {
                  onLoadSample();
                  onClose();
                }}
                style={{
                  padding: "10px 16px",
                  borderRadius: 10,
                  background: "var(--blue)",
                  color: "white",
                  border: "none",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  boxShadow: "0 1px 4px rgba(20,115,230,0.25)",
                }}
              >
                Load Sample Calculator Demo
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
