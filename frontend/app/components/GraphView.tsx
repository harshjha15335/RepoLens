"use client";

import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  Network,
  Search,
  ZoomIn,
  ZoomOut,
  FileCode,
  ArrowLeft,
  Boxes,
  RefreshCw,
  Maximize2,
  GitFork,
  Compass,
} from "lucide-react";
import { GraphResponse, GraphNodeData, CallFlowItem, Citation } from "../types";
import { api } from "../lib/api";

interface GraphViewProps {
  repositoryId: string;
  onInspectNode: (citation: Citation) => void;
  onBackToCode: () => void;
}

interface NodePosition {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const NODE_WIDTH = 170;
const NODE_HEIGHT = 44;

export default function GraphView({ repositoryId, onInspectNode, onBackToCode }: GraphViewProps) {
  const [tab, setTab] = useState<"visual" | "cards" | "call_flow">("visual");
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [callFlows, setCallFlows] = useState<CallFlowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [edgeTypeFilter, setEdgeTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Canvas pan & zoom state
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Interactive node positions & dragging state
  const [nodePositions, setNodePositions] = useState<Map<string, { x: number; y: number }>>(new Map());
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const svgRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

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

  // Filtered nodes based on search and type
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

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  // Filtered edges based on visible nodes and relationship type
  const filteredEdges = useMemo(() => {
    if (!graphData) return [];
    return graphData.edges.filter((e) => {
      const bothVisible = visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target);
      const matchRel = edgeTypeFilter === "all" || e.type.toUpperCase() === edgeTypeFilter.toUpperCase();
      return bothVisible && matchRel;
    });
  }, [graphData, visibleNodeIds, edgeTypeFilter]);

  // Compute force-directed positions when nodes change
  useEffect(() => {
    if (filteredNodes.length === 0) {
      setNodePositions(new Map());
      return;
    }

    const width = containerRef.current?.clientWidth || 900;
    const height = containerRef.current?.clientHeight || 600;
    const cx = width / 2;
    const cy = height / 2;

    const positions = new Map<string, NodePosition>();
    const n = filteredNodes.length;
    const radius = Math.min(width, height) * 0.38;

    filteredNodes.forEach((node, i) => {
      const angle = (i / n) * 2 * Math.PI;
      const r = radius * (0.65 + 0.35 * ((i % 4) / 3));
      positions.set(node.id, {
        x: cx + r * Math.cos(angle) + (Math.sin(i * 3) * 30),
        y: cy + r * Math.sin(angle) + (Math.cos(i * 3) * 30),
        vx: 0,
        vy: 0,
      });
    });

    const k = Math.max(140, Math.sqrt((width * height) / Math.max(n, 1)) * 0.75);
    const nodeIds = filteredNodes.map((node) => node.id);

    // Iterative spring simulation
    for (let iter = 0; iter < 70; iter++) {
      const temp = (1 - iter / 70) * 0.85;

      // Repulsion between all node pairs
      for (let i = 0; i < n; i++) {
        const id1 = nodeIds[i];
        const p1 = positions.get(id1)!;
        for (let j = i + 1; j < n; j++) {
          const id2 = nodeIds[j];
          const p2 = positions.get(id2)!;
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 420) {
            const force = (k * k) / dist;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            p1.vx += fx;
            p1.vy += fy;
            p2.vx -= fx;
            p2.vy -= fy;
          }
        }
      }

      // Attraction along connected edges
      filteredEdges.forEach((edge) => {
        const p1 = positions.get(edge.source);
        const p2 = positions.get(edge.target);
        if (!p1 || !p2) return;
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist * dist) / k;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        p1.vx += fx;
        p1.vy += fy;
        p2.vx -= fx;
        p2.vy -= fy;
      });

      // Centering gravity & damping update
      filteredNodes.forEach((node) => {
        const p = positions.get(node.id)!;
        p.vx += (cx - p.x) * 0.035;
        p.vy += (cy - p.y) * 0.035;

        p.x += Math.max(-45, Math.min(45, p.vx * 0.03 * temp));
        p.y += Math.max(-45, Math.min(45, p.vy * 0.03 * temp));
        p.vx *= 0.55;
        p.vy *= 0.55;
      });
    }

    const finalPos = new Map<string, { x: number; y: number }>();
    positions.forEach((pos, id) => {
      finalPos.set(id, { x: Math.round(pos.x), y: Math.round(pos.y) });
    });

    setNodePositions(finalPos);
    setPan({ x: 0, y: 0 });
    setZoomLevel(1);
  }, [filteredNodes, filteredEdges]);

  // Set of connected neighbor node IDs for the currently selected node
  const connectedNodeIds = useMemo(() => {
    if (!selectedNode || !graphData) return new Set<string>();
    const set = new Set<string>();
    graphData.edges.forEach((edge) => {
      if (edge.source === selectedNode.id) set.add(edge.target);
      if (edge.target === selectedNode.id) set.add(edge.source);
    });
    return set;
  }, [selectedNode, graphData]);

  // Color & Badge Tokens
  const getNodeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case "class":
        return {
          bg: "#faf5ff",
          border: "#c084fc",
          accent: "#9333ea",
          text: "#581c87",
          tagBg: "#f3e8ff",
          tagText: "#7e22ce",
        };
      case "function":
        return {
          bg: "#f0f9ff",
          border: "#60a5fa",
          accent: "#2563eb",
          text: "#1e3a8a",
          tagBg: "#eff6ff",
          tagText: "#1d4ed8",
        };
      case "method":
        return {
          bg: "#fffbeb",
          border: "#fbbf24",
          accent: "#d97706",
          text: "#78350f",
          tagBg: "#fef3c7",
          tagText: "#b45309",
        };
      case "file":
        return {
          bg: "#f0fdf4",
          border: "#4ade80",
          accent: "#16a34a",
          text: "#14532d",
          tagBg: "#dcfce7",
          tagText: "#15803d",
        };
      default:
        return {
          bg: "#f8fafc",
          border: "#94a3b8",
          accent: "#64748b",
          text: "#0f172a",
          tagBg: "#f1f5f9",
          tagText: "#475569",
        };
    }
  };

  const getEdgeStyle = (type: string) => {
    switch (type.toUpperCase()) {
      case "CALLS":
        return { stroke: "#0284c7", strokeDash: "none", width: 2, labelBg: "#e0f2fe", labelText: "#0369a1" };
      case "INHERITS":
        return { stroke: "#9333ea", strokeDash: "5 3", width: 2, labelBg: "#f3e8ff", labelText: "#7e22ce" };
      case "IMPORTS":
        return { stroke: "#4f46e5", strokeDash: "4 4", width: 1.8, labelBg: "#e0e7ff", labelText: "#3730a3" };
      case "CONTAINS":
        return { stroke: "#94a3b8", strokeDash: "2 3", width: 1.5, labelBg: "#f1f5f9", labelText: "#475569" };
      default:
        return { stroke: "#cbd5e1", strokeDash: "none", width: 1.5, labelBg: "#f8fafc", labelText: "#64748b" };
    }
  };

  // Canvas Panning Handlers
  const handleMouseDownCanvas = (e: React.MouseEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMoveCanvas = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (draggingNodeId) {
        const svg = svgRef.current;
        if (!svg) return;
        const rect = svg.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - pan.x) / zoomLevel;
        const mouseY = (e.clientY - rect.top - pan.y) / zoomLevel;
        setNodePositions((prev) => {
          const next = new Map(prev);
          next.set(draggingNodeId, {
            x: Math.round(mouseX - dragOffset.x),
            y: Math.round(mouseY - dragOffset.y),
          });
          return next;
        });
      } else if (isPanning) {
        setPan({
          x: e.clientX - panStart.x,
          y: e.clientY - panStart.y,
        });
      }
    },
    [draggingNodeId, dragOffset, isPanning, pan.x, pan.y, panStart.x, panStart.y, zoomLevel]
  );

  const handleMouseUpCanvas = () => {
    setIsPanning(false);
    setDraggingNodeId(null);
  };

  // Zoom via wheel
  const handleWheel = (e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoomLevel((z) => Math.min(2.5, Math.max(0.35, Math.round(z * factor * 100) / 100)));
  };

  // Fit graph to view
  const handleFitToView = () => {
    if (filteredNodes.length === 0 || nodePositions.size === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodePositions.forEach((pos) => {
      minX = Math.min(minX, pos.x - NODE_WIDTH / 2);
      maxX = Math.max(maxX, pos.x + NODE_WIDTH / 2);
      minY = Math.min(minY, pos.y - NODE_HEIGHT / 2);
      maxY = Math.max(maxY, pos.y + NODE_HEIGHT / 2);
    });

    const containerWidth = containerRef.current?.clientWidth || 900;
    const containerHeight = containerRef.current?.clientHeight || 600;
    const graphWidth = Math.max(100, maxX - minX + 120);
    const graphHeight = Math.max(100, maxY - minY + 120);

    const fitZoom = Math.min(1.5, Math.max(0.4, Math.min(containerWidth / graphWidth, containerHeight / graphHeight)));
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    setZoomLevel(Math.round(fitZoom * 100) / 100);
    setPan({
      x: containerWidth / 2 - centerX * fitZoom,
      y: containerHeight / 2 - centerY * fitZoom,
    });
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
      {/* Top Toolbar */}
      <div
        className="graph-toolbar"
        style={{
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
          padding: "8px 14px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 10, minWidth: 0 }}>
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
              onClick={() => setTab("visual")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "4px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                transition: "all 120ms",
                background: tab === "visual" ? "var(--surface)" : "transparent",
                color: tab === "visual" ? "var(--blue)" : "var(--text-secondary)",
                boxShadow: tab === "visual" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              <Compass size={13} />
              Interactive Graph ({graphData?.nodes?.length || 0})
            </button>
            <button
              onClick={() => setTab("cards")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "4px 10px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 500,
                border: "none",
                cursor: "pointer",
                transition: "all 120ms",
                background: tab === "cards" ? "var(--surface)" : "transparent",
                color: tab === "cards" ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: tab === "cards" ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              <Boxes size={13} />
              Card Explorer
            </button>
            <button
              onClick={() => setTab("call_flow")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 5,
                padding: "4px 10px",
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
              <GitFork size={13} />
              Call Flows ({callFlows.length})
            </button>
          </div>
        </div>

        {/* Filters and Controls */}
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, minWidth: 0 }}>
          {/* Search Node */}
          <div style={{ position: "relative" }}>
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
                height: 28,
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 7,
                paddingLeft: 27,
                paddingRight: 8,
                fontSize: 12,
                color: "var(--text-primary)",
                outline: "none",
                width: 155,
              }}
            />
          </div>

          {/* Node type filter */}
          <select
            value={nodeTypeFilter}
            onChange={(e) => setNodeTypeFilter(e.target.value)}
            style={{
              height: 28,
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 7,
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
              height: 28,
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 7,
              padding: "0 8px",
              fontSize: 12,
              color: "var(--text-primary)",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="all">All Relationships</option>
            <option value="CONTAINS">CONTAINS</option>
            <option value="IMPORTS">IMPORTS</option>
            <option value="CALLS">CALLS</option>
            <option value="INHERITS">INHERITS</option>
          </select>

          {/* Canvas Zoom Controls (for Visual Graph) */}
          {tab === "visual" && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 2,
                background: "#f8fafc",
                border: "1px solid var(--border)",
                borderRadius: 7,
                padding: 1,
              }}
            >
              <button
                type="button"
                title="Zoom out"
                onClick={() => setZoomLevel((z) => Math.max(0.35, Math.round((z - 0.15) * 100) / 100))}
                style={{
                  width: 26,
                  height: 26,
                  border: "none",
                  background: "transparent",
                  borderRadius: 5,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--text-secondary)",
                }}
              >
                <ZoomOut size={13} />
              </button>
              <button
                type="button"
                title="Reset zoom"
                onClick={() => { setZoomLevel(1); setPan({ x: 0, y: 0 }); }}
                style={{
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  border: "none",
                  background: "transparent",
                  padding: "0 6px",
                  cursor: "pointer",
                  color: "var(--text-primary)",
                }}
              >
                {Math.round(zoomLevel * 100)}%
              </button>
              <button
                type="button"
                title="Zoom in"
                onClick={() => setZoomLevel((z) => Math.min(2.5, Math.round((z + 0.15) * 100) / 100))}
                style={{
                  width: 26,
                  height: 26,
                  border: "none",
                  background: "transparent",
                  borderRadius: 5,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--text-secondary)",
                }}
              >
                <ZoomIn size={13} />
              </button>
              <button
                type="button"
                title="Fit graph to view"
                onClick={handleFitToView}
                style={{
                  width: 26,
                  height: 26,
                  border: "none",
                  background: "transparent",
                  borderRadius: 5,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--text-secondary)",
                  marginLeft: 2,
                }}
              >
                <Maximize2 size={12} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main View Area */}
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
            <span>Generating interactive code knowledge graph...</span>
          </div>
        ) : tab === "visual" ? (
          /* ======================================================== */
          /* Interactive Visual Node & Edge Graph Canvas              */
          /* ======================================================== */
          <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", overflow: "hidden", position: "relative" }}>
            <div
              ref={containerRef}
              style={{
                flex: 1,
                minWidth: 0,
                minHeight: 0,
                position: "relative",
                overflow: "hidden",
                background: "#f8fafc",
                cursor: isPanning ? "grabbing" : "grab",
              }}
            >
              <svg
                ref={svgRef}
                style={{ width: "100%", height: "100%", display: "block" }}
                onMouseDown={handleMouseDownCanvas}
                onMouseMove={handleMouseMoveCanvas}
                onMouseUp={handleMouseUpCanvas}
                onMouseLeave={handleMouseUpCanvas}
                onWheel={handleWheel}
              >
                {/* SVG Definitions for Arrowheads and Grid */}
                <defs>
                  {/* Subtle dot grid pattern */}
                  <pattern id="grid-dots" width="24" height="24" patternUnits="userSpaceOnUse">
                    <circle cx="12" cy="12" r="1.2" fill="#cbd5e1" />
                  </pattern>

                  {/* Arrow markers per relationship */}
                  <marker id="arrow-CALLS" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="#0284c7" />
                  </marker>
                  <marker id="arrow-IMPORTS" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="#4f46e5" />
                  </marker>
                  <marker id="arrow-INHERITS" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="#9333ea" />
                  </marker>
                  <marker id="arrow-CONTAINS" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8.5 5 L 0 8.5 z" fill="#94a3b8" />
                  </marker>
                </defs>

                {/* Background Grid */}
                <rect width="100%" height="100%" fill="url(#grid-dots)" />

                {/* Transform Group for Pan and Zoom */}
                <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoomLevel})`}>
                  {/* 1. EDGES */}
                  {filteredEdges.map((edge) => {
                    const p1 = nodePositions.get(edge.source);
                    const p2 = nodePositions.get(edge.target);
                    if (!p1 || !p2) return null;

                    const isConnectedToSelected =
                      selectedNode && (edge.source === selectedNode.id || edge.target === selectedNode.id);
                    const hasSelection = Boolean(selectedNode);
                    const opacity = hasSelection ? (isConnectedToSelected ? 1 : 0.15) : 0.85;

                    const style = getEdgeStyle(edge.type);

                    // Compute curved quadratic bezier
                    const midX = (p1.x + p2.x) / 2;
                    const midY = (p1.y + p2.y) / 2;
                    const dx = p2.x - p1.x;
                    const dy = p2.y - p1.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const curveOffset = Math.min(25, dist * 0.1);
                    const ctrlX = midX - (dy / dist) * curveOffset;
                    const ctrlY = midY + (dx / dist) * curveOffset;

                    const markerId = `arrow-${edge.type.toUpperCase()}`;

                    return (
                      <g key={edge.id || `${edge.source}-${edge.target}`} style={{ opacity, transition: "opacity 150ms ease" }}>
                        {/* Edge line */}
                        <path
                          d={`M ${p1.x} ${p1.y} Q ${ctrlX} ${ctrlY} ${p2.x} ${p2.y}`}
                          fill="none"
                          stroke={style.stroke}
                          strokeWidth={isConnectedToSelected ? style.width + 1 : style.width}
                          strokeDasharray={style.strokeDash}
                          markerEnd={`url(#${markerId})`}
                        />
                        {/* Edge Relationship Label */}
                        <g transform={`translate(${ctrlX}, ${ctrlY})`}>
                          <rect
                            x={-24}
                            y={-8}
                            width={48}
                            height={16}
                            rx={4}
                            fill={style.labelBg}
                            stroke={style.stroke}
                            strokeWidth={0.8}
                          />
                          <text
                            x={0}
                            y={3}
                            textAnchor="middle"
                            fontSize={8}
                            fontWeight={700}
                            fontFamily="var(--font-mono)"
                            fill={style.labelText}
                          >
                            {edge.type}
                          </text>
                        </g>
                      </g>
                    );
                  })}

                  {/* 2. NODES */}
                  {filteredNodes.map((node) => {
                    const pos = nodePositions.get(node.id);
                    if (!pos) return null;

                    const isSelected = selectedNode?.id === node.id;
                    const isConnected = connectedNodeIds.has(node.id);
                    const hasSelection = Boolean(selectedNode);
                    const isSearchMatch =
                      searchQuery.trim().length > 0 &&
                      (node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        node.qualified_name.toLowerCase().includes(searchQuery.toLowerCase()));

                    const opacity = hasSelection ? (isSelected || isConnected ? 1 : 0.3) : 1;
                    const color = getNodeColor(node.type);

                    const handleNodeMouseDown = (e: React.MouseEvent) => {
                      e.stopPropagation();
                      setSelectedNode(node);
                      setDraggingNodeId(node.id);
                      const svg = svgRef.current;
                      if (!svg) return;
                      const rect = svg.getBoundingClientRect();
                      const mouseX = (e.clientX - rect.left - pan.x) / zoomLevel;
                      const mouseY = (e.clientY - rect.top - pan.y) / zoomLevel;
                      setDragOffset({ x: mouseX - pos.x, y: mouseY - pos.y });
                    };

                    const handleDoubleClick = (e: React.MouseEvent) => {
                      e.stopPropagation();
                      if (node.file_path && node.start_line) {
                        onInspectNode({
                          file_path: node.file_path,
                          start_line: node.start_line,
                          end_line: node.end_line || node.start_line,
                          symbol_name: node.name,
                        });
                      }
                    };

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${pos.x}, ${pos.y})`}
                        style={{
                          cursor: draggingNodeId === node.id ? "grabbing" : "grab",
                          opacity,
                          transition: draggingNodeId === node.id ? "none" : "opacity 150ms ease",
                        }}
                        onMouseDown={handleNodeMouseDown}
                        onDoubleClick={handleDoubleClick}
                      >
                        {/* Outer Selection Glow / Highlight */}
                        {isSelected && (
                          <rect
                            x={-NODE_WIDTH / 2 - 5}
                            y={-NODE_HEIGHT / 2 - 5}
                            width={NODE_WIDTH + 10}
                            height={NODE_HEIGHT + 10}
                            rx={14}
                            fill="none"
                            stroke="var(--blue)"
                            strokeWidth={2}
                            strokeDasharray="4 2"
                            opacity={0.8}
                          />
                        )}
                        {isSearchMatch && !isSelected && (
                          <rect
                            x={-NODE_WIDTH / 2 - 4}
                            y={-NODE_HEIGHT / 2 - 4}
                            width={NODE_WIDTH + 8}
                            height={NODE_HEIGHT + 8}
                            rx={12}
                            fill="none"
                            stroke="#f59e0b"
                            strokeWidth={2}
                          />
                        )}

                        {/* Node Card Background */}
                        <rect
                          x={-NODE_WIDTH / 2}
                          y={-NODE_HEIGHT / 2}
                          width={NODE_WIDTH}
                          height={NODE_HEIGHT}
                          rx={9}
                          fill={isSelected ? color.bg : "#ffffff"}
                          stroke={isSelected ? "var(--blue)" : isConnected ? color.accent : color.border}
                          strokeWidth={isSelected ? 2.5 : isConnected ? 1.8 : 1}
                          filter="drop-shadow(0 2px 4px rgba(0,0,0,0.06))"
                        />

                        {/* Left color bar indicator */}
                        <rect
                          x={-NODE_WIDTH / 2}
                          y={-NODE_HEIGHT / 2}
                          width={4}
                          height={NODE_HEIGHT}
                          rx={2}
                          fill={color.accent}
                        />

                        {/* Node Type Badge */}
                        <g transform={`translate(${-NODE_WIDTH / 2 + 12}, ${-NODE_HEIGHT / 2 + 8})`}>
                          <rect
                            x={0}
                            y={0}
                            width={38}
                            height={14}
                            rx={3}
                            fill={color.tagBg}
                            stroke={color.border}
                            strokeWidth={0.5}
                          />
                          <text
                            x={19}
                            y={10}
                            textAnchor="middle"
                            fontSize={8}
                            fontWeight={700}
                            fontFamily="var(--font-mono)"
                            fill={color.tagText}
                          >
                            {node.type.toUpperCase().slice(0, 4)}
                          </text>
                        </g>

                        {/* Node Name */}
                        <text
                          x={-NODE_WIDTH / 2 + 56}
                          y={-NODE_HEIGHT / 2 + 19}
                          fontSize={11}
                          fontWeight={600}
                          fontFamily="var(--font-mono)"
                          fill={color.text}
                        >
                          {node.name.length > 13 ? `${node.name.slice(0, 12)}...` : node.name}
                        </text>

                        {/* Secondary text: File Coordinates */}
                        <text
                          x={-NODE_WIDTH / 2 + 12}
                          y={-NODE_HEIGHT / 2 + 34}
                          fontSize={9}
                          fontFamily="var(--font-mono)"
                          fill="#64748b"
                        >
                          {node.file_path ? `${node.file_path.split("/").pop()}:L${node.start_line || 1}` : "global"}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>

              {/* Canvas Bottom Legend & Quick Hints */}
              <div
                style={{
                  position: "absolute",
                  bottom: 12,
                  left: 12,
                  right: 12,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "rgba(255, 255, 255, 0.94)",
                  backdropFilter: "blur(6px)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  padding: "6px 14px",
                  fontSize: 11,
                  boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
                  pointerEvents: "auto",
                }}
              >
                {/* Node type indicators */}
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>Nodes:</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#16a34a" }} />
                    <span style={{ color: "var(--text-primary)" }}>File</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#9333ea" }} />
                    <span style={{ color: "var(--text-primary)" }}>Class</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#2563eb" }} />
                    <span style={{ color: "var(--text-primary)" }}>Function</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#d97706" }} />
                    <span style={{ color: "var(--text-primary)" }}>Method</span>
                  </span>
                </div>

                {/* Mouse hints */}
                <div style={{ color: "var(--text-muted)", fontSize: 10 }}>
                  Drag nodes to rearrange • Drag canvas to pan • Scroll to zoom • Double-click node to inspect code
                </div>
              </div>
            </div>

            {/* Right Side: Selected Node Inspector Panel */}
            <div
              className="graph-inspector"
              style={{
                width: 310,
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
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
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
                        const color = getNodeColor(selectedNode.type);
                        return (
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 700,
                              fontFamily: "var(--font-mono)",
                              textTransform: "uppercase",
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: color.tagBg,
                              color: color.tagText,
                              border: `1px solid ${color.border}`,
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
                      borderRadius: 9,
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
                      Connected Relationships ({graphData?.edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length || 0}):
                    </span>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 220, overflowY: "auto" }}>
                      {graphData?.edges
                        .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                        .map((edge, idx) => {
                          const isSource = edge.source === selectedNode.id;
                          const connectedNode = graphData?.nodes.find((node) => node.id === (isSource ? edge.target : edge.source));
                          const edgeStyle = getEdgeStyle(edge.type);
                          return (
                            <button
                              type="button"
                              key={edge.id || idx}
                              disabled={!connectedNode}
                              onClick={() => connectedNode && setSelectedNode(connectedNode)}
                              title={connectedNode?.qualified_name}
                              style={{
                                padding: "6px 8px",
                                borderRadius: 7,
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
                                  padding: "2px 5px",
                                  borderRadius: 4,
                                  fontFamily: "var(--font-mono)",
                                  textTransform: "uppercase",
                                  fontWeight: 700,
                                  background: edgeStyle.labelBg,
                                  color: edgeStyle.labelText,
                                  border: `1px solid ${edgeStyle.stroke}`,
                                }}
                              >
                                {edge.type}
                              </span>
                              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)", fontSize: 10, overflowWrap: "anywhere" }}>
                                {isSource ? "-> " : "<- "}{connectedNode?.name || "Unavailable node"}
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
                        borderRadius: 9,
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
                  Click any node on the graph canvas to inspect its relationships.
                </div>
              )}
            </div>
          </div>
        ) : tab === "cards" ? (
          /* ======================================================== */
          /* Tabular Card Explorer View                               */
          /* ======================================================== */
          <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", overflow: "hidden" }}>
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
                    const color = getNodeColor(node.type);
                    const fileName = node.file_path ? node.file_path.split("/").pop() : "";

                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        style={{
                          padding: 12,
                          borderRadius: 10,
                          background: "#ffffff",
                          border: isSelected ? "2px solid var(--blue)" : "1px solid var(--border)",
                          boxShadow: isSelected
                            ? "0 4px 16px rgba(20, 115, 230, 0.18)"
                            : "0 1px 3px rgba(0, 0, 0, 0.04)",
                          cursor: "pointer",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          minWidth: 230,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              textTransform: "uppercase",
                              fontFamily: "var(--font-mono)",
                              padding: "2px 6px",
                              borderRadius: 4,
                              background: color.tagBg,
                              color: color.tagText,
                              border: `1px solid ${color.border}`,
                            }}
                          >
                            {node.type}
                          </span>
                          {fileName && (
                            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                              {fileName}
                            </span>
                          )}
                        </div>
                        <h4 style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--text-primary)", margin: "2px 0 0 0" }}>
                          {node.name}
                        </h4>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>
                          <span>{node.start_line ? `L${node.start_line}-${node.end_line}` : "Global"}</span>
                          <span style={{ color: isSelected ? "var(--blue)" : "var(--text-muted)" }}>{isSelected ? "Selected" : "Inspect"}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Inspector */}
            <div
              className="graph-inspector"
              style={{
                width: 310,
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
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600 }}>
                      Selected Node Details
                    </span>
                    <h3 style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 700, color: "var(--text-primary)", margin: "4px 0 0 0" }}>
                      {selectedNode.name}
                    </h3>
                  </div>
                  <div style={{ padding: 12, borderRadius: 9, background: "#f8fafc", border: "1px solid var(--border)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    <div style={{ color: "var(--text-muted)" }}>Qualified Name</div>
                    <div style={{ color: "var(--blue)", fontWeight: 500, wordBreak: "break-all" }}>{selectedNode.qualified_name}</div>
                  </div>
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
                        borderRadius: 9,
                        background: "var(--blue)",
                        color: "white",
                        border: "none",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      <FileCode size={14} /> Inspect in Code Viewer
                    </button>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          /* ======================================================== */
          /* Call Flows Tab                                           */
          /* ======================================================== */
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
                  const edgeStyle = getEdgeStyle(flow.relationship);
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
                        style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
                      >
                        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)" }}>
                          {flow.caller.name}
                        </span>
                        <span style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {flow.caller.file_path}
                        </span>
                      </div>

                      <span
                        style={{
                          fontSize: 10,
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontFamily: "var(--font-mono)",
                          fontWeight: 700,
                          background: edgeStyle.labelBg,
                          color: edgeStyle.labelText,
                          border: `1px solid ${edgeStyle.stroke}`,
                        }}
                      >
                        {flow.relationship}
                      </span>
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
