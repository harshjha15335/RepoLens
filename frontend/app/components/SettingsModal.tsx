"use client";

import { Settings, X } from "lucide-react";
import { TutorMode } from "../types";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultTutorMode: TutorMode;
  onSetDefaultTutorMode: (mode: TutorMode) => void;
  fontSize: number;
  onSetFontSize: (size: number) => void;
}

export default function SettingsModal({
  isOpen,
  onClose,
  defaultTutorMode,
  onSetDefaultTutorMode,
  fontSize,
  onSetFontSize,
}: SettingsModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="presentation"
      style={{
        position: "fixed", inset: 0, zIndex: 50, display: "flex",
        alignItems: "center", justifyContent: "center", padding: 16,
        background: "rgba(10, 25, 45, 0.4)", backdropFilter: "blur(4px)",
      }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="slide-up"
        style={{
          width: "100%", maxWidth: 540, borderRadius: 20,
          background: "var(--surface)", border: "1px solid var(--border)",
          boxShadow: "0 24px 60px rgba(0, 0, 0, 0.15)", overflow: "hidden",
        }}
      >
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--blue)" }}>
              <Settings size={16} />
            </div>
            <h3 id="settings-title" style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>Settings & Preferences</h3>
          </div>
          <button type="button" aria-label="Close settings" onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", padding: 6, borderRadius: 6, color: "var(--text-muted)", display: "flex" }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Editor Font Size</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <button type="button" aria-label="Decrease editor font size" onClick={() => onSetFontSize(Math.max(11, fontSize - 1))} style={sizeButtonStyle}>−</button>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, minWidth: 36, textAlign: "center" }}>{fontSize}px</span>
              <button type="button" aria-label="Increase editor font size" onClick={() => onSetFontSize(Math.min(20, fontSize + 1))} style={sizeButtonStyle}>+</button>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
            <label htmlFor="settings-tutor-mode" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Tutor Mode</label>
            <select
              id="settings-tutor-mode"
              value={defaultTutorMode}
              onChange={(event) => onSetDefaultTutorMode(event.target.value as TutorMode)}
              style={{ height: 32, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "0 10px", fontSize: 12, color: "var(--text-primary)" }}
            >
              <option value="beginner">Beginner</option>
              <option value="developer">Developer</option>
              <option value="interview">Interview</option>
              <option value="debug">Debug</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}

const sizeButtonStyle = {
  width: 28, height: 28, borderRadius: 6, background: "#f3f4f6",
  border: "1px solid var(--border)", cursor: "pointer", fontSize: 14, fontWeight: 600,
};
