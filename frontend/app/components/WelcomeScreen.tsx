"use client";

import { ArrowUpRight, Code2, FileSearch, MessageSquare, Network, RefreshCw } from "lucide-react";

interface WelcomeScreenProps {
  loading: boolean;
  error: string | null;
  sampleLoading: boolean;
  onRetry: () => void;
  onImport: () => void;
  onLoadSample: () => void;
}

export default function WelcomeScreen({ loading, error, sampleLoading, onRetry, onImport, onLoadSample }: WelcomeScreenProps) {
  return (
    <main className="welcome-screen">
      <section className="welcome-card" aria-labelledby="welcome-title">
        <div className="welcome-brand"><Code2 size={22} aria-hidden="true" /> CodeMentor-RAG</div>
        <span className="welcome-eyebrow">YOUR CODEBASE, EXPLAINED</span>
        <h1 id="welcome-title">Find the code.<br />Understand the why.</h1>
        {loading ? (
          <p className="welcome-feedback" role="status"><RefreshCw size={16} className="spinner" /> Loading your repositories…</p>
        ) : error ? (
          <div className="welcome-error" role="alert">
            <strong>We couldn’t load your repositories.</strong>
            <p>{error}</p>
            <button className="workspace-button" onClick={onRetry}><RefreshCw size={14} /> Try again</button>
          </div>
        ) : (
          <>
            <div className="welcome-actions">
              <button className="welcome-primary" onClick={onImport}>Import a repository <ArrowUpRight size={16} aria-hidden="true" /></button>
              <button className="welcome-secondary" onClick={onLoadSample} disabled={sampleLoading}>
                {sampleLoading ? <><RefreshCw size={15} className="spinner" /> Preparing demo…</> : "Try the calculator demo"}
              </button>
            </div>
            <p className="welcome-hint" role="status">{sampleLoading ? "The sample will open once the upload is complete." : "Import a ZIP or Git URL. Or explore a sample first."}</p>
          </>
        )}
        <div className="welcome-features">
          <div><FileSearch size={20} /><strong>Explore the source</strong></div>
          <div><Network size={20} /><strong>See how it connects</strong></div>
          <div><MessageSquare size={20} /><strong>Ask with context</strong></div>
        </div>
      </section>
    </main>
  );
}
