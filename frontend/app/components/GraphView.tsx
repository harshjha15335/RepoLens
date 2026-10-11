"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Network,
  Search,
  Filter,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  FileCode,
  ArrowRight,
  ArrowLeft,
  Boxes,
  Cpu,
  GitFork,
  ExternalLink,
  RefreshCw,
  Sliders,
} from "lucide-react";
import { GraphResponse, GraphNodeData, CallFlowItem, Citation } from "../types";
import { api } from "../lib/api";

interface GraphViewProps {
  repositoryId: string;
  onInspectNode: (citation: Citation) => void;
  onBackToCode: () => void;
}

export default function GraphView({ repositoryId, onInspectNode, onBackToCode }: GraphViewProps) {
  const [tab, setTab] = useState<"graph" | "call_flow">("graph");
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [callFlows, setCallFlows] = useState<CallFlowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [edgeTypeFilter, setEdgeTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [zoomLevel, setZoomLevel] = useState(1);

  // Load graph and call flows
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [graph, flows] = await Promise.all([
          api.getGraph(repositoryId, nodeTypeFilter, edgeTypeFilter, 250),
          api.getCallFlows(repositoryId),
        ]);
        if (cancelled) return;
        setGraphData(graph);
        setCallFlows(flows.flows || []);
        setSelectedNode((current) => graph.nodes.find((node) => node.id === current?.id) || graph.nodes[0] || null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Unable to load graph");
        console.error("Failed to load graph data:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [repositoryId, nodeTypeFilter, edgeTypeFilter]);

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    if (!graphData) return [];
    return graphData.nodes.filter((n) => {
      const matchSearch =
        !searchQuery.trim() ||
        n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.qualified_name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchType =
        nodeTypeFilter === "all" || n.type.toLowerCase() === nodeTypeFilter.toLowerCase();
      return matchSearch && matchType;
    });
  }, [graphData, searchQuery, nodeTypeFilter]);

  const getNodeBadge = (type: string) => {
    switch (type.toLowerCase()) {
      case "class":
        return { bg: "#f3e8ff", color: "#7e22ce", border: "#e9d5ff" };
      case "function":
        return { bg: "#eff6ff", color: "#1d4ed8", border: "#dbeafe" };
      case "method":
        return { bg: "#fffbeb", color: "#b45309", border: "#fef3c7" };
      case "file":
        return { bg: "#f0fdf4", color: "#15803d", border: "#dcfce7" };
      default:
        return { bg: "#f3f4f6", color: "#4b5563", border: "#e5e7eb" };
    }
  };

  const getEdgeBadge = (type: string) => {
    switch (type.toUpperCase()) {
      case "CALLS":
        return { bg: "#ecfeff", color: "#0e7490", border: "#cffafe" };
      case "INHERITS":
        return { bg: "#f5f3ff", color: "#6d28d9", border: "#ede9fe" };
      case "IMPORTS":
        return { bg: "#eef2ff", color: "#4338ca", border: "#e0e7ff" };
      case "CONTAINS":
        return { bg: "#f8fafc", color: "#475569", border: "#e2e8f0" };
      default:
        return { bg: "#f9fafb", color: "#6b7280", border: "#e5e7eb" };
    }
  };

  return (
    <div
      className="graph-view"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: "100%",
        background: "var(--surface)",
        overflow: "hidden",
        userSelect: "none",
      }}
    >
      {/* ─── Top Toolbar ─── */}
      <div
        className="graph-toolbar"
        style={{
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, minWidth: 0 }}>
          <button type="button" onClick={onBackToCode} className="graph-back-button">
            <ArrowLeft size={14} /> Back to code
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Network style={{ width: 16, height: 16, color: "var(--blue)" }} />
            <h2 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
              Code Knowledge Graph
            </h2>
          </div>

          {/* View Tab Toggle */}
          <div
            style={{
              display: "flex",
              background: "#f3f4f6",
              padding: 2,
              borderRadius: 8,
              border: "1px solid var(--border)",
            }}
          >
            <button
              onClick={() => setTab("graph")}
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                border: "none",
                cursor: "pointer",
                transition: "all 120ms",
                background: tab === "graph" ? "var(--surface)" : "transparent",
                color: tab === "graph" ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === "graph" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              Graph Explorer ({graphData?.nodes?.length || 0})
            </button>
            <button
              onClick={() => setTab("call_flow")}
              style={{
                padding: "3px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                border: "none",
                cursor: "pointer",
                transition: "all 120ms",
                background: tab === "call_flow" ? "var(--surface)" : "transparent",
                color: tab === "call_flow" ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === "call_flow" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              Call Flows ({callFlows.length})
            </button>
          </div>
        </div>

        {tab === "graph" && (
          <div className="graph-filters" style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, minWidth: 0 }}>
            {/* Search */}
            <div className="graph-search" style={{ position: "relative" }}>
              <Search
                style={{
                  width: 13,
                  height: 13,
                  color: "var(--text-muted)",
                  position: "absolute",
                  left: 9,
                  top: "50%",
                  transform: "translateY(-50%)",
                }}
              />
              <input
                type="text"
                placeholder="Find node in graph..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  height: 30,
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  paddingLeft: 28,
                  paddingRight: 8,
                  fontSize: 12,
                  color: "var(--text-primary)",
                  outline: "none",
                }}
              />
            </div>

            {/* Node type filter */}
            <select
              value={nodeTypeFilter}
              onChange={(e) => setNodeTypeFilter(e.target.value)}
              style={{
                height: 30,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "0 8px",
                fontSize: 12,
                color: "var(--text-primary)",
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="all">All Node Types</option>
              <option value="class">Classes</option>
              <option value="function">Functions</option>
              <option value="method">Methods</option>
              <option value="file">Files</option>
            </select>

            {/* Relationship filter */}
            <select
              value={edgeTypeFilter}
              onChange={(e) => setEdgeTypeFilter(e.target.value)}
              style={{
                height: 30,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "0 8px",
                fontSize: 12,
                color: "var(--text-primary)",
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="all">All Relationships</option>
              <option value="CALLS">Calls</option>
              <option value="INHERITS">Inherits</option>
              <option value="IMPORTS">Imports</option>
              <option value="CONTAINS">Contains</option>
            </select>

            {/* Zoom Controls */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "#f3f4f6",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 1,
              }}
            >
              <button
                onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.15))}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "4px 6px",
                  display: "flex",
                  color: "var(--text-secondary)",
                }}
                title="Zoom Out"
              >
                <ZoomOut style={{ width: 13, height: 13 }} />
              </button>
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", padding: "0 4px", color: "var(--text-secondary)" }}>
                {Math.round(zoomLevel * 100)}%
              </span>
              <button
                onClick={() => setZoomLevel((z) => Math.min(1.8, z + 0.15))}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "4px 6px",
                  display: "flex",
                  color: "var(--text-secondary)",
                }}
                title="Zoom In"
              >
                <ZoomIn style={{ width: 13, height: 13 }} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ─── Main View Area ─── */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {error ? (
          <div role="alert" style={{ padding: 24, color: "var(--text-secondary)" }}>{error}</div>
        ) : loading ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-muted)",
              fontSize: 13,
            }}
          >
            <RefreshCw style={{ width: 24, height: 24, animation: "spin 1s linear infinite", color: "var(--blue)", marginBottom: 8 }} />
            <span>Rendering code knowledge graph...</span>
          </div>
        ) : tab === "graph" ? (
          <div className="graph-body" style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", overflow: "hidden" }}>
            {/* Visual Graph Canvas - Spacious with Auto-Fit Grid (guaranteed min-width 240px per node) */}
            <div
              className="graph-canvas dotted-grid"
              style={{
                flex: 1,
                minWidth: 0,
                minHeight: 0,
                overflow: "auto",
                padding: 20,
                background: "#fafafa",
              }}
            >
              <div
                style={{
                  transform: `scale(${zoomLevel})`,
                  transformOrigin: "top left",
                  transition: "transform 150ms ease",
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                  gap: 14,
                  minWidth: "100%",
                }}
              >
                {filteredNodes.length === 0 ? (
                  <div style={{ gridColumn: "1 / -1", padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
                    No nodes match current filters.
                  </div>
                ) : (
                  filteredNodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id;
                    const badge = getNodeBadge(node.type);
                    const fileName = node.file_path ? node.file_path.split("/").pop() : "";

                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        style={{
                          padding: 12,
                          borderRadius: 12,
                          background: "#ffffff",
                          border: isSelected ? "2px solid var(--blue)" : "1px solid var(--border)",
                          boxShadow: isSelected
                            ? "0 4px 16px rgba(20, 115, 230, 0.18)"
                            : "0 1px 3px rgba(0, 0, 0, 0.04)",
                          cursor: "pointer",
                          transition: "all 120ms ease",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          minWidth: 230,
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) {
                            e.currentTarget.style.borderColor = "#cbd5e1";
                            e.currentTarget.style.boxShadow = "0 3px 8px rgba(0,0,0,0.06)";
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) {
                            e.currentTarget.style.borderColor = "var(--border)";
                            e.currentTarget.style.boxShadow = "0 1px 3px rgba(0, 0, 0, 0.04)";
                          }
                        }}
                      >
                        {/* Top: Type badge & File */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              textTransform: "uppercase",
                              fontFamily: "var(--font-mono)",
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: badge.bg,
                              color: badge.color,
                              border: `1px solid ${badge.border}`,
                            }}
                          >
                            {node.type}
                          </span>

                          {fileName && (
                            <span
                              style={{
                                fontSize: 11,
                                fontFamily: "var(--font-mono)",
                                color: "var(--text-muted)",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                maxWidth: 120,
                              }}
                            >
                              {fileName}
                            </span>
                          )}
                        </div>

                        {/* Name */}
                        <h4
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 13,
                            fontWeight: 600,
                            color: "var(--text-primary)",
                            margin: "2px 0 0 0",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {node.name}
                        </h4>

                        {/* Line coordinates & Selection indicator */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: 11,
                            fontFamily: "var(--font-mono)",
                            color: "var(--text-secondary)",
                            marginTop: 2,
                          }}
                        >
                          <span>
                            {node.start_line ? `L${node.start_line}-${node.end_line}` : "Global"}
                          </span>
                          <span style={{ color: isSelected ? "var(--blue)" : "var(--text-muted)", fontSize: 11, fontWeight: 500 }}>
                            {isSelected ? "Selected ✓" : "Inspect →"}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Side: Selected Node Inspector Panel */}
            <div
              className="graph-inspector"
              style={{
                borderLeft: "1px solid var(--border)",
                background: "var(--surface)",
                padding: 16,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                flexShrink: 0,
                overflowY: "auto",
              }}
            >
              {selectedNode ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <div>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: "var(--font-mono)",
                        textTransform: "uppercase",
                        color: "var(--text-muted)",
                        letterSpacing: "0.05em",
                        fontWeight: 600,
                      }}
                    >
                      Selected Node Details
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, minWidth: 0 }}>
                      <h3
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 15,
                          fontWeight: 700,
                          color: "var(--text-primary)",
                          margin: 0,
                          minWidth: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {selectedNode.name}
                      </h3>
                      {(() => {
                        const badge = getNodeBadge(selectedNode.type);
                        return (
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 700,
                              fontFamily: "var(--font-mono)",
                              textTransform: "uppercase",
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: badge.bg,
                              color: badge.color,
                              border: `1px solid ${badge.border}`,
                              flexShrink: 0,
                            }}
                          >
                            {selectedNode.type}
                          </span>
                        );
                      })()}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: 12,
                      borderRadius: 10,
                      background: "#f8fafc",
                      border: "1px solid var(--border)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                    }}
                  >
                    <div>
                      <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>
                        Qualified Name
                      </span>
                      <span style={{ color: "var(--blue)", fontSize: 11, wordBreak: "break-all", fontWeight: 500 }}>
                        {selectedNode.qualified_name}
                      </span>
                    </div>

                    {selectedNode.file_path && (
                      <div>
                        <span style={{ color: "var(--text-muted)", fontSize: 10, display: "block" }}>
                          File Coordinates
                        </span>
                        <span style={{ color: "var(--text-primary)", fontSize: 11, overflowWrap: "anywhere" }}>
                          {selectedNode.file_path}:L{selectedNode.start_line}-{selectedNode.end_line}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Connected Relationships */}
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8, display: "block" }}>
                      Connected Relationships:
                    </span>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {graphData?.edges
                        .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                        .map((edge, idx) => {
                          const isSource = edge.source === selectedNode.id;
                          const connectedNode = graphData?.nodes.find((node) => node.id === (isSource ? edge.target : edge.source));
                          const edgeBadge = getEdgeBadge(edge.type);
                          return (
                            <button
                              type="button"
                              key={edge.id || idx}
                              disabled={!connectedNode}
                              onClick={() => connectedNode && setSelectedNode(connectedNode)}
                              title={connectedNode?.qualified_name}
                              style={{
                                padding: "6px 8px",
                                borderRadius: 8,
                                background: "#f8fafc",
                                border: "1px solid var(--border)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                fontSize: 11,
                                gap: 8,
                                textAlign: "left",
                                cursor: connectedNode ? "pointer" : "default",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: 9,
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  fontFamily: "var(--font-mono)",
                                  textTransform: "uppercase",
                                  fontWeight: 600,
                                  background: edgeBadge.bg,
                                  color: edgeBadge.color,
                                  border: `1px solid ${edgeBadge.border}`,
                                }}
                              >
                                {edge.type}
                              </span>
                              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", fontSize: 10, overflowWrap: "anywhere" }}>
                                {isSource ? "→ " : "← "}{connectedNode?.name || "Unavailable node"}
                              </span>
                            </button>
                          );
                        })}
                    </div>
                  </div>

                  {/* Action to Jump to Source Code */}
                  {selectedNode.file_path && selectedNode.start_line && (
                    <button
                      onClick={() =>
                        onInspectNode({
                          file_path: selectedNode.file_path!,
                          start_line: selectedNode.start_line!,
                          end_line: selectedNode.end_line || selectedNode.start_line!,
                          symbol_name: selectedNode.name,
                        })
                      }
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 6,
                        padding: "9px 14px",
                        borderRadius: 10,
                        background: "var(--blue)",
                        color: "white",
                        border: "none",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        boxShadow: "0 2px 6px rgba(20,115,230,0.25)",
                        transition: "background 120ms",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--blue-hover)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--blue)")}
                    >
                      <FileCode style={{ width: 14, height: 14 }} />
                      <span>Inspect in Code Viewer</span>
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 12 }}>
                  Click any node on the canvas to inspect its relationships and dependencies.
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Call Flows & Chains Tab */
          <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
            <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: 12 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
                Static Call Flow & Hierarchy Traces
              </h3>

              {callFlows.length === 0 ? (
                <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 12 }}>
                  No static call flow edges detected.
                </div>
              ) : (
                callFlows.map((flow) => {
                  const edgeBadge = getEdgeBadge(flow.relationship);
                  return (
                    <div
                      key={flow.id}
                      style={{
                        padding: 12,
                        borderRadius: 10,
                        background: "#ffffff",
                        border: "1px solid var(--border)",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        fontSize: 12,
                      }}
                    >
                      {/* Caller */}
                      <div
                        onClick={() =>
                          flow.caller.file_path &&
                          flow.caller.start_line &&
                          onInspectNode({
                            file_path: flow.caller.file_path,
                            start_line: flow.caller.start_line,
                            end_line: flow.caller.end_line || flow.caller.start_line,
                            symbol_name: flow.caller.name,
                          })
                        }
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          cursor: "pointer",
                          maxWidth: "40%",
                        }}
                      >
                        <div
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 8,
                            background: "#eef2ff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#4338ca",
                            flexShrink: 0,
                          }}
                        >
                          <Boxes style={{ width: 14, height: 14 }} />
                        </div>
                        <div style={{ overflow: "hidden" }}>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontWeight: 600,
                              color: "var(--text-primary)",
                              display: "block",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {flow.caller.name}
                          </span>
                          <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", display: "block" }}>
                            {flow.caller.file_path}:L{flow.caller.start_line}
                          </span>
                        </div>
                      </div>

                      {/* Relationship Badge */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "0 16px" }}>
                        <span
                          style={{
                            fontSize: 9,
                            padding: "2px 8px",
                            borderRadius: 999,
                            fontFamily: "var(--font-mono)",
                            textTransform: "uppercase",
                            fontWeight: 700,
                            background: edgeBadge.bg,
                            color: edgeBadge.color,
                            border: `1px solid ${edgeBadge.border}`,
                          }}
                        >
                          {flow.relationship}
                        </span>
                        <ArrowRight style={{ width: 14, height: 14, color: "var(--text-muted)", marginTop: 4 }} />
                      </div>

                      {/* Callee */}
                      <div
                        onClick={() =>
                          flow.callee.file_path &&
                          flow.callee.start_line &&
                          onInspectNode({
                            file_path: flow.callee.file_path,
                            start_line: flow.callee.start_line,
                            end_line: flow.callee.end_line || flow.callee.start_line,
                            symbol_name: flow.callee.name,
                          })
                        }
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          cursor: "pointer",
                          maxWidth: "40%",
                        }}
                      >
                        <div style={{ textAlign: "right", overflow: "hidden" }}>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontWeight: 600,
                              color: "var(--text-primary)",
                              display: "block",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {flow.callee.name}
                          </span>
                          <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", display: "block" }}>
                            {flow.callee.file_path}:L{flow.callee.start_line}
                          </span>
                        </div>
                        <div
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 8,
                            background: "#ecfeff",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#0e7490",
                            flexShrink: 0,
                          }}
                        >
                          <Boxes style={{ width: 14, height: 14 }} />
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
