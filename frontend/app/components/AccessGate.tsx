"use client";

import React, { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";

type AuthStatus = { authenticated: boolean; configured: boolean };

interface AccessGateProps {
  children: (signOut: () => Promise<void>) => ReactNode;
}

export default function AccessGate({ children }: AccessGateProps) {
  const [authenticated, setAuthenticated] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [accessKey, setAccessKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  const checkStatus = useCallback(async (signal?: AbortSignal) => {
    if (!signal) {
      setChecking(true);
      setError(null);
    }
    try {
      const response = await fetch("/api/auth/status", { credentials: "same-origin", signal });
      const status = await response.json().catch(() => ({})) as Partial<AuthStatus> & { error?: string };
      if (!response.ok) throw new Error(status.error || `Could not check sign-in status (HTTP ${response.status}).`);
      setConfigured(Boolean(status.configured));
      setAuthenticated(Boolean(status.authenticated && status.configured));
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(cause instanceof Error ? cause.message : "Could not check sign-in status.");
      setAuthenticated(false);
    } finally {
      if (!signal?.aborted) setChecking(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(() => {
      if (!controller.signal.aborted) return checkStatus(controller.signal);
    });
    return () => controller.abort();
  }, [checkStatus]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setAuthenticated(false);
      setError("Your session has expired. Sign in again to continue.");
    };
    window.addEventListener("repolens:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("repolens:unauthorized", handleUnauthorized);
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting || configured !== true || !accessKey) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ access_key: accessKey }),
      });
      const result = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(result.error || "Sign-in failed. Check the access key and try again.");
      setAccessKey("");
      setAuthenticated(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-in failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const signOut = useCallback(async () => {
    setError(null);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
      const result = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(result.error || `Sign-out failed (HTTP ${response.status}).`);
      setAuthenticated(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign-out failed. Try again.");
    }
  }, []);

  if (checking) {
    return <main style={styles.screen}><p style={styles.muted} role="status">Checking access…</p></main>;
  }

  if (authenticated) {
    return <>
      {error && <div role="alert" style={styles.workspaceError}>{error}</div>}
      {children(signOut)}
    </>;
  }

  return (
    <main style={styles.screen}>
      <section style={styles.card} aria-labelledby="access-title">
        <div style={styles.brand}><span aria-hidden="true" style={styles.mark}>&lt;/&gt;</span> RepoLens</div>
        <p style={styles.eyebrow}>PRIVATE WORKSPACE</p>
        <h1 id="access-title" style={styles.title}>Sign in to RepoLens</h1>
        <p style={styles.description}>Enter the workspace access key to continue.</p>
        {configured === false && <p role="status" style={styles.notice}>Sign-in is not configured on this server. Set the server access key to enable workspace access.</p>}
        {error && <p role="alert" style={styles.error}>{error}</p>}
        <form onSubmit={handleLogin} style={styles.form}>
          <label htmlFor="access-key" style={styles.label}>Access key</label>
          <input
            id="access-key"
            type="password"
            autoComplete="current-password"
            value={accessKey}
            onChange={(event) => setAccessKey(event.target.value)}
            disabled={configured !== true || submitting}
            required
            style={styles.input}
          />
          <button type="submit" disabled={configured !== true || submitting || !accessKey} style={styles.submit}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <button type="button" onClick={() => void checkStatus()} disabled={submitting} style={styles.retry}>Check again</button>
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  screen: { minHeight: "100dvh", display: "grid", placeItems: "center", padding: 24, background: "radial-gradient(ellipse at 15% 0%, #e8f2ff, transparent 55%), var(--bg-desktop)", color: "var(--text-primary)", fontFamily: "var(--font-sans)" },
  card: { width: "100%", maxWidth: 440, padding: 40, border: "1px solid var(--border)", borderRadius: 20, background: "var(--surface)", boxShadow: "0 16px 60px rgba(20,30,50,.06)" },
  brand: { display: "flex", alignItems: "center", gap: 10, marginBottom: 42, fontSize: 16, fontWeight: 700 },
  mark: { display: "grid", placeItems: "center", width: 30, height: 30, borderRadius: 9, background: "linear-gradient(135deg, #1473e6, #0ea5e9)", color: "white", fontSize: 12, fontWeight: 700 },
  eyebrow: { margin: 0, color: "var(--text-secondary)", fontSize: 11, letterSpacing: ".12em", fontWeight: 700 },
  title: { margin: "12px 0 8px", fontSize: 30, letterSpacing: "-.03em" },
  description: { margin: "0 0 24px", color: "var(--text-secondary)", fontSize: 14 },
  form: { display: "grid", gap: 10 },
  label: { fontSize: 12, fontWeight: 600 },
  input: { width: "100%", height: 44, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, background: "var(--surface)", color: "var(--text-primary)", fontSize: 14 },
  submit: { height: 44, marginTop: 6, border: 0, borderRadius: 8, background: "var(--blue)", color: "white", fontSize: 13, fontWeight: 600, cursor: "pointer" },
  retry: { marginTop: 14, padding: "6px 0", border: 0, background: "transparent", color: "var(--text-secondary)", fontSize: 12, cursor: "pointer" },
  muted: { color: "var(--text-secondary)", fontSize: 14 },
  notice: { padding: 12, borderRadius: 8, background: "var(--blue-light)", color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.5 },
  error: { padding: 12, border: "1px solid #fecaca", borderRadius: 8, background: "var(--red-light)", color: "#991b1b", fontSize: 13, lineHeight: 1.5 },
  workspaceError: { position: "fixed", zIndex: 100, top: 12, left: "50%", transform: "translateX(-50%)", padding: "10px 14px", border: "1px solid #fecaca", borderRadius: 8, background: "var(--red-light)", color: "#991b1b", fontSize: 13, boxShadow: "0 4px 16px rgba(0,0,0,.08)" },
};
