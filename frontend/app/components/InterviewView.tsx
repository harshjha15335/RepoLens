"use client";

import React, { useState } from "react";
import {
  GraduationCap,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  FileCode,
  ExternalLink,
  Trophy,
  Send,
} from "lucide-react";
import { InterviewQuestion, InterviewFeedback, Citation } from "../types";
import { api } from "../lib/api";

interface InterviewViewProps {
  repositoryId: string;
  repoName?: string;
  onInspectCitation: (citation: Citation) => void;
  onBackToCode: () => void;
}

export default function InterviewView({
  repositoryId,
  onInspectCitation,
  onBackToCode,
}: InterviewViewProps) {
  // State machine: "setup" | "interviewing" | "feedback" | "completed"
  const [stage, setStage] = useState<"setup" | "interviewing" | "feedback" | "completed">("setup");
  const [difficulty, setDifficulty] = useState<"beginner" | "intermediate" | "advanced">("intermediate");
  const [focus, setFocus] = useState<string>("general");
  const [questionCount, setQuestionCount] = useState<number>(5);

  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState("");
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [scores, setScores] = useState<number[]>([]);

  // Start interview: calls backend to generate grounded questions
  const handleStartInterview = async () => {
    setEvaluating(true);
    try {
      const data = await api.generateInterviewQuestions({
        repositoryId,
        difficulty,
        focus,
        count: questionCount,
      });

      if (data.questions && data.questions.length > 0) {
        setQuestions(data.questions);
        setCurrentIndex(0);
        setUserAnswer("");
        setFeedback(null);
        setScores([]);
        setStage("interviewing");
      } else {
        alert("Could not generate interview questions for this repository. Ensure indexing is complete.");
      }
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to start interview");
    } finally {
      setEvaluating(false);
    }
  };

  // Submit answer
  const handleSubmitAnswer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userAnswer.trim() || evaluating) return;

    const currentQ = questions[currentIndex];
    setEvaluating(true);

    try {
      const res = await api.evaluateInterviewAnswer({
        repositoryId,
        question: currentQ.question,
        userAnswer: userAnswer.trim(),
        targetFiles: currentQ.target_files,
        targetSymbols: currentQ.target_symbols,
      });

      setFeedback(res);
      setScores((prev) => [...prev, res.score]);
      setStage("feedback");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to evaluate answer");
    } finally {
      setEvaluating(false);
    }
  };

  // Next question or finish
  const handleNextQuestion = () => {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((idx) => idx + 1);
      setUserAnswer("");
      setFeedback(null);
      setStage("interviewing");
    } else {
      setStage("completed");
    }
  };

  const currentQ = questions[currentIndex];
  const averageScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--bg-desktop)] overflow-y-auto p-3 sm:p-6 select-text">
      <div className="max-w-3xl mx-auto w-full space-y-6">
        <button type="button" onClick={onBackToCode} className="inline-flex items-center gap-2 text-xs text-[var(--text-secondary)] hover:text-[var(--blue-hover)]">
          <ArrowLeft className="w-4 h-4" /> Back to code
        </button>
        {/* Setup Stage */}
        {stage === "setup" && (
          <div className="rounded-[var(--radius-panel)] bg-[var(--surface)] border border-[var(--border)] shadow-[var(--shadow-subtle)] overflow-hidden p-3 sm:p-6 space-y-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-[var(--radius-button)] bg-[var(--blue)] flex items-center justify-center text-white shadow-[var(--shadow-subtle)]">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-[var(--text-primary)]">Repository Technical Interview</h2>
              </div>
            </div>

            <div className="space-y-4 pt-2">
              {/* Difficulty */}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-2">
                  Select Difficulty:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {([
                    { id: "beginner", label: "Beginner", desc: "Core concepts & symbols" },
                    { id: "intermediate", label: "Intermediate", desc: "Control flow & patterns" },
                    { id: "advanced", label: "Advanced", desc: "Architecture & failure modes" },
                  ] as const).map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => setDifficulty(d.id)}
                      className={`p-3 rounded-[var(--radius-control)] border text-left transition-all ${
                        difficulty === d.id
                          ? "bg-[var(--blue-light)] border-[var(--blue)] shadow-[var(--shadow-subtle)]"
                          : "bg-[var(--surface-secondary)] border-[var(--border)] hover:border-[var(--blue)] text-[var(--text-secondary)]"
                      }`}
                    >
                      <span className="font-bold text-xs text-[var(--text-primary)] block capitalize">{d.label}</span>
                      <span className="text-[11px] text-[var(--text-muted)]">{d.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Focus Area */}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-2">
                  Technical Focus:
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {[
                    "general",
                    "architecture",
                    "backend",
                    "frontend",
                    "algorithms",
                    "data flow",
                  ].map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => setFocus(f)}
                      className={`px-3 py-2 rounded-[var(--radius-control)] text-xs font-medium capitalize border transition-all ${
                        focus === f
                          ? "bg-[var(--blue-light)] text-[var(--blue)] border-[var(--blue)] shadow-[var(--shadow-subtle)]"
                          : "bg-[var(--surface-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--blue)]"
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              {/* Question Count */}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-2">
                  Question Count:
                </label>
                <div className="flex flex-wrap gap-2">
                  {[5, 10, 15].map((cnt) => (
                    <button
                      key={cnt}
                      type="button"
                      onClick={() => setQuestionCount(cnt)}
                      className={`px-4 py-1.5 rounded-[var(--radius-control)] text-xs font-mono font-bold border transition-all ${
                        questionCount === cnt
                          ? "bg-[var(--blue-light)] text-[var(--blue)] border-[var(--blue)]"
                          : "bg-[var(--surface-secondary)] text-[var(--text-secondary)] border-[var(--border)] hover:border-[var(--blue)]"
                      }`}
                    >
                      {cnt} Questions
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-[var(--border)] flex justify-end">
              <button
                onClick={handleStartInterview}
                disabled={evaluating}
                className="px-6 py-2.5 rounded-[var(--radius-button)] bg-[var(--blue)] hover:bg-[var(--blue-hover)] text-white font-semibold text-xs flex items-center gap-2 shadow-[var(--shadow-subtle)] transition-all"
              >
                {evaluating ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                <span>{evaluating ? "Generating Grounded Questions..." : "Start Interview"}</span>
              </button>
            </div>
          </div>
        )}

        {/* Interviewing / Question Stage */}
        {stage === "interviewing" && currentQ && (
          <div className="rounded-[var(--radius-panel)] bg-[var(--surface)] border border-[var(--border)] shadow-[var(--shadow-subtle)] overflow-hidden p-3 sm:p-6 space-y-5">
            {/* Header info */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2 py-0.5 rounded whitespace-nowrap font-mono text-[11px] font-bold bg-[var(--blue-light)] text-[var(--blue)] border border-[var(--blue)]">
                  Question {currentIndex + 1} of {questions.length}
                </span>
                <span className="text-xs text-[var(--text-secondary)]">·</span>
                <span className="text-xs font-medium text-[var(--blue)] capitalize">{currentQ.topic}</span>
              </div>
              <span className="text-[11px] font-mono text-[var(--text-muted)] capitalize">
                {currentQ.difficulty}
              </span>
            </div>

            {/* Question Box */}
            <div className="p-4 rounded-[var(--radius-control)] bg-[var(--surface-secondary)] border border-[var(--border)]">
              <h3 className="text-sm font-semibold text-[var(--text-primary)] leading-relaxed">
                {currentQ.question}
              </h3>

              {currentQ.target_files && currentQ.target_files.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mt-3 pt-2 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-muted)] break-all">
                  <span>Target Component:</span>
                  <span className="text-[var(--blue)] font-medium">
                    {currentQ.target_files.join(", ")}
                  </span>
                </div>
              )}
            </div>

            {/* Answer Form */}
            <form onSubmit={handleSubmitAnswer} className="space-y-3">
              <label className="block text-xs font-semibold text-[var(--text-secondary)]">
                Your Answer (grounded in codebase evidence):
              </label>
              <textarea
                rows={5}
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                placeholder="Explain the implementation, patterns, method responsibilities, or error behavior as evidenced by the repository..."
                className="w-full bg-[var(--surface-secondary)] border border-[var(--border)] rounded-[var(--radius-control)] p-3 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors shadow-inner"
              />

              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => setStage("setup")}
                  className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
                >
                  Exit Interview
                </button>

                <button
                  type="submit"
                  disabled={!userAnswer.trim() || evaluating}
                  className="px-5 py-2 rounded-[var(--radius-button)] bg-[var(--blue)] hover:bg-[var(--blue-hover)] text-white font-semibold text-xs flex items-center gap-1.5 shadow-[var(--shadow-subtle)] disabled:opacity-40 transition-all"
                >
                  {evaluating ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                  <span>{evaluating ? "Checking Source Overlap..." : "Submit Answer"}</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Feedback Stage */}
        {stage === "feedback" && feedback && currentQ && (
          <div className="rounded-[var(--radius-panel)] bg-[var(--surface)] border border-[var(--border)] shadow-[var(--shadow-subtle)] overflow-hidden p-3 sm:p-6 space-y-5 animate-in fade-in duration-150">
            {/* Header info */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-2 py-0.5 rounded whitespace-nowrap font-mono text-[11px] font-bold bg-[var(--blue-light)] text-[var(--blue)] border border-[var(--blue)]">
                  Question {currentIndex + 1} Feedback
                </span>
                <span className="text-xs text-[var(--text-secondary)]">·</span>
                <span className="text-xs font-medium text-[var(--text-secondary)]">{currentQ.topic}</span>
              </div>

              {/* Score pill */}
              <div className="flex items-center gap-2 font-mono whitespace-nowrap">
                <span className="text-xs text-[var(--text-secondary)]">Source overlap score:</span>
                <span
                  className={`text-sm font-bold ${
                    feedback.score >= 80
                      ? "text-[#16834a]"
                      : feedback.score >= 60
                      ? "text-[#9a6700]"
                      : "text-[#c62828]"
                  }`}
                >
                  {feedback.score}/100
                </span>
              </div>
            </div>

            {/* Question recap */}
            <div className="text-xs text-[var(--text-secondary)] bg-[var(--surface-secondary)] p-3 rounded-xl border border-[var(--border)]">
              <span className="font-semibold text-[var(--text-secondary)] block mb-0.5">Question:</span>
              <span>{currentQ.question}</span>
            </div>

            {/* Structured Feedback Sections */}
            <div className="space-y-3 text-xs">
              {/* Correct */}
              <div className="p-3.5 rounded-xl bg-[var(--green-light)] border border-[#b7efcf]">
                <div className="flex items-center gap-1.5 text-[#16834a] font-bold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Matched source terms:</span>
                </div>
                <p className="text-[var(--text-secondary)] leading-relaxed pl-5">
                  {feedback.what_was_correct}
                </p>
              </div>

              {/* Missing */}
              <div className="p-3.5 rounded-xl bg-[var(--orange-light)] border border-[#f5d58c]">
                <div className="flex items-center gap-1.5 text-[#9a6700] font-bold mb-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Missing source terms:</span>
                </div>
                <p className="text-[var(--text-secondary)] leading-relaxed pl-5">
                  {feedback.what_was_missing}
                </p>
              </div>

              {/* Grounded Code Explanation */}
              <div className="p-3.5 rounded-[var(--radius-control)] bg-[var(--surface-secondary)] border border-[var(--border)]">
                <span className="text-[var(--text-secondary)] font-semibold block mb-1">
                  Relevant source excerpts:
                </span>
                <p className="text-[var(--text-secondary)] leading-relaxed">
                  {feedback.grounded_explanation.replace(/^Relevant source excerpts:\s*/i, "")}
                </p>
              </div>

              {/* Relevant Citations */}
              {feedback.citations && feedback.citations.length > 0 && (
                <div className="pt-2">
                  <span className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider block mb-2">
                    Repository Evidence (Click to inspect source):
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {feedback.citations.map((c, idx) => (
                      <button
                        key={idx}
                        onClick={() => onInspectCitation(c)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-control)] font-mono text-xs break-all bg-[var(--blue-light)] hover:bg-[#d8eaff] border border-[#bed8fa] text-[var(--blue)] hover:text-[var(--blue-hover)] transition-colors"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                        <span>{c.file_path}</span>
                        <span className="text-[var(--blue)] font-bold">
                          :L{c.start_line}-{c.end_line}
                        </span>
                        <ExternalLink className="w-3 h-3 text-[var(--text-secondary)] ml-0.5" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Next button */}
            <div className="pt-2 border-t border-[var(--border)] flex justify-end">
              <button
                onClick={handleNextQuestion}
                className="px-5 py-2.5 rounded-[var(--radius-button)] bg-[var(--blue)] hover:bg-[var(--blue-hover)] text-white font-semibold text-xs flex items-center gap-1.5 shadow-[var(--shadow-subtle)] transition-all"
              >
                <span>
                  {currentIndex + 1 < questions.length ? "Next Question" : "View Final Report"}
                </span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Completed Stage */}
        {stage === "completed" && (
          <div className="rounded-[var(--radius-panel)] bg-[var(--surface)] border border-[var(--border)] shadow-[var(--shadow-subtle)] overflow-hidden p-8 max-sm:p-4 text-center space-y-5 animate-in zoom-in-95 duration-200">
            <div className="w-14 h-14 rounded-2xl bg-[var(--blue)] mx-auto flex items-center justify-center text-white shadow-[var(--shadow-subtle)]">
              <Trophy className="w-7 h-7" />
            </div>

            <div>
              <h2 className="text-lg font-bold text-[var(--text-primary)]">Interview Complete!</h2>
            </div>

            <div className="p-4 rounded-[var(--radius-control)] bg-[var(--surface-secondary)] border border-[var(--border)] max-w-sm mx-auto font-mono">
              <span className="text-xs text-[var(--text-secondary)] block mb-1">Average source overlap</span>
              <span className="text-3xl font-extrabold text-[#16834a]">{averageScore}%</span>
            </div>

            <div className="pt-2 flex justify-center gap-3">
              <button
                onClick={() => setStage("setup")}
                className="px-5 py-2 rounded-[var(--radius-button)] bg-[var(--blue)] hover:bg-[var(--blue-hover)] text-white font-medium text-xs transition-colors shadow-[var(--shadow-subtle)]"
              >
                Start Another Interview
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
