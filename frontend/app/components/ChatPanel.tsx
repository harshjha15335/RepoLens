"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  FileCode,
  ChevronDown,
  ChevronUp,
  Layers,
  Copy,
  Check,
  X,
  Paperclip,
  MoreVertical,
  Plus,
  History,
  Trash2,
} from "lucide-react";
import { ChatMessage, ChatSession, TutorMode, Citation, RetrievedChunk, CodeContextAttachment } from "../types";

interface ChatPanelProps {
  messages: ChatMessage[];
  loading: boolean;
  tutorMode: TutorMode;
  onTutorModeChange: (mode: TutorMode) => void;
  onSendMessage: (question: string, contextAttachment?: CodeContextAttachment) => Promise<boolean>;
  onCitationClick: (citation: Citation) => void;
  contextAttachment?: CodeContextAttachment | null;
  onRemoveContext?: () => void;
  repoName?: string;
  isRepoReady: boolean;
  onOpenInterview?: () => void;
  sessions: ChatSession[];
  currentSessionId?: string;
  onNewSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

const SUGGESTED_PROMPTS = [
  "Explain the high-level architecture of this codebase",
  "Where is the Calculator class defined and how does division handle zero?",
  "What is the inheritance hierarchy?",
  "Trace what calls the _record method",
  "How does the expression parser work?",
];

function ResponseTimer() {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const intervalId = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <span aria-live="polite">
      {elapsedSeconds >= 20 ? "Local model is still generating" : "Waiting for response"} · {elapsedSeconds}s
    </span>
  );
}

