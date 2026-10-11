"use client";

import React from "react";
import {
  Folder,
  Search,
  Boxes,
  Network,
  MessageSquare,
  GraduationCap,
  BarChart3,
  Settings,
  Sun,
  Moon,
  Command,
} from "lucide-react";
import { ActiveActivityView, Theme } from "../types";

interface ActivityRailProps {
  activeView: ActiveActivityView;
  onViewChange: (view: ActiveActivityView) => void;
  theme: Theme;
  onToggleTheme: () => void;
  onOpenCommandPalette: () => void;
  onOpenSettings: () => void;
  unreadCount?: number;
}

export default function ActivityRail({
  activeView,
  onViewChange,
  theme,
  onToggleTheme,
  onOpenCommandPalette,
  onOpenSettings,
}: ActivityRailProps) {
  const navItems: {
    id: ActiveActivityView;
    label: string;
    icon: typeof Folder;
    shortcut?: string;
  }[] = [
    { id: "files", label: "Explorer (Files)", icon: Folder, shortcut: "Ctrl+Shift+E" },
    { id: "search", label: "Repository Search", icon: Search, shortcut: "Ctrl+Shift+F" },
    { id: "symbols", label: "AST Symbols", icon: Boxes, shortcut: "Ctrl+Shift+O" },
    { id: "graph", label: "Code Knowledge Graph", icon: Network },
    { id: "interview", label: "Repository Interview", icon: GraduationCap },
    { id: "evaluation", label: "Retrieval Benchmarks", icon: BarChart3 },
  ];

  return (
    <nav
      aria-label="Activity Rail"
      className="w-12 border-r border-slate-800/80 bg-[#060911] flex flex-col items-center py-3 justify-between shrink-0 select-none z-20"
    >
      {/* Top Main Navigation Icons */}
      <div className="flex flex-col items-center gap-1.5 w-full">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              title={`${item.label}${item.shortcut ? ` (${item.shortcut})` : ""}`}
              aria-label={item.label}
              className={`relative w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 shadow-sm"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
              }`}
            >
              <Icon className="w-4 h-4" />
              {isActive && (
                <span className="absolute -left-1.5 top-2 bottom-2 w-1 rounded-r bg-indigo-500" />
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Utility Icons */}
      <div className="flex flex-col items-center gap-1.5 w-full pt-2 border-t border-slate-800/60">
        {/* Command Palette Button */}
        <button
          onClick={onOpenCommandPalette}
          title="Command Palette (Ctrl+K)"
          aria-label="Command Palette"
          className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:bg-slate-800/50 transition-colors"
        >
          <Command className="w-4 h-4" />
        </button>

        {/* Theme Switcher */}
        <button
          onClick={onToggleTheme}
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
          aria-label="Toggle Theme"
          className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-amber-400 hover:bg-slate-800/50 transition-colors"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4" />
          ) : (
            <Moon className="w-4 h-4" />
          )}
        </button>

        {/* Settings Button */}
        <button
          onClick={onOpenSettings}
          title="Settings"
          aria-label="Open Settings"
          className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </nav>
  );
}
