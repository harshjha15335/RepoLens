"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Code2, FolderTree, MessageSquare } from "lucide-react";
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
  const currentRepoId = currentRepo?.id;
  const currentRepoStatus = currentRepo?.status.toLowerCase();
  const fileRequestVersion = useRef(0);
  const sessionRequestVersion = useRef(0);
  const chatRequestVersion = useRef(0);
  const chatInFlight = useRef(false);
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
  const [fileError, setFileError] = useState<string | null>(null);
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
  const [mobilePanel, setMobilePanel] = useState("code");

  // Diagnostics
  const [chatLoading, setChatLoading] = useState(false);
  const isPolling = currentRepo !== null && !["ready", "failed", "cancelled"].includes(currentRepo.status.toLowerCase());

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
    } catch (e: unknown) {
      setRepositoryError(e instanceof Error ? e.message : "Check your connection and try again.");
    } finally {
      setRepositoriesLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { void loadRepositories(); }, 0);
    return () => clearTimeout(timer);
  }, [loadRepositories]);

  // Load repo-specific data
  const loadRepoData = useCallback(async (repoId: string, isCurrent: () => boolean) => {
    const sessionVersion = ++sessionRequestVersion.current;
    try {
      const [repoFiles, repoSymbols, repoSessions] = await Promise.all([
        api.getFiles(repoId).catch(() => []),
        api.getSymbols(repoId).catch(() => []),
        api.getSessions(repoId).catch(() => []),
      ]);
      if (!isCurrent()) return;

      setFiles(repoFiles);
      setSymbols(repoSymbols);
      if (sessionVersion === sessionRequestVersion.current) setSessions(repoSessions);

      if (repoSessions.length > 0 && sessionVersion === sessionRequestVersion.current) {
        const firstSession = repoSessions[0];
        setCurrentSessionId(firstSession.id);
        const detail = await api.getSession(firstSession.id).catch((error) => {
          console.error("Failed to load initial session:", error);
          return null;
        });
        if (!isCurrent()) return;
        if (sessionVersion === sessionRequestVersion.current) setMessages(detail?.messages || []);
      } else if (sessionVersion === sessionRequestVersion.current) {
        setCurrentSessionId(undefined);
        setMessages([]);
      }

      if (repoFiles.length > 0) {
        const firstPath = repoFiles[0].path;
        setSelectedFilePath(firstPath);
        setOpenTabs([firstPath]);
      } else {
        setSelectedFilePath(undefined);
        setOpenTabs([]);
        setFileContent(null);
      }
    } catch (e) {
      console.error("Failed to load repo data:", e);
    }
  }, []);

  useEffect(() => {
    if (currentRepoId && currentRepoStatus === "ready") {
      let cancelled = false;
      const timer = setTimeout(() => { void loadRepoData(currentRepoId, () => !cancelled); }, 0);
      return () => { cancelled = true; clearTimeout(timer); };
    }
  }, [currentRepoId, currentRepoStatus, loadRepoData]);

  // Polling for repo status
  useEffect(() => {
    if (!currentRepoId || !isPolling) return;
    let cancelled = false;
    let requestInFlight = false;
    const interval = setInterval(async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const updated = await api.getRepositoryStatus(currentRepoId);
        if (cancelled) return;
        setCurrentRepo(updated);
        setRepositories((prev) =>
          prev.map((r) => (r.id === updated.id ? updated : r))
        );

      } catch (err) {
        console.error("Status polling error:", err);
      } finally {
        requestInFlight = false;
      }
    }, 1500);

    return () => { cancelled = true; clearInterval(interval); };
  }, [currentRepoId, isPolling]);

  // File loading
  const loadFileContent = useCallback(
    async (filePath: string) => {
      if (!currentRepoId) return;
      const requestVersion = ++fileRequestVersion.current;
      setLoadingFile(true);
      setFileError(null);
      try {
        const content = await api.getFileContent(currentRepoId, filePath);
        if (requestVersion !== fileRequestVersion.current) return;
        setFileContent(content);
        setSelectedFilePath(filePath);
        setOpenTabs((prev) => (prev.includes(filePath) ? prev : [...prev, filePath]));
      } catch (e: unknown) {
        if (requestVersion !== fileRequestVersion.current) return;
        console.error("Failed to load file content:", e);
        setFileContent(null);
        setFileError(e instanceof Error ? e.message : "Could not load the file.");
      } finally {
        if (requestVersion === fileRequestVersion.current) setLoadingFile(false);
      }
    },
    [currentRepoId]
  );

  useEffect(() => {
    if (selectedFilePath && currentRepoId && currentRepoStatus === "ready") {
      const requestVersions = fileRequestVersion;
      const timer = setTimeout(() => { void loadFileContent(selectedFilePath); }, 0);
      return () => { clearTimeout(timer); requestVersions.current++; };
    }
  }, [selectedFilePath, currentRepoId, currentRepoStatus, loadFileContent]);

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
        fileRequestVersion.current++;
        setLoadingFile(false);
        setSelectedFilePath(undefined);
        setFileContent(null);
        setFileError(null);
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
  const handleAttachContext = (context: CodeContextAttachment, actionPrompt?: string, mode?: TutorMode) => {
    setMobilePanel("tutor");
    setContextAttachment(context);
    if (actionPrompt) {
      return handleSendMessage(actionPrompt, context, mode);
    }
    return Promise.resolve(true);
  };

  // Chat message sending
  const handleSendMessage = async (question: string, attachedCtx?: CodeContextAttachment, mode?: TutorMode) => {
    if (chatInFlight.current || !currentRepo || currentRepo.status?.toLowerCase() !== "ready") return false;
    sessionRequestVersion.current++;
    const requestVersion = ++chatRequestVersion.current;
    const repoId = currentRepo.id;
    chatInFlight.current = true;

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
        repositoryId: repoId,
        question,
        tutorMode: mode || tutorMode,
        sessionId: currentSessionId,
        codeContext: attachedCtx,
      });
      if (requestVersion !== chatRequestVersion.current) return false;

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

      void api.getSessions(repoId)
        .then((updatedSessions) => {
          if (requestVersion === chatRequestVersion.current) setSessions(updatedSessions);
        })
        .catch((err) => console.error("Failed to refresh sessions:", err));
      return true;
    } catch (err: unknown) {
      if (requestVersion === chatRequestVersion.current) {
        setMessages((prev) => prev.filter((message) => message.id !== tempUserMsg.id));
        alert(err instanceof Error ? err.message : "Failed to get AI response");
      }
      return false;
    } finally {
      if (requestVersion === chatRequestVersion.current) {
        chatInFlight.current = false;
        setChatLoading(false);
      }
    }
  };

  // Sessions
  const handleSelectSession = async (sessionId: string) => {
    const requestVersion = ++sessionRequestVersion.current;
    chatRequestVersion.current++;
    chatInFlight.current = false;
    setChatLoading(false);
    setCurrentSessionId(sessionId);
    setMessages([]);
    try {
      const detail = await api.getSession(sessionId);
      if (requestVersion === sessionRequestVersion.current) setMessages(detail.messages || []);
    } catch (e) {
      console.error("Failed to load session:", e);
      if (requestVersion === sessionRequestVersion.current) {
        alert(e instanceof Error ? e.message : "Failed to load session");
      }
    }
  };

  const handleNewSession = async () => {
    if (!currentRepo) return;
    const repoId = currentRepo.id;
    const requestVersion = ++sessionRequestVersion.current;
    try {
      const newSess = await api.createSession(repoId, tutorMode);
      if (requestVersion !== sessionRequestVersion.current) return;
      chatRequestVersion.current++;
      chatInFlight.current = false;
      setChatLoading(false);
      setSessions((prev) => [newSess, ...prev]);
      setCurrentSessionId(newSess.id);
      setMessages([]);
    } catch (e: unknown) {
      if (requestVersion === sessionRequestVersion.current) {
        alert(e instanceof Error ? e.message : "Failed to create session");
      }
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    const requestVersion = sessionRequestVersion.current;
    try {
      await api.deleteSession(sessionId);
      if (requestVersion !== sessionRequestVersion.current) return;
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        sessionRequestVersion.current++;
        chatRequestVersion.current++;
        chatInFlight.current = false;
        setChatLoading(false);
        setCurrentSessionId(undefined);
        setMessages([]);
      }
    } catch (e: unknown) {
      if (requestVersion === sessionRequestVersion.current) {
        alert(e instanceof Error ? e.message : "Failed to delete session");
      }
    }
  };

  // Repository Operations
  const activateRepository = (repo: Repository) => {
    fileRequestVersion.current++;
    sessionRequestVersion.current++;
    chatRequestVersion.current++;
    chatInFlight.current = false;
    setChatLoading(false);
    setLoadingFile(false);
    setCurrentRepo(repo);
    setFiles([]);
    setSymbols([]);
    setSessions([]);
    setCurrentSessionId(undefined);
    setMessages([]);
    setSelectedFilePath(undefined);
    setOpenTabs([]);
    setFileContent(null);
    setFileError(null);
    setHighlightRange(undefined);
    setContextAttachment(null);
    setActiveActivityView("files");
    setCenterView("code");
    setMobilePanel("code");
  };

  const handleUploadZip = async (file: File) => {
    const newRepo = await api.uploadRepository(file);
    setRepositories((prev) => [newRepo, ...prev]);
    activateRepository(newRepo);
    return newRepo;
  };

  const handleImportGit = async (url: string, branch?: string) => {
    const newRepo = await api.importGit(url, branch);
    setRepositories((prev) => [newRepo, ...prev]);
    activateRepository(newRepo);
    return newRepo;
  };

  const handleDeleteRepo = async (repoId: string) => {
    try {
      await api.deleteRepository(repoId);
      const remaining = repositories.filter((r) => r.id !== repoId);
      setRepositories(remaining);
      if (currentRepo?.id === repoId) {
        if (remaining.length > 0) activateRepository(remaining[0]);
        else {
          fileRequestVersion.current++;
          sessionRequestVersion.current++;
          chatRequestVersion.current++;
          chatInFlight.current = false;
          setChatLoading(false);
          setCurrentRepo(null);
          setFiles([]);
          setSymbols([]);
          setSessions([]);
          setCurrentSessionId(undefined);
          setMessages([]);
          setSelectedFilePath(undefined);
          setFileContent(null);
          setOpenTabs([]);
        }
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to delete repository");
    }
  };

  const handleReindex = async () => {
    if (!currentRepo) return;
    try {
      const updated = await api.reindexRepository(currentRepo.id);
      setCurrentRepo(updated);
      setRepositories((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to reindex");
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
      activateRepository(newRepo);
    } catch (e: unknown) {
      setRepositoryError(e instanceof Error ? e.message : "The sample could not be loaded. Try again.");
    } finally {
      setSampleLoading(false);
    }
  };

  // Determine what the center panel shows
  const showInterview = activeActivityView === "interview";
  const showGraph = !showInterview && (centerView === "graph" || activeActivityView === "graph");
  const returnToCode = () => {
    setActiveActivityView("files");
    setCenterView("code");
    setMobilePanel("code");
  };

  // Keep the welcome screen as the home view until the user opens a repository.
  if (!currentRepo) {
    return (
      <>
        <WelcomeScreen
          loading={repositoriesLoading}
          error={repositoryError}
          sampleLoading={sampleLoading}
          canOpenIDE={repositories.length > 0}
          onRetry={loadRepositories}
          onImport={() => setUploadModalOpen(true)}
          onLoadSample={handleLoadSample}
          onOpenIDE={() => {
            const readyRepo = repositories.find((repo) => repo.status?.toLowerCase() === "ready");
            activateRepository(readyRepo || repositories[0]);
          }}
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
            activateRepository(repo);
          }}
          onOpenUpload={() => setUploadModalOpen(true)}
          onLoadSample={handleLoadSample}
          onRefresh={loadRepositories}
          onDeleteRepo={handleDeleteRepo}
          onReindex={handleReindex}
          isPolling={isPolling}
          tutorMode={tutorMode}
          onTutorModeChange={setTutorMode}
        />

        <nav className="workspace-mobile-nav" aria-label="Workspace panels">
          <button aria-label="Files" title="Files" aria-pressed={mobilePanel === "explorer"} onClick={() => setMobilePanel("explorer")}><FolderTree size={18} /></button>
          <button aria-label="Code" title="Code" aria-pressed={mobilePanel === "code"} onClick={() => setMobilePanel("code")}><Code2 size={18} /></button>
          <button aria-label="Chat" title="Chat" aria-pressed={mobilePanel === "tutor"} onClick={() => setMobilePanel("tutor")}><MessageSquare size={18} /></button>
        </nav>
        {repositoryError && <div className="workspace-error" role="alert">{repositoryError} <button className="workspace-button" onClick={loadRepositories}>Retry</button></div>}
        {fileError && selectedFilePath && <div className="workspace-error" role="alert">{fileError} <button className="workspace-button" onClick={() => loadFileContent(selectedFilePath)}>Retry file</button></div>}
        <div className="workspace-panels" data-mobile-panel={mobilePanel}>
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
                setActiveActivityView("files");
                setCenterView("code");
                setMobilePanel("code");
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
                  onBackToCode={returnToCode}
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
                  onBackToCode={returnToCode}
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
                chatLoading={chatLoading}
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
              onOpenInterview={() => { setActiveActivityView("interview"); setCenterView("code"); setMobilePanel("code"); }}
              sessions={sessions}
              currentSessionId={currentSessionId}
              onNewSession={handleNewSession}
              onSelectSession={handleSelectSession}
              onDeleteSession={handleDeleteSession}
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
        onNavigateView={(view) => { setActiveActivityView(view); setMobilePanel("code"); if (view === "interview") setCenterView("code"); }}
        onOpenUpload={() => setUploadModalOpen(true)}
        onOpenEvaluation={() => setEvalModalOpen(true)}
        onOpenSettings={() => setSettingsModalOpen(true)}
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
          key={`retrieval-${currentRepo.id}`}
          isOpen={labModalOpen}
          onClose={() => setLabModalOpen(false)}
          repositoryId={currentRepo.id}
          onInspectChunk={handleCitationClick}
        />
      )}

      {currentRepo && (
        <EvaluationModal
          key={`evaluation-${currentRepo.id}`}
          isOpen={evalModalOpen}
          onClose={() => setEvalModalOpen(false)}
          repositoryId={currentRepo.id}
        />
      )}

      <SettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        defaultTutorMode={tutorMode}
        onSetDefaultTutorMode={setTutorMode}
        fontSize={fontSize}
        onSetFontSize={setFontSize}
      />
    </div>
  );
}
