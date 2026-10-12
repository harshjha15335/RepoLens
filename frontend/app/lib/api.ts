import {
  Repository,
  FileInfo,
  FileContent,
  SymbolInfo,
  ChatMessage,
  ChatSession,
  RetrievedChunk,
  EvaluationRun,
  TutorMode,
  GraphResponse,
  CallFlowItem,
  Citation,
  InterviewQuestion,
  InterviewFeedback,
  CodeContextAttachment,
} from "../types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
const CHAT_REQUEST_TIMEOUT_MS = 160_000;

async function request<T>(endpoint: string, options?: RequestInit, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort(options?.signal?.reason);
  if (options?.signal?.aborted) onAbort();
  else options?.signal?.addEventListener("abort", onAbort, { once: true });

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(options?.headers || {}),
      },
    });

    if (!response.ok) {
      if (response.status === 401 && typeof window !== "undefined") {
        window.dispatchEvent(new Event("repolens:unauthorized"));
      }
      // A response stream can only be read once, even if JSON parsing fails.
      const body = await response.text();
      let errorDetail = body;
      try {
        const errJson = JSON.parse(body);
        const detail = errJson?.error || errJson?.detail || errJson || "";
        errorDetail = typeof detail === "string" ? detail : JSON.stringify(detail);
      } catch {
        // Preserve non-JSON errors returned by the backend or its proxy.
      }
      if (errorDetail.trim().toLowerCase() === "internal server error") {
        errorDetail = `The server could not complete this request (HTTP ${response.status}). Check that the backend is running and inspect its logs.`;
      }
      throw new Error(errorDetail || `HTTP error ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    if (timedOut) {
      throw new Error(`Request timed out after ${timeoutMs / 1000} seconds. The client stopped waiting; server work may continue.`, { cause: error });
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    options?.signal?.removeEventListener("abort", onAbort);
  }
}

export const api = {
  // Repositories
  async getRepositories(): Promise<Repository[]> {
    const data = await request<{ repositories: Repository[]; total: number }>("/repositories");
    return data.repositories;
  },

  async getRepository(repoId: string): Promise<Repository> {
    return request<Repository>(`/repositories/${repoId}`);
  },

  async getRepositoryStatus(repoId: string): Promise<Repository> {
    return request<Repository>(`/repositories/${repoId}/status`);
  },

  async uploadRepository(file: File): Promise<Repository> {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${BASE_URL}/repositories/upload`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: "Upload failed" }));
      throw new Error(err.error || err.detail || "Upload failed");
    }

    return response.json();
  },

  async importGit(url: string, branch?: string): Promise<Repository> {
    return request<Repository>("/repositories/git", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, branch: branch || "main" }),
    });
  },

  async deleteRepository(repoId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/repositories/${repoId}`, {
      method: "DELETE",
    });
  },

  async reindexRepository(repoId: string): Promise<Repository> {
    return request<Repository>(`/repositories/${repoId}/index`, {
      method: "POST",
    });
  },

  // Files & Content
  async getFiles(repoId: string): Promise<FileInfo[]> {
    return request<FileInfo[]>(`/repositories/${repoId}/files`);
  },

  async getFileContent(repoId: string, path: string): Promise<FileContent> {
    const encoded = encodeURIComponent(path);
    return request<FileContent>(`/repositories/${repoId}/files/content?path=${encoded}`);
  },

  // Symbols
  async getSymbols(repoId: string, symbolType?: string): Promise<SymbolInfo[]> {
    const query = symbolType ? `?symbol_type=${encodeURIComponent(symbolType)}` : "";
    const res = await request<{ symbols: SymbolInfo[]; total: number }>(
      `/repositories/${repoId}/symbols${query}`
    );
    return res.symbols;
  },

  // Code Knowledge Graph
  async getGraph(
    repoId: string,
    nodeType?: string,
    relationshipType?: string,
    limit = 200
  ): Promise<GraphResponse> {
    const params = new URLSearchParams();
    if (nodeType && nodeType !== "all") params.append("node_type", nodeType);
    if (relationshipType && relationshipType !== "all") params.append("relationship_type", relationshipType);
    params.append("limit", limit.toString());
    return request<GraphResponse>(`/repositories/${repoId}/graph?${params.toString()}`);
  },

  async getCallFlows(repoId: string): Promise<{ repository_id: string; flows: CallFlowItem[]; total: number }> {
    return request<{ repository_id: string; flows: CallFlowItem[]; total: number }>(
      `/repositories/${repoId}/call-flows`
    );
  },

  // Interview Mode
  async generateInterviewQuestions(params: {
    repositoryId: string;
    difficulty: "beginner" | "intermediate" | "advanced";
    focus: string;
    count: number;
  }): Promise<{
    repository_id: string;
    difficulty: string;
    focus: string;
    questions: InterviewQuestion[];
    total: number;
  }> {
    return request(`/repositories/${params.repositoryId}/interview/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: params.difficulty,
        focus: params.focus,
        count: params.count,
      }),
    });
  },

  async evaluateInterviewAnswer(params: {
    repositoryId: string;
    question: string;
    userAnswer: string;
    targetFiles: string[];
    targetSymbols: string[];
  }): Promise<InterviewFeedback> {
    return request<InterviewFeedback>(`/repositories/${params.repositoryId}/interview/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: params.question,
        user_answer: params.userAnswer,
        target_files: params.targetFiles,
        target_symbols: params.targetSymbols,
      }),
    });
  },

  // Chat & Sessions
  async getSessions(repoId?: string): Promise<ChatSession[]> {
    const query = repoId ? `?repository_id=${encodeURIComponent(repoId)}` : "";
    const res = await request<{ sessions: ChatSession[]; total: number }>(`/sessions${query}`);
    return res.sessions;
  },

  async getSession(sessionId: string): Promise<ChatSession> {
    return request<ChatSession>(`/sessions/${sessionId}`);
  },

  async createSession(repoId: string, tutorMode: TutorMode = "developer"): Promise<ChatSession> {
    return request<ChatSession>(
      `/sessions?repository_id=${encodeURIComponent(repoId)}&tutor_mode=${encodeURIComponent(tutorMode)}`,
      { method: "POST" }
    );
  },

  async deleteSession(sessionId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/sessions/${sessionId}`, {
      method: "DELETE",
    });
  },

  async sendMessage(params: {
    repositoryId: string;
    question: string;
    tutorMode: TutorMode;
    sessionId?: string;
    codeContext?: CodeContextAttachment;
  }): Promise<{
    session_id: string;
    message_id: string;
    answer: string;
    citations: Citation[];
    retrieval_metadata: NonNullable<ChatMessage["retrieval_metadata"]>;
  }> {
    return request<{
      session_id: string;
      message_id: string;
      answer: string;
      citations: Citation[];
      retrieval_metadata: NonNullable<ChatMessage["retrieval_metadata"]>;
    }>("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repository_id: params.repositoryId,
        question: params.question,
        tutor_mode: params.tutorMode,
        session_id: params.sessionId,
        code_context: params.codeContext,
      }),
    }, CHAT_REQUEST_TIMEOUT_MS);
  },

  // Direct Retrieval Search
  async searchRetrieval(params: {
    repositoryId: string;
    query: string;
    strategy?: string;
    topK?: number;
    enableGraphExpansion?: boolean;
    enableMmr?: boolean;
    enableReranking?: boolean;
  }): Promise<{
    query: string;
    intent?: string;
    chunks: RetrievedChunk[];
    total_retrieved: number;
    latency_ms: number;
    strategy: string;
  }> {
    return request("/retrieval/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repository_id: params.repositoryId,
        query: params.query,
        top_k: params.topK ?? 10,
        strategy: params.strategy ?? "hybrid_rrf",
        enable_graph_expansion: params.enableGraphExpansion ?? true,
        enable_mmr: params.enableMmr ?? true,
        enable_reranking: params.enableReranking ?? false,
      }),
    });
  },

  // Evaluation
  async runEvaluation(params: {
    repositoryId: string;
    strategies?: string[];
    datasetPath?: string;
  }): Promise<EvaluationRun> {
    return request<EvaluationRun>("/evaluation/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repository_id: params.repositoryId,
        strategies: params.strategies ?? ["bm25", "dense", "hybrid_rrf", "graph_expansion"],
        dataset_path: params.datasetPath,
      }),
    });
  },

  async getEvaluation(evaluationId: string): Promise<EvaluationRun> {
    return request<EvaluationRun>(`/evaluation/${evaluationId}`);
  },
};