export default function ChatPanel({
  messages,
  loading,
  tutorMode,
  onSendMessage,
  onCitationClick,
  contextAttachment,
  onRemoveContext,
  isRepoReady,
  onOpenInterview,
  sessions,
  currentSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [expandedRetrieval, setExpandedRetrieval] = useState<{ [msgId: string]: boolean }>({});
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading || !isRepoReady) return;
    const question = input.trim();
    void onSendMessage(question, contextAttachment || undefined).then((sent) => {
      if (sent) setInput((current) => current === question ? "" : current);
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const toggleRetrieval = (msgId: string) => {
    setExpandedRetrieval((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const copyText = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedCode(id);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch {
      alert("Could not copy the code. Check clipboard access and try again.");
    }
  };

const stripEmojis = (str: string) => {
  if (!str) return '';
  return str
    .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{2300}-\u{23FF}\u{2B50}-\u{2B55}\u{FE0E}\u{FE0F}]/gu, '')
    .replace(/[ \t]+/g, ' ');
};

  const renderMessageContent = (rawContent: string, messageId: string) => {
    const content = stripEmojis(rawContent);
    const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
    type MessagePart = { type: "text"; content: string } | { type: "code"; language: string; code: string };
    const parts: MessagePart[] = [];
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: "text", content: content.slice(lastIndex, match.index) });
      }
      parts.push({ type: "code", language: match[1] || "text", code: match[2] });
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < content.length) {
      parts.push({ type: "text", content: content.slice(lastIndex) });
    }

    return (
      <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)' }}>
        {parts.map((part, i) => {
          if (part.type === "code") {
            const blockId = `${messageId}-block-${i}`;
            return (
              <div key={i} style={{
                margin: '10px 0', borderRadius: 10, overflow: 'hidden',
                border: '1px solid var(--border)', background: '#fafafa',
              }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 10px', background: 'var(--surface-selected)',
                  borderBottom: '1px solid var(--border)',
                  fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                }}>
                  <span style={{ textTransform: 'uppercase', fontWeight: 600 }}>{part.language}</span>
                  <button
                    onClick={() => copyText(part.code, blockId)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 3,
                      background: 'none', border: 'none', cursor: 'pointer',
                      fontSize: 10, color: 'var(--text-muted)',
                    }}
                  >
                    {copiedCode === blockId ? <Check style={{ width: 12, height: 12, color: 'var(--green)' }} /> : <Copy style={{ width: 12, height: 12 }} />}
                  </button>
                </div>
                <pre style={{
                  padding: 10, fontFamily: 'var(--font-mono)', fontSize: 12,
                  overflowX: 'auto', lineHeight: 1.5, margin: 0,
                  color: 'var(--text-primary)',
                }}>
                  <code>{part.code}</code>
                </pre>
              </div>
            );
          }
          return (
            <div key={i} style={{ whiteSpace: 'pre-line' }}>
              {part.content}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="dotted-grid" style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      background: 'var(--surface-secondary)',
      overflow: 'hidden', position: 'relative',
    }}>
      {/* Panel Header */}
      <div style={{
        height: 44, borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', flexShrink: 0,
        background: 'var(--surface)',
      }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
          AI Tutor
        </span>
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Chat options"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: 4, borderRadius: 6, display: 'flex',
              color: 'var(--text-muted)', transition: 'color 80ms',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            <MoreVertical style={{ width: 16, height: 16 }} />
          </button>
          {menuOpen && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 50 }} onClick={() => setMenuOpen(false)} />
              <div style={{
                position: 'absolute', right: 0, top: '100%', marginTop: 4,
                width: 240, maxHeight: 360, overflowY: 'auto', background: 'var(--surface)',
                borderRadius: 10, border: '1px solid var(--border)',
                boxShadow: 'var(--shadow-floating)', padding: 4, zIndex: 51,
              }}>
                {[
                  { label: "New Chat", icon: Plus, action: onNewSession },
                  { label: "Start Interview", icon: History, action: onOpenInterview },
                ].map(({ label, icon: Icon, action }) => (
                  <button
                    key={label}
                    onClick={() => { action?.(); setMenuOpen(false); }}
                    disabled={!isRepoReady}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                      padding: '7px 10px', borderRadius: 6, border: 'none',
                      background: 'transparent', cursor: 'pointer', fontSize: 12,
                      color: 'var(--text-primary)', textAlign: 'left',
                      transition: 'background 80ms',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <Icon style={{ width: 14, height: 14, color: 'var(--text-muted)' }} />
                    {label}
                  </button>
                ))}
                {sessions.length > 0 && (
                  <div style={{ borderTop: '1px solid var(--border)', marginTop: 4, paddingTop: 4 }}>
                    <div style={{ padding: '5px 10px', fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Recent chats</div>
                    {sessions.map((session) => (
                      <div key={session.id} style={{ display: 'flex', alignItems: 'center', background: currentSessionId === session.id ? 'var(--surface-selected)' : 'transparent', borderRadius: 6 }}>
                        <button
                          onClick={() => { onSelectSession(session.id); setMenuOpen(false); }}
                          style={{ flex: 1, minWidth: 0, padding: '7px 10px', border: 'none', background: 'transparent', textAlign: 'left', color: 'var(--text-primary)', cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}
                        >
                          {session.title || `Chat ${new Date(session.created_at).toLocaleDateString()}`}
                        </button>
                        <button aria-label={`Delete ${session.title || 'chat'}`} title="Delete chat" onClick={() => onDeleteSession(session.id)} style={{ padding: 6, display: 'flex', border: 'none', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}><Trash2 size={13} /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 16px' }}>
            <div style={{
              width: 44, height: 44, borderRadius: 14,
              background: 'var(--blue-light)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 16px',
            }}>
              <Bot style={{ width: 22, height: 22, color: 'var(--blue)' }} />
            </div>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px' }}>
              RepoLens AI Tutor
            </h3>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: 6, textAlign: 'center' }}>
                Suggested questions
              </div>
              {SUGGESTED_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => { if (isRepoReady) onSendMessage(prompt); }}
                  disabled={!isRepoReady}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    padding: '8px 10px', marginBottom: 4,
                    borderRadius: 'var(--radius-row)', fontSize: 12,
                    color: 'var(--text-secondary)',
                    background: 'var(--surface)', border: '1px solid var(--border)',
                    cursor: isRepoReady ? 'pointer' : 'not-allowed',
                    opacity: isRepoReady ? 1 : 0.5,
                    transition: 'background 80ms',
                  }}
                  onMouseEnter={(e) => { if (isRepoReady) e.currentTarget.style.background = 'var(--surface-hover)'; }}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--surface)')}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              const messageMode = typeof msg.retrieval_metadata?.tutor_mode === "string"
                ? msg.retrieval_metadata.tutor_mode : tutorMode;
              return (
                <div key={msg.id} style={{
                  display: 'flex', gap: 8,
                  flexDirection: isUser ? 'row-reverse' : 'row',
                  maxWidth: '100%',
                }}>
                  {/* Message Content */}
                  <div style={{
                    background: isUser ? 'var(--surface)' : 'var(--surface)',
                    border: `1px solid ${isUser ? 'var(--border)' : 'var(--border)'}`,
                    borderRadius: 12,
                    padding: '10px 14px',
                    maxWidth: '95%',
                    boxShadow: 'var(--shadow-subtle)',
                  }}>
                    {/* Header */}
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      marginBottom: 6, fontSize: 11, color: 'var(--text-muted)',
                    }}>
                      <span style={{ fontWeight: 600, color: isUser ? 'var(--text-secondary)' : 'var(--blue)', fontSize: 11 }}>
                        {isUser ? "You" : "RepoLens"}
                      </span>
                      {!isUser && (
                        <span style={{
                          fontSize: 9, padding: '1px 6px', borderRadius: 4,
                          textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.03em',
                          background: 'var(--blue-light)', color: 'var(--blue)',
                        }}>
                          {messageMode}
                        </span>
                      )}
                    </div>

                    {/* Body */}
                    {isUser ? (
                      <p style={{ fontSize: 13, color: 'var(--text-primary)', margin: 0, whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                        {stripEmojis(msg.content)}
                      </p>
                    ) : (
                      renderMessageContent(msg.content, msg.id)
                    )}

                    {/* Citations */}
                    {!isUser && msg.citations && msg.citations.length > 0 && (
                      <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                        <div style={{
                          fontSize: 10, fontWeight: 600, color: 'var(--text-muted)',
                          marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4,
                        }}>
                          <FileCode style={{ width: 12, height: 12, color: 'var(--blue)' }} />
                          Sources
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                          {msg.citations.map((c, idx) => {
                            const fn = c.file_path.split("/").pop() || c.file_path;
                            return (
                              <button
                                key={idx}
                                onClick={() => onCitationClick(c)}
                                title={c.snippet || `${c.file_path}:${c.start_line}-${c.end_line}`}
                                style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 4,
                                  padding: '3px 8px', borderRadius: 7,
                                  fontSize: 11, fontFamily: 'var(--font-mono)',
                                  background: 'var(--surface)', border: '1px solid var(--border)',
                                  color: 'var(--text-secondary)', cursor: 'pointer',
                                  transition: 'all 100ms',
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.borderColor = 'var(--blue)';
                                  e.currentTarget.style.color = 'var(--blue)';
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.borderColor = 'var(--border)';
                                  e.currentTarget.style.color = 'var(--text-secondary)';
                                }}
                              >
                                <span style={{ fontWeight: 500 }}>{fn}</span>
                                <span style={{ color: 'var(--text-muted)' }}>·</span>
                                <span>{c.start_line}–{c.end_line}</span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Retrieval Inspector */}
                    {!isUser && msg.retrieval_metadata && (
                      <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                        <button
                          onClick={() => toggleRetrieval(msg.id)}
                          style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            width: '100%', background: 'none', border: 'none',
                            cursor: 'pointer', fontSize: 10, color: 'var(--text-muted)',
                            padding: 0, transition: 'color 80ms',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                        >
                          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 500 }}>
                            <Layers style={{ width: 12, height: 12, color: 'var(--blue)' }} />
                            Retrieval Inspector
                          </span>
                          {expandedRetrieval[msg.id] ? <ChevronUp style={{ width: 12, height: 12 }} /> : <ChevronDown style={{ width: 12, height: 12 }} />}
                        </button>

                        {expandedRetrieval[msg.id] && (
                          <div style={{
                            marginTop: 6, padding: 8, borderRadius: 8,
                            background: 'var(--surface-secondary)', border: '1px solid var(--border)',
                            fontSize: 10,
                          }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, fontFamily: 'var(--font-mono)' }}>
                              <div>
                                <div style={{ color: 'var(--text-muted)' }}>Intent</div>
                                <div style={{ color: 'var(--blue)', fontWeight: 500 }}>{msg.retrieval_metadata.intent || "GENERAL"}</div>
                              </div>
                              <div>
                                <div style={{ color: 'var(--text-muted)' }}>Strategy</div>
                                <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{msg.retrieval_metadata.strategy || "hybrid_rrf"}</div>
                              </div>
                              <div>
                                <div style={{ color: 'var(--text-muted)' }}>Retrieved</div>
                                <div style={{ color: 'var(--text-primary)' }}>{msg.retrieval_metadata.total_retrieved || 0} ({msg.retrieval_metadata.latency_ms || 0}ms)</div>
                              </div>
                            </div>

                            {msg.retrieval_metadata.retrieved_chunks && msg.retrieval_metadata.retrieved_chunks.length > 0 && (
                              <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                                {msg.retrieval_metadata.retrieved_chunks.slice(0, 3).map((chunk: RetrievedChunk, cIdx: number) => (
                                  <div
                                    key={cIdx}
                                    onClick={() => onCitationClick({
                                      file_path: chunk.file_path,
                                      start_line: chunk.start_line,
                                      end_line: chunk.end_line,
                                      symbol_name: chunk.symbol_name,
                                    })}
                                    style={{
                                      padding: '3px 6px', borderRadius: 4,
                                      cursor: 'pointer', display: 'flex',
                                      justifyContent: 'space-between', fontSize: 10,
                                      fontFamily: 'var(--font-mono)',
                                      transition: 'background 80ms',
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-hover)')}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                                  >
                                    <span style={{ color: 'var(--text-primary)' }}>
                                      {chunk.file_path.split("/").pop()}:L{chunk.start_line}-{chunk.end_line}
                                    </span>
                                    <span style={{ color: 'var(--green)', fontWeight: 500 }}>
                                      {chunk.score.toFixed(3)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {loading && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
            <div style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 12, padding: '8px 14px',
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: 12, color: 'var(--text-muted)',
              boxShadow: 'var(--shadow-subtle)',
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--blue)',
              }} className="pulse-ring" />
              <ResponseTimer />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: 12, borderTop: '1px solid var(--border)',
        background: 'var(--surface)', flexShrink: 0,
      }}>
        {/* Context Attachment */}
        {contextAttachment && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '5px 10px', marginBottom: 8,
            borderRadius: 8, background: 'var(--blue-light)',
            border: '1px solid rgba(20,115,230,0.15)',
            fontSize: 11,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--blue)' }}>
              <Paperclip style={{ width: 12, height: 12 }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>
                {contextAttachment.file_path.split("/").pop()} · L{contextAttachment.start_line}–{contextAttachment.end_line}
              </span>
            </div>
            {onRemoveContext && (
              <button
                onClick={onRemoveContext}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text-muted)', display: 'flex',
                }}
              >
                <X style={{ width: 12, height: 12 }} />
              </button>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center',
            border: '1px solid var(--border)', borderRadius: 999,
            padding: '4px 4px 4px 14px',
            background: 'var(--surface)',
            transition: 'border-color 120ms',
          }}>
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!isRepoReady || loading}
              placeholder={!isRepoReady ? "Waiting for indexing..." : "Ask RepoLens..."}
              style={{
                flex: 1, border: 'none', outline: 'none',
                background: 'transparent', resize: 'none',
                fontSize: 13, color: 'var(--text-primary)',
                fontFamily: 'var(--font-sans)',
                lineHeight: 1.4, padding: '4px 0',
                minHeight: 24, maxHeight: 80,
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || !isRepoReady || loading}
              style={{
                width: 30, height: 30, borderRadius: '50%',
                background: input.trim() ? 'var(--blue)' : 'var(--border)',
                border: 'none', cursor: input.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 120ms', flexShrink: 0,
              }}
            >
              <Send style={{ width: 13, height: 13, color: 'white' }} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
