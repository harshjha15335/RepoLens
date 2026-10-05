export interface RepositoryStats {
  files: number;
  chunks: number;
  symbols: number;
  graph_nodes: number;
  graph_edges: number;
}

export type RepositoryStatus =
  | "pending"
  | "discovering"
  | "parsing"
  | "chunking"
  | "building_graph"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed"
  | "PENDING"
  | "DISCOVERING"
  | "PARSING"
  | "CHUNKING"
  | "BUILDING_GRAPH"
  | "EMBEDDING"
  | "INDEXING"
  | "READY"
  | "FAILED"
  | string;

export interface Repository {
  id: string;
  name: string;
  source_type: "zip" | "git";
  status: RepositoryStatus;
  progress: number;
  progress_message?: string | null;
  error_message?: string | null;
  languages: string[];
  stats: RepositoryStats;
  created_at: string;
  updated_at: string;
  indexed_at?: string | null;
}

export interface FileInfo {
  id: string;
  path: string;
  language?: string | null;
  size_bytes: number;
  symbol_count: number;
  chunk_count: number;
}

export interface FileContent {
  path: string;
  content: string;
  language?: string | null;
  total_lines: number;
}

export interface SymbolInfo {
  name: string;
  symbol_type: string;
  file_path: string;
  start_line: number;
  end_line: number;
  parent_symbol?: string | null;
}

export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string | null;
  symbol?: string | null;
  snippet?: string | null;
  content_preview?: string | null;
  confidence?: number;
}

export interface RetrievedChunk {
  chunk_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string | null;
  symbol_type?: string | null;
  content: string;
  score: number;
  source: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  retrieval_metadata?: {
    intent?: string;
    strategy?: string;
    total_retrieved?: number;
    latency_ms?: number;
    retrieved_chunks?: RetrievedChunk[];
    [key: string]: any;
  };
  created_at: string;
}

export interface ChatSession {
  id: string;
  repository_id: string;
  title?: string | null;
  tutor_mode: TutorMode;
  message_count: number;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export type TutorMode = "beginner" | "developer" | "interview" | "debug";

export type Theme = "dark" | "light";

export type ActiveActivityView =
  | "files"
  | "search"
  | "symbols"
  | "graph"
  | "interview"
  | "evaluation"
  | "settings";

export interface CodeContextAttachment {
  file_path: string;
  start_line: number;
  end_line: number;
  text?: string;
  symbol_name?: string;
}

export interface GraphNodeData {
  id: string;
  type: "file" | "class" | "function" | "method" | string;
  name: string;
  qualified_name: string;
  file_path?: string;
  start_line?: number;
  end_line?: number;
  metadata?: Record<string, any>;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  type: "CONTAINS" | "IMPORTS" | "CALLS" | "INHERITS" | string;
  metadata?: Record<string, any>;
}

export interface GraphResponse {
  repository_id: string;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  stats: {
    total_nodes: number;
    total_edges: number;
    node_types: Record<string, number>;
    edge_types: Record<string, number>;
  };
}

export interface CallFlowItem {
  id: string;
  relationship: string;
  caller: {
    name: string;
    type: string;
    file_path?: string;
    start_line?: number;
    end_line?: number;
  };
  callee: {
    name: string;
    type: string;
    file_path?: string;
    start_line?: number;
    end_line?: number;
  };
}

export interface InterviewQuestion {
  id: string;
  topic: string;
  difficulty: "beginner" | "intermediate" | "advanced";
  question: string;
  target_files: string[];
  target_symbols: string[];
  expected_concepts: string[];
}

export interface InterviewFeedback {
  score: number;
  what_was_correct: string;
  what_was_missing: string;
  grounded_explanation: string;
  citations: Citation[];
}

export interface EvaluationMetricResult {
  strategy: string;
  recall_at_5: number;
  recall_at_10: number;
  mrr: number;
  avg_latency_ms: number;
  results: Array<{
    id: string;
    question: string;
    relevant_files: string[];
    retrieved_files: string[];
    hit_at_5: boolean;
    hit_at_10: boolean;
    reciprocal_rank: number;
    latency_ms: number;
  }>;
}

export interface EvaluationRun {
  id: string;
  repository_id: string;
  status: "running" | "completed" | "failed";
  metrics: EvaluationMetricResult[];
  created_at: string;
  completed_at?: string | null;
}
