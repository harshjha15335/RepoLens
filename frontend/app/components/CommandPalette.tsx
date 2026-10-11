"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  FileCode,
  Boxes,
  Sparkles,
  Network,
  GraduationCap,
  BarChart3,
  Settings,
  Upload,
  ArrowRight,
} from "lucide-react";
import { ActiveActivityView, FileInfo, SymbolInfo, TutorMode } from "../types";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  files: FileInfo[];
  symbols: SymbolInfo[];
  onSelectFile: (path: string) => void;
  onSelectSymbol: (symbol: SymbolInfo) => void;
  onSelectTutorMode: (mode: TutorMode) => void;
  onNavigateView: (view: ActiveActivityView) => void;
  onOpenUpload: () => void;
  onOpenEvaluation: () => void;
  onOpenSettings: () => void;
  onAskQuestion: (q: string) => void;
}

export default function CommandPalette({
  isOpen,
  onClose,
  files,
  symbols,
  onSelectFile,
  onSelectSymbol,
  onSelectTutorMode,
  onNavigateView,
  onOpenUpload,
  onOpenEvaluation,
  onOpenSettings,
  onAskQuestion,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const timer = window.setTimeout(() => {
      setQuery("");
      setSelectedIndex(0);
      inputRef.current?.focus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isOpen]);

  if (!isOpen) return null;

  // Filter items
  const cleanQ = query.toLowerCase().trim();

  const matchingFiles = cleanQ
    ? files.filter((f) => f.path.toLowerCase().includes(cleanQ)).slice(0, 5)
    : files.slice(0, 4);

  const matchingSymbols = cleanQ
    ? symbols.filter((s) => s.name.toLowerCase().includes(cleanQ) || s.file_path.toLowerCase().includes(cleanQ)).slice(0, 5)
    : symbols.slice(0, 4);

  const actions = [
    {
      id: "mode-beginner",
      title: "Switch Tutor Mode to Beginner",
      category: "Tutor Persona",
      icon: GraduationCap,
      action: () => {
        onSelectTutorMode("beginner");
        onClose();
      },
    },
    {
      id: "mode-developer",
      title: "Switch Tutor Mode to Developer",
      category: "Tutor Persona",
      icon: Sparkles,
      action: () => {
        onSelectTutorMode("developer");
        onClose();
      },
    },
    {
      id: "mode-interview",
      title: "Start Repository Interview",
      category: "Interview",
      icon: GraduationCap,
      action: () => {
        onNavigateView("interview");
        onClose();
      },
    },
    {
      id: "mode-debug",
      title: "Switch Tutor Mode to Debug Investigator",
      category: "Tutor Persona",
      icon: Sparkles,
      action: () => {
        onSelectTutorMode("debug");
        onClose();
      },
    },
    {
      id: "view-graph",
      title: "Open Code Knowledge Graph & Call Flows",
      category: "Navigation",
      icon: Network,
      action: () => {
        onNavigateView("graph");
        onClose();
      },
    },
    {
      id: "view-eval",
      title: "Run RAG Retrieval Evaluation Suite",
      category: "Evaluation",
      icon: BarChart3,
      action: () => {
        onOpenEvaluation();
        onClose();
      },
    },
    {
      id: "import-repo",
      title: "Import Repository (ZIP or Git)",
      category: "Repository",
      icon: Upload,
      action: () => {
        onOpenUpload();
        onClose();
      },
    },
    {
      id: "settings",
      title: "Open Preferences & Settings",
      category: "Preferences",
      icon: Settings,
      action: () => {
        onOpenSettings();
        onClose();
      },
    },
  ].filter(
    (a) => !cleanQ || a.title.toLowerCase().includes(cleanQ) || a.category.toLowerCase().includes(cleanQ)
  );

  // Flatten options for arrow key navigation
  type PaletteEntry =
    | { type: "file"; item: FileInfo; execute: () => void }
    | { type: "symbol"; item: SymbolInfo; execute: () => void }
    | { type: "action"; item: (typeof actions)[number]; execute: () => void }
    | { type: "ask"; item: { query: string }; execute: () => void };
  const allItems: PaletteEntry[] = [];

  matchingFiles.forEach((f) => {
    allItems.push({
      type: "file",
      item: f,
      execute: () => {
        onSelectFile(f.path);
        onClose();
      },
    });
  });

  matchingSymbols.forEach((s) => {
    allItems.push({
      type: "symbol",
      item: s,
      execute: () => {
        onSelectSymbol(s);
        onClose();
      },
    });
  });

  actions.forEach((a) => {
    allItems.push({
      type: "action",
      item: a,
      execute: a.action,
    });
  });

  // If query is non-empty, add an "Ask AI" option
  if (cleanQ) {
    allItems.unshift({
      type: "ask",
      item: { query },
      execute: () => {
        onAskQuestion(query);
        onClose();
      },
    });
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, allItems.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + allItems.length) % Math.max(1, allItems.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (allItems[selectedIndex]) {
        allItems[selectedIndex].execute();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="p-3 border-b border-slate-800 flex items-center gap-3 bg-slate-950/80">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a file name, symbol, question, or action..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          />
          <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400 font-mono border border-slate-700">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 space-y-1">
          {allItems.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No matching files, symbols, or actions found.
            </div>
          ) : (
            allItems.map((entry, idx) => {
              const isSelected = idx === selectedIndex;

              if (entry.type === "ask") {
                return (
                  <div
                    key="ask-ai"
                    onClick={entry.execute}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between p-2.5 rounded-xl cursor-pointer text-xs transition-colors ${
                      isSelected
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "text-indigo-300 hover:bg-slate-800/60"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
                      <span>
                        Ask CodeMentor: &quot;<strong>{query}</strong>&quot;
                      </span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 shrink-0 opacity-80" />
                  </div>
                );
              }

              if (entry.type === "file") {
                const f = entry.item;
                return (
                  <div
                    key={f.id || f.path}
                    onClick={entry.execute}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between p-2 rounded-xl cursor-pointer text-xs transition-colors ${
                      isSelected
                        ? "bg-slate-800 text-white"
                        : "text-slate-300 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FileCode className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      <span className="font-mono text-xs truncate">{f.path}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono uppercase shrink-0">
                      File
                    </span>
                  </div>
                );
              }

              if (entry.type === "symbol") {
                const s = entry.item;
                return (
                  <div
                    key={`${s.name}-${s.file_path}-${s.start_line}`}
                    onClick={entry.execute}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between p-2 rounded-xl cursor-pointer text-xs transition-colors ${
                      isSelected
                        ? "bg-slate-800 text-white"
                        : "text-slate-300 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Boxes className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="font-mono font-medium text-xs truncate">{s.name}</span>
                      <span className="text-[10px] text-slate-500 font-mono truncate">
                        {s.file_path}:L{s.start_line}
                      </span>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.2 rounded font-mono uppercase bg-slate-900 border border-slate-700 text-slate-400 shrink-0">
                      {s.symbol_type}
                    </span>
                  </div>
                );
              }

              if (entry.type === "action") {
                const a = entry.item;
                const Icon = a.icon;
                return (
                  <div
                    key={a.id}
                    onClick={entry.execute}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between p-2 rounded-xl cursor-pointer text-xs transition-colors ${
                      isSelected
                        ? "bg-slate-800 text-white"
                        : "text-slate-300 hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Icon className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      <span>{a.title}</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono shrink-0">
                      {a.category}
                    </span>
                  </div>
                );
              }

              return null;
            })
          )}
        </div>
      </div>
    </div>
  );
}
