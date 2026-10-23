"use client";

import { ArrowUpRight, Code2, FileSearch, MessageSquare, Network, RefreshCw } from "lucide-react";
import { Repository } from "../types";
import RepoLensLogo from "./RepoLensLogo";

interface WelcomeScreenProps {
  loading: boolean;
  error: string | null;
  sampleLoading: boolean;
  canOpenIDE: boolean;
  onRetry: () => void;
  onImport: () => void;
  onLoadSample: () => void;
  onOpenIDE: () => void;
  repositories: Repository[];
  onSelectRepository: (repository: Repository) => void;
  onSignOut?: () => void | Promise<void>;
}

export default function WelcomeScreen({ loading, error, sampleLoading, canOpenIDE, onRetry, onImport, onLoadSample, onOpenIDE, repositories, onSelectRepository, onSignOut }: WelcomeScreenProps) {
  return (
    <main className="welcome-screen">
      <section className="welcome-card" aria-labelledby="welcome-title">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="welcome-brand" style={{ marginBottom: 0 }}><RepoLensLogo size={24} aria-hidden="true" /> RepoLens</div>
          {onSignOut && <button className="workspace-button" onClick={() => void onSignOut()}>Sign out</button>}
        </div>
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
              {canOpenIDE && <button className="welcome-primary" onClick={onOpenIDE}>Open IDE <Code2 size={16} aria-hidden="true" /></button>}
              <button className="welcome-primary" onClick={onImport}>Import a repository <ArrowUpRight size={16} aria-hidden="true" /></button>
              <button className="welcome-secondary" onClick={onLoadSample} disabled={sampleLoading}>
                {sampleLoading ? <><RefreshCw size={15} className="spinner" /> Preparing demo…</> : "Try the calculator demo"}
              </button>
            </div>
            <p className="welcome-hint" role="status">{sampleLoading ? "The sample will open once the upload is complete." : "Import a ZIP or Git URL. Or explore a sample first."}</p>
            {repositories.length > 0 && (
              <section className="welcome-repositories" aria-label="Your repositories">
                <h2>Your repositories</h2>
                <div className="welcome-repository-list">
                  {repositories.map((repository) => (
                    <button key={repository.id} type="button" onClick={() => onSelectRepository(repository)} className="welcome-repository">
                      <span className="welcome-repository-name">{repository.name}</span>
                      <span className="welcome-repository-status">{repository.status.toLowerCase() === "ready" ? `${repository.stats?.files ?? 0} files · Ready` : repository.status.replaceAll("_", " ")}</span>
                      <ArrowUpRight size={16} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </section>
            )}
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
