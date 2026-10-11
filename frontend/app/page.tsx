"use client";

import React, { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import WelcomeScreen from "./components/WelcomeScreen";
import Sidebar from "./components/Sidebar";
import CodeViewer from "./components/CodeViewer";
import ChatPanel from "./components/ChatPanel";
import GraphView from "./components/GraphView";
import InterviewView from "./components/InterviewView";
import CommandPalette from "./components/CommandPalette";
import UploadModal from "./components/UploadModal";
import RetrievalLabModal from "./components/RetrievalLabModal";
import EvaluationModal from "./components/EvaluationModal";
import SettingsModal from "./components/SettingsModal";
import {
  Repository,
  FileInfo,
  SymbolInfo,
  FileContent,
  ChatMessage,
  ChatSession,
  TutorMode,
  Citation,
  ActiveActivityView,
  CodeContextAttachment,
} from "./types";
import { api } from "./lib/api";

export default function Home() {
  // View state
  const [activeActivityView, setActiveActivityView] = useState<ActiveActivityView>("files");
  const [fontSize, setFontSize] = useState<number>(14);
  const [centerView, setCenterView] = useState<"code" | "graph" | "retrieval" | "evaluation">("code");

  // Repository state
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [currentRepo, setCurrentRepo] = useState<Repository | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [tutorMode, setTutorMode] = useState<TutorMode>("developer");

  // Code Viewer & Tabs state
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [selectedFilePath, setSelectedFilePath] = useState<string | undefined>();
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [highlightRange, setHighlightRange] = useState<
    { start: number; end: number; symbol?: string | null } | undefined
  >();
  const [contextAttachment, setContextAttachment] = useState<CodeContextAttachment | null>(null);

  // Modals
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [labModalOpen, setLabModalOpen] = useState(false);
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  const [repositoriesLoading, setRepositoriesLoading] = useState(true);
  const [repositoryError, setRepositoryError] = useState<string | null>(null);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [explorerVisible, setExplorerVisible] = useState(true);
  const [tutorVisible, setTutorVisible] = useState(true);
  const [mobilePanel, setMobilePanel] = useState("code");
  const [tutorWidth, setTutorWidth] = useState(340);
  const [compactWorkspace, setCompactWorkspace] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 1050px)");
    const update = () => setCompactWorkspace(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  // Diagnostics
  const [chatLoading, setChatLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  // Keyboard shortcut listener for Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Initial repository load
  const loadRepositories = useCallback(async () => {
    setRepositoriesLoading(true);
    setRepositoryError(null);
    try {
      const repos = await api.getRepositories();
      setRepositories(repos);
      if (repos.length > 0 && !currentRepo) {
        const readyRepo = repos.find((r) => r.status?.toLowerCase() === "ready") || repos[0];
        setCurrentRepo(readyRepo);
      }
    } catch (e: any) {
      setRepositoryError(e instanceof Error ? e.message : "Check your connection and try again.");
    } finally {
      setRepositoriesLoading(false);
    }
  }, [currentRepo]);

  useEffect(() => {
    loadRepositories();
  }, [loadRepositories]);

  // Load repo-specific data
  const loadRepoData = useCallback(async (repoId: string) => {
    try {
      const [repoFiles, repoSymbols, repoSessions] = await Promise.all([
        api.getFiles(repoId).catch(() => []),
        api.getSymbols(repoId).catch(() => []),
        api.getSessions(repoId).catch(() => []),
      ]);

      setFiles(repoFiles);
      setSymbols(repoSymbols);
      setSessions(repoSessions);

      if (repoSessions.length > 0) {
        const firstSession = repoSessions[0];
        setCurrentSessionId(firstSession.id);
        const detail = await api.getSession(firstSession.id);
        setMessages(detail.messages || []);
      } else {
        setCurrentSessionId(undefined);
        setMessages([]);
      }

      if (repoFiles.length > 0) {
        const firstPath = repoFiles[0].path;
        setSelectedFilePath(firstPath);
        setOpenTabs([firstPath]);
      }
    } catch (e) {
      console.error("Failed to load repo data:", e);
    }
  }, []);

  useEffect(() => {
    if (currentRepo && currentRepo.status?.toLowerCase() === "ready") {
      loadRepoData(currentRepo.id);
    }
  }, [currentRepo?.id, currentRepo?.status, loadRepoData]);

  // Polling for repo status
  useEffect(() => {
    const isFinished =
      !currentRepo ||
      currentRepo.status?.toLowerCase() === "ready" ||
      currentRepo.status?.toLowerCase() === "failed";
    if (isFinished) {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    const interval = setInterval(async () => {
      try {
        const updated = await api.getRepositoryStatus(currentRepo.id);
        setCurrentRepo(updated);
        setRepositories((prev) =>
          prev.map((r) => (r.id === updated.id ? updated : r))
        );

        if (updated.status?.toLowerCase() === "ready") {
          setIsPolling(false);
          loadRepoData(updated.id);
        } else if (updated.status?.toLowerCase() === "failed") {
          setIsPolling(false);
        }
      } catch (err) {
        console.error("Status polling error:", err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [currentRepo?.id, currentRepo?.status, loadRepoData]);

  // File loading
  const loadFileContent = useCallback(
    async (filePath: string) => {
      if (!currentRepo) return;
      setLoadingFile(true);
      try {
        const content = await api.getFileContent(currentRepo.id, filePath);
        setFileContent(content);
        setSelectedFilePath(filePath);
        setOpenTabs((prev) => (prev.includes(filePath) ? prev : [...prev, filePath]));
      } catch (e: any) {
        console.error("Failed to load file content:", e);
      } finally {
        setLoadingFile(false);
      }
    },
    [currentRepo]
  );

  useEffect(() => {
    if (selectedFilePath && currentRepo && currentRepo.status?.toLowerCase() === "ready") {
      loadFileContent(selectedFilePath);
    }
  }, [selectedFilePath, currentRepo?.id, currentRepo?.status, loadFileContent]);

  // File tab management
  const handleSelectTab = (path: string) => {
    setSelectedFilePath(path);
    setHighlightRange(undefined);
    loadFileContent(path);
  };

  const handleCloseTab = (path: string) => {
    const remaining = openTabs.filter((t) => t !== path);
    setOpenTabs(remaining);
    if (selectedFilePath === path) {
      if (remaining.length > 0) {
        handleSelectTab(remaining[remaining.length - 1]);
      } else {
        setSelectedFilePath(undefined);
        setFileContent(null);
      }
    }
  };

  // Citation click: opens file, scrolls to lines, highlights with pulse
  const handleCitationClick = (citation: Citation) => {
    if (centerView !== "code") setCenterView("code");
    if (activeActivityView === "graph" || activeActivityView === "interview") {
      setActiveActivityView("files");
    }

    setSelectedFilePath(citation.file_path);
    setHighlightRange({
      start: citation.start_line,
      end: citation.end_line,
      symbol: citation.symbol_name || citation.symbol,
    });
    loadFileContent(citation.file_path);
  };

  // Symbol click: opens file at symbol line
  const handleSymbolClick = (symbol: SymbolInfo) => {
    if (centerView !== "code") setCenterView("code");
    if (activeActivityView === "graph" || activeActivityView === "interview") {
      setActiveActivityView("symbols");
    }
    setSelectedFilePath(symbol.file_path);
    setHighlightRange({
      start: symbol.start_line,
      end: symbol.end_line,
      symbol: symbol.name,
    });
    loadFileContent(symbol.file_path);
  };

  // Code selection context attachment
  const handleAttachContext = (context: CodeContextAttachment, actionPrompt?: string) => {
    setContextAttachment(context);
    if (actionPrompt) {
      handleSendMessage(actionPrompt, context);
    }
  };

  // Chat message sending
  const handleSendMessage = async (question: string, attachedCtx?: CodeContextAttachment) => {
    if (!currentRepo || currentRepo.status?.toLowerCase() !== "ready") return;

    let finalQuestion = question;
    if (attachedCtx) {
      finalQuestion = `[Context: ${attachedCtx.file_path} L${attachedCtx.start_line}-${attachedCtx.end_line}]\n${question}`;
    }

    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setChatLoading(true);

    try {
      const response = await api.sendMessage({
        repositoryId: currentRepo.id,
        question: finalQuestion,
        tutorMode,
        sessionId: currentSessionId,
      });

      setCurrentSessionId(response.session_id);

      const assistantMsg: ChatMessage = {
        id: response.message_id,
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        retrieval_metadata: response.retrieval_metadata,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setContextAttachment(null);

      const updatedSessions = await api.getSessions(currentRepo.id);
      setSessions(updatedSessions);
    } catch (err: any) {
      alert(err.message || "Failed to get AI response");
    } finally {
      setChatLoading(false);
    }
  };

  // Sessions
  const handleSelectSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const detail = await api.getSession(sessionId);
      setMessages(detail.messages || []);
    } catch (e) {
      console.error("Failed to load session:", e);
    }
  };

  const handleNewSession = async () => {
    if (!currentRepo) return;
    try {
      const newSess = await api.createSession(currentRepo.id, tutorMode);
      setSessions((prev) => [newSess, ...prev]);
      setCurrentSessionId(newSess.id);
      setMessages([]);
    } catch (e: any) {
      alert(e.message || "Failed to create session");
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        setCurrentSessionId(undefined);
        setMessages([]);
      }
    } catch (e: any) {
      alert(e.message || "Failed to delete session");
    }
  };

  // Repository Operations
  const handleUploadZip = async (file: File) => {
    const newRepo = await api.uploadRepository(file);
    setRepositories((prev) => [newRepo, ...prev]);
    setCurrentRepo(newRepo);
    return newRepo;
  };

  const handleImportGit = async (url: string, branch?: string) => {
    const newRepo = await api.importGit(url, branch);
    setRepositories((prev) => [newRepo, ...prev]);
    setCurrentRepo(newRepo);
    return newRepo;
  };

  const handleDeleteRepo = async (repoId: string) => {
    try {
      await api.deleteRepository(repoId);
      const remaining = repositories.filter((r) => r.id !== repoId);
      setRepositories(remaining);
      if (currentRepo?.id === repoId) {
        setCurrentRepo(remaining.length > 0 ? remaining[0] : null);
        setFiles([]);
        setSymbols([]);
        setSessions([]);
        setMessages([]);
        setFileContent(null);
        setOpenTabs([]);
      }
    } catch (e: any) {
      alert(e.message || "Failed to delete repository");
    }
  };

  const handleReindex = async () => {
    if (!currentRepo) return;
    try {
      const updated = await api.reindexRepository(currentRepo.id);
      setCurrentRepo(updated);
      setRepositories((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e: any) {
      alert(e.message || "Failed to reindex");
    }
  };

  // 1-Click Load Sample Calculator
  const handleLoadSample = async () => {
    if (sampleLoading) return;
    setSampleLoading(true);
    setRepositoryError(null);
    try {
      const res = await fetch("/api/sample", { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Sample load failed" }));
        throw new Error(err.error || "Failed to load sample repository");
      }
      const newRepo = await res.json();
      setRepositories((prev) => [newRepo, ...prev.filter((r) => r.id !== newRepo.id)]);
      setCurrentRepo(newRepo);
    } catch (e: any) {
      setRepositoryError(e instanceof Error ? e.message : "The sample could not be loaded. Try again.");
    } finally {
      setSampleLoading(false);
    }
  };

  // Determine what the center panel shows
  const showGraph = centerView === "graph" || activeActivityView === "graph";
  const showInterview = activeActivityView === "interview";

  // Repository dashboard (no repo selected or no repos)
  if (!currentRepo && repositories.length === 0) {
    return (
      <>
        <WelcomeScreen
          loading={repositoriesLoading}
          error={repositoryError}
          sampleLoading={sampleLoading}
          onRetry={loadRepositories}
          onImport={() => setUploadModalOpen(true)}
          onLoadSample={handleLoadSample}
        />
        <UploadModal
          isOpen={uploadModalOpen}
          onClose={() => setUploadModalOpen(false)}
          onUploadZip={handleUploadZip}
          onImportGit={handleImportGit}
          onLoadSample={handleLoadSample}
        />
      </>
    );
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column',
      width: '100vw', height: '100vh',
      background: 'var(--bg-desktop)',
      overflow: 'hidden',
    }}>
      {/* Main Full-Screen Application Window */}
      <div style={{
        flex: 1,
        width: '100%', height: '100%',
        background: 'var(--bg-desktop)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Global Top Bar */}
        <Header
          repositories={repositories}
          currentRepo={currentRepo}
          onSelectRepo={(repo) => {
            setCurrentRepo(repo);
            setHighlightRange(undefined);
          }}
          onOpenUpload={() => setUploadModalOpen(true)}
          onOpenLab={() => setLabModalOpen(true)}
          onOpenEvaluation={() => setEvalModalOpen(true)}
          onLoadSample={handleLoadSample}
          onRefresh={loadRepositories}
          onDeleteRepo={handleDeleteRepo}
          onReindex={handleReindex}
          isPolling={isPolling}
          tutorMode={tutorMode}
          onTutorModeChange={setTutorMode}
          centerView={centerView}
          onCenterViewChange={setCenterView}
          onOpenSettings={() => setSettingsModalOpen(true)}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        />

        <nav className="workspace-toolbar" aria-label="Workspace panels">
          <div className="workspace-panel-controls">
            <button className="workspace-button" aria-pressed={compactWorkspace ? mobilePanel === "explorer" : explorerVisible} onClick={() => { if (!compactWorkspace) setExplorerVisible(!explorerVisible); setMobilePanel("explorer"); }}>Explorer</button>
            <button className="workspace-button workspace-code-toggle" aria-pressed={mobilePanel === "code"} onClick={() => setMobilePanel("code")}>Code</button>
            <button className="workspace-button" aria-pressed={compactWorkspace ? mobilePanel === "tutor" : tutorVisible} onClick={() => { if (!compactWorkspace) setTutorVisible(!tutorVisible); setMobilePanel("tutor"); }}>AI tutor</button>
          </div>
          <label className="workspace-width-control">Tutor width <input type="range" min="260" max="480" step="20" value={tutorWidth} onChange={(event) => setTutorWidth(Number(event.target.value))} /></label>
          <span className="workspace-shortcut">Search files & commands <kbd>Ctrl / ⌘ K</kbd></span>
        </nav>
        {repositoryError && <div className="workspace-error" role="alert">{repositoryError} <button className="workspace-button" onClick={loadRepositories}>Retry</button></div>}
        <div className="workspace-panels" data-explorer={explorerVisible} data-tutor={tutorVisible} data-mobile-panel={mobilePanel} style={{ "--tutor-width": `${tutorWidth}px` } as React.CSSProperties}>
          {/* Left Panel - Repository Explorer */}
          <div className="workspace-explorer" style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-panel)',
            overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}>
            <Sidebar
              currentRepo={currentRepo}
              files={files}
              symbols={symbols}
              sessions={sessions}
              currentSessionId={currentSessionId}
              selectedFilePath={selectedFilePath}
              activeView={activeActivityView}
              onSelectFile={(path) => {
                setSelectedFilePath(path);
                setHighlightRange(undefined);
                setCenterView("code");
                loadFileContent(path);
              }}
              onSelectSymbol={handleSymbolClick}
              onSelectSession={handleSelectSession}
              onNewSession={handleNewSession}
              onDeleteSession={handleDeleteSession}
              onAskQuery={(q) => handleSendMessage(q)}
              collapsed={false}
              onToggleCollapse={() => {}}
            />
          </div>

          {/* Center Panel - Main Code Workspace */}
          <div className="workspace-editor" style={{
            minWidth: 0,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-panel)',
            overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
            position: 'relative',
          }}>
            {showGraph ? (
              currentRepo ? (
                <GraphView
                  repositoryId={currentRepo.id}
                  onInspectNode={handleCitationClick}
                />
              ) : (
                <div style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
                  Select a repository to explore its code knowledge graph.
                </div>
              )
            ) : showInterview ? (
              currentRepo ? (
                <InterviewView
                  repositoryId={currentRepo.id}
                  repoName={currentRepo.name}
                  onInspectCitation={handleCitationClick}
                />
              ) : (
                <div style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--text-muted)' }}>
                  Select a repository to start an interview session.
                </div>
              )
            ) : (
              <CodeViewer
                repoName={currentRepo?.name}
                repoStatus={currentRepo?.status}
                fileContent={fileContent}
                loading={loadingFile}
                highlightRange={highlightRange}
                openTabs={openTabs}
                activeFilePath={selectedFilePath}
                onSelectTab={handleSelectTab}
                onCloseTab={handleCloseTab}
                onAttachContext={handleAttachContext}
                fontSize={fontSize}
                onSendMessage={handleSendMessage}
                isRepoReady={currentRepo?.status?.toLowerCase() === "ready"}
                centerView={centerView}
                onCenterViewChange={setCenterView}
                onOpenSettings={() => setSettingsModalOpen(true)}
                onOpenLab={() => setLabModalOpen(true)}
                onOpenEvaluation={() => setEvalModalOpen(true)}
              />
            )}
          </div>

          {/* Right Panel - AI Tutor */}
          <div className="workspace-tutor" style={{
            background: 'var(--surface-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-panel)',
            overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
          }}>
            <ChatPanel
              messages={messages}
              loading={chatLoading}
              tutorMode={tutorMode}
              onTutorModeChange={setTutorMode}
              onSendMessage={handleSendMessage}
              onCitationClick={handleCitationClick}
              contextAttachment={contextAttachment}
              onRemoveContext={() => setContextAttachment(null)}
              repoName={currentRepo?.name}
              isRepoReady={currentRepo?.status?.toLowerCase() === "ready"}
              onOpenInterview={() => setActiveActivityView("interview")}
            />
          </div>
        </div>
      </div>

      {/* Global Modals */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        files={files}
        symbols={symbols}
        onSelectFile={(path) => {
          setSelectedFilePath(path);
          loadFileContent(path);
          setActiveActivityView("files");
          setCenterView("code");
        }}
        onSelectSymbol={(sym) => handleSymbolClick(sym)}
        onSelectTutorMode={setTutorMode}
        onNavigateView={(view) => setActiveActivityView(view)}
        onOpenUpload={() => setUploadModalOpen(true)}
        onOpenEvaluation={() => setEvalModalOpen(true)}
        onOpenSettings={() => setSettingsModalOpen(true)}
        onToggleTheme={() => {}}
        onAskQuestion={(q) => handleSendMessage(q)}
      />

      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        onUploadZip={handleUploadZip}
        onImportGit={handleImportGit}
        onLoadSample={handleLoadSample}
      />

      {currentRepo && (
        <RetrievalLabModal
          isOpen={labModalOpen}
          onClose={() => setLabModalOpen(false)}
          repositoryId={currentRepo.id}
          onInspectChunk={handleCitationClick}
        />
      )}

      {currentRepo && (
        <EvaluationModal
          isOpen={evalModalOpen}
          onClose={() => setEvalModalOpen(false)}
          repositoryId={currentRepo.id}
        />
      )}

      <SettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        theme={"light"}
        onToggleTheme={() => {}}
        defaultTutorMode={tutorMode}
        onSetDefaultTutorMode={setTutorMode}
        fontSize={fontSize}
        onSetFontSize={setFontSize}
      />
    </div>
  );
}
