"use client";

import React from "react";
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Network,
  Cpu,
  ShieldCheck,
} from "lucide-react";
import { Repository } from "../types";

interface StatusBarProps {
  currentRepo: Repository | null;
  activeFilePath?: string;
  activeLine?: number;
  onOpenSettings: () => void;
}

export default function StatusBar({
  currentRepo,
  activeFilePath,
  activeLine,
  onOpenSettings,
}: StatusBarProps) {
  const primaryLang =
    currentRepo?.languages && currentRepo.languages.length > 0
      ? currentRepo.languages[0]
      : "Python";

  return (
    <footer className="h-6 border-t border-slate-800/80 bg-[#060911] text-[11px] text-slate-400 px-3 flex items-center justify-between select-none shrink-0 z-30 font-mono">
      {/* Left side: Repo & indexing status */}
      <div className="flex items-center gap-3">
        {currentRepo ? (
          <div className="flex items-center gap-1.5">
            {currentRepo.status?.toLowerCase() === "ready" ? (
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="w-3 h-3" />
                <span>READY</span>
              </span>
            ) : currentRepo.status?.toLowerCase() === "failed" ? (
              <span className="flex items-center gap-1 text-rose-400">
                <AlertCircle className="w-3 h-3" />
                <span>FAILED</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-400 animate-pulse">
                <Clock className="w-3 h-3" />
                <span>{currentRepo.status.toUpperCase()}</span>
              </span>
            )}
            <span className="text-slate-600">|</span>
            <span className="text-slate-300 font-sans font-medium">{currentRepo.name}</span>
          </div>
        ) : (
          <span className="text-slate-500">No repository active</span>
        )}

        {currentRepo && (
          <>
            <span className="text-slate-600">|</span>
            <span className="text-indigo-400 capitalize">{primaryLang}</span>
            <span className="text-slate-600">|</span>
            <span>{currentRepo.stats?.files || 0} Files</span>
            <span className="text-slate-600">|</span>
            <span>{currentRepo.stats?.symbols || 0} Symbols</span>
            <span className="text-slate-600">|</span>
            <span>{currentRepo.stats?.chunks || 0} AST Chunks</span>
            <span className="text-slate-600">|</span>
            <span className="flex items-center gap-1 text-cyan-400">
              <Network className="w-3 h-3" />
              <span>{currentRepo.stats?.graph_nodes || 0} Nodes</span>
            </span>
          </>
        )}
      </div>

      {/* Right side: File coordinates, sandbox safety, provider info */}
      <div className="flex items-center gap-3">
        {activeFilePath && (
          <>
            <span className="text-slate-300 truncate max-w-xs">{activeFilePath}</span>
            {activeLine && <span className="text-indigo-300">Ln {activeLine}</span>}
            <span className="text-slate-600">|</span>
          </>
        )}

        <div className="flex items-center gap-1 text-emerald-400/90 text-[10px]" title="Code is analyzed statically without code execution">
          <ShieldCheck className="w-3 h-3" />
          <span>Static Analysis Sandbox</span>
        </div>

        <span className="text-slate-600">|</span>

        <button
          onClick={onOpenSettings}
          className="flex items-center gap-1 text-slate-400 hover:text-slate-200 transition-colors"
          title="Embeddings: all-MiniLM-L6-v2 · Click for provider settings"
        >
          <Cpu className="w-3 h-3 text-indigo-400" />
          <span>all-MiniLM-L6-v2</span>
        </button>

        <span className="text-slate-500">UTF-8</span>
      </div>
    </footer>
  );
}
