"use client";

import React, { useState } from "react";
import {
  Upload,
  ChevronDown,
  Code2,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
  Trash2,
  Layers,
  Settings,
  Command,
  Search,
} from "lucide-react";
import { Repository, TutorMode } from "../types";

interface HeaderProps {
  repositories: Repository[];
  currentRepo: Repository | null;
  onSelectRepo: (repo: Repository) => void;
  onOpenUpload: () => void;
  onLoadSample: () => void;
  onRefresh: () => void;
  onDeleteRepo: (repoId: string) => void;
  onReindex: () => void;
  isPolling: boolean;
  tutorMode: TutorMode;
  onTutorModeChange: (mode: TutorMode) => void;
}

const TUTOR_MODES: { id: TutorMode; label: string }[] = [
  { id: "beginner", label: "Beginner" },
  { id: "developer", label: "Developer" },
  { id: "interview", label: "Interview" },
  { id: "debug", label: "Debug" },
];

export default function Header({
  repositories,
  currentRepo,
  onSelectRepo,
  onOpenUpload,
  onLoadSample,
  onRefresh,
  onDeleteRepo,
  onReindex,
  isPolling,
  tutorMode,
  onTutorModeChange,
}: HeaderProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [modeDropdownOpen, setModeDropdownOpen] = useState(false);

  const repoStatus = currentRepo?.status?.toLowerCase();
  const isReady = repoStatus === "ready";
  const isFailed = repoStatus === "failed";
  const isIndexing = currentRepo != null && !["ready", "failed", "pending"].includes(repoStatus || "");

  const modeLabel = TUTOR_MODES.find((m) => m.id === tutorMode)?.label || "Developer";

  return (
    <header className="app-header" style={{
      height: 52,
      borderBottom: '1px solid var(--border)',
      background: 'var(--surface)',
      padding: '0 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexShrink: 0,
      borderRadius: 'var(--radius-window) var(--radius-window) 0 0',
    }}>
      {/* Left: Breadcrumb Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Brand Mark */}
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: 'linear-gradient(135deg, #1473e6 0%, #0ea5e9 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
          </svg>
        </div>

        {/* Breadcrumbs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>CodeMentor</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 300 }}>/</span>
          <span>Repositories</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 300 }}>/</span>

          {/* Repository Selector */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 500, color: 'var(--text-primary)',
                padding: '2px 4px', borderRadius: 6,
              }}
            >
              <span>{currentRepo ? currentRepo.name : "Select Repository"}</span>
              <ChevronDown style={{ width: 14, height: 14, color: 'var(--text-muted)' }} />
            </button>

            {dropdownOpen && (
              <>
                <div
                  style={{ position: 'fixed', inset: 0, zIndex: 50 }}
                  onClick={() => setDropdownOpen(false)}
                />
                <div style={{
                  position: 'absolute', left: 0, top: '100%', marginTop: 8,
                  width: 280, background: 'var(--surface)',
                  borderRadius: 14, border: '1px solid var(--border)',
                  boxShadow: '0 16px 50px rgba(0,0,0,0.12)',
                  padding: 6, zIndex: 51,
                }}>
                  <div style={{
                    padding: '8px 10px', fontSize: 11, fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                    color: 'var(--text-muted)', borderBottom: '1px solid var(--border)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <span>Repositories ({repositories.length})</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); onRefresh(); }}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        padding: 2, color: 'var(--text-muted)', display: 'flex',
                      }}
                      title="Refresh"
                    >
                      <RefreshCw style={{
                        width: 12, height: 12,
                        animation: isPolling ? 'spin 1s linear infinite' : 'none',
                      }} />
                    </button>
                  </div>

                  <div style={{ maxHeight: 240, overflowY: 'auto', padding: '4px 0' }}>
                    {repositories.length === 0 ? (
                      <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
                        No repositories imported yet.
                      </div>
                    ) : (
                      repositories.map((repo) => (
                        <div
                          key={repo.id}
                          onClick={() => { onSelectRepo(repo); setDropdownOpen(false); }}
                          style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                            fontSize: 12,
                            background: currentRepo?.id === repo.id ? 'var(--surface-selected)' : 'transparent',
                            transition: 'background 120ms',
                          }}
                          onMouseEnter={(e) => {
                            if (currentRepo?.id !== repo.id)
                              e.currentTarget.style.background = 'var(--surface-hover)';
                          }}
                          onMouseLeave={(e) => {
                            if (currentRepo?.id !== repo.id)
                              e.currentTarget.style.background = 'transparent';
                          }}
                        >
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                              {repo.name}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                              {repo.stats?.files || 0} files · {repo.stats?.symbols || 0} symbols
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                            <StatusDot status={repo.status} />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (confirm(`Delete "${repo.name}"?`)) onDeleteRepo(repo.id);
                              }}
                              style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                color: 'var(--text-muted)', padding: 2, display: 'flex',
                                opacity: 1, transition: 'color 120ms',
                              }}
                              aria-label={`Delete ${repo.name}`}
                              title="Delete"
                            >
                              <Trash2 style={{ width: 12, height: 12 }} />
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div style={{
                    borderTop: '1px solid var(--border)',
                    padding: '6px 0 2px',
                    display: 'flex', gap: 4,
                  }}>
                    <button
                      onClick={() => { setDropdownOpen(false); onOpenUpload(); }}
                      style={{
                        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        gap: 4, padding: '6px 0', fontSize: 12, fontWeight: 500,
                        color: 'var(--blue)', background: 'none', border: 'none',
                        cursor: 'pointer', borderRadius: 6,
                        transition: 'background 120ms',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-light)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <Upload style={{ width: 12, height: 12 }} />
                      Import New
                    </button>
                    <button
                      onClick={() => { setDropdownOpen(false); onLoadSample(); }}
                      style={{
                        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        gap: 4, padding: '6px 0', fontSize: 12, fontWeight: 500,
                        color: 'var(--text-secondary)', background: 'none', border: 'none',
                        cursor: 'pointer', borderRadius: 6,
                        transition: 'background 120ms',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      Demo
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Import button (maps to "Share" in reference) */}
        <button
          onClick={onOpenUpload}
          style={{
            padding: '6px 14px', borderRadius: 'var(--radius-button)',
            background: 'var(--surface)', border: '1px solid var(--border)',
            fontSize: 12, fontWeight: 500, color: 'var(--text-primary)',
            cursor: 'pointer', transition: 'all 120ms',
            display: 'flex', alignItems: 'center', gap: 5,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
        >
          <Upload style={{ width: 13, height: 13 }} />
          Import
        </button>

        {/* Index/Reindex button (maps to "Save and Publish" in reference) */}
        <button
          onClick={onReindex}
          disabled={!currentRepo || isIndexing}
          style={{
            padding: '6px 16px', borderRadius: 'var(--radius-button)',
            background: isIndexing ? 'var(--blue)' : 'var(--blue)',
            border: 'none', fontSize: 12, fontWeight: 600,
            color: 'white', cursor: currentRepo && !isIndexing ? 'pointer' : 'not-allowed',
            transition: 'all 120ms',
            display: 'flex', alignItems: 'center', gap: 5,
            boxShadow: '0 1px 4px rgba(20,115,230,0.25)',
            opacity: currentRepo && !isIndexing ? 1 : 0.7,
          }}
          onMouseEnter={(e) => { if (currentRepo) e.currentTarget.style.background = 'var(--blue-hover)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--blue)'; }}
        >
          {isIndexing ? (
            <>
              <RefreshCw style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} />
              Indexing {currentRepo?.progress || 0}%
            </>
          ) : isReady ? (
            <>
              Reindex
            </>
          ) : isFailed ? (
            <>Retry indexing</>
          ) : (
            <>Start indexing</>
          )}
        </button>

        {/* Tutor Mode selector (maps to "Profile" in reference) */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setModeDropdownOpen(!modeDropdownOpen)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 12px', borderRadius: 'var(--radius-button)',
              background: 'var(--surface)', border: '1px solid var(--border)',
              fontSize: 12, fontWeight: 500, color: 'var(--text-primary)',
              cursor: 'pointer', transition: 'all 120ms',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
          >
            <span>{modeLabel}</span>
            <ChevronDown style={{ width: 12, height: 12, color: 'var(--text-muted)' }} />
          </button>

          {modeDropdownOpen && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 50 }} onClick={() => setModeDropdownOpen(false)} />
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 8,
                width: 170, background: 'var(--surface)',
                borderRadius: 12, border: '1px solid var(--border)',
                boxShadow: '0 12px 40px rgba(0,0,0,0.1)',
                padding: 4, zIndex: 51,
              }}>
                {TUTOR_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => { onTutorModeChange(mode.id); setModeDropdownOpen(false); }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      width: '100%', padding: '8px 10px', borderRadius: 6,
                      background: tutorMode === mode.id ? 'var(--surface-selected)' : 'transparent',
                      border: 'none', cursor: 'pointer', fontSize: 12,
                      color: 'var(--text-primary)', textAlign: 'left',
                      transition: 'background 120ms',
                    }}
                    onMouseEnter={(e) => {
                      if (tutorMode !== mode.id) e.currentTarget.style.background = 'var(--surface-hover)';
                    }}
                    onMouseLeave={(e) => {
                      if (tutorMode !== mode.id) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <span>{mode.label}</span>
                    {tutorMode === mode.id && (
                      <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--blue)' }} />
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

// Small status dot component
function StatusDot({ status }: { status: string }) {
  const s = status?.toLowerCase();
  let color = 'var(--orange)';
  if (s === 'ready') color = 'var(--green)';
  else if (s === 'failed') color = 'var(--red)';

  return (
    <span style={{
      width: 7, height: 7, borderRadius: '50%',
      background: color, display: 'inline-block', flexShrink: 0,
    }} />
  );
}
