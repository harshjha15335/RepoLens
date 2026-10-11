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
  Target,
  Trophy,
  HelpCircle,
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
  repoName,
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
    <div className="flex-1 flex flex-col h-full bg-[#030712] overflow-y-auto p-6 select-text">
      <div className="max-w-3xl mx-auto w-full space-y-6">
        <button type="button" onClick={onBackToCode} className="inline-flex items-center gap-2 text-xs text-slate-300 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> Back to code
        </button>
        {/* Setup Stage */}
        {stage === "setup" && (
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden p-6 space-y-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-emerald-500/20">
                <GraduationCap className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white">Repository Technical Interview</h2>
              </div>
            </div>

            <div className="space-y-4 pt-2">
              {/* Difficulty */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Select Difficulty:
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {([
                    { id: "beginner", label: "Beginner", desc: "Core concepts & symbols" },
                    { id: "intermediate", label: "Intermediate", desc: "Control flow & patterns" },
                    { id: "advanced", label: "Advanced", desc: "Architecture & failure modes" },
                  ] as const).map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => setDifficulty(d.id)}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        difficulty === d.id
                          ? "bg-emerald-950/40 border-emerald-500/60 shadow-md shadow-emerald-500/10"
                          : "bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-400"
                      }`}
                    >
                      <span className="font-bold text-xs text-white block capitalize">{d.label}</span>
                      <span className="text-[11px] text-slate-500">{d.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Focus Area */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Technical Focus:
                </label>
                <div className="grid grid-cols-3 gap-2">
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
                      className={`px-3 py-2 rounded-xl text-xs font-medium capitalize border transition-all ${
                        focus === f
                          ? "bg-indigo-600/30 text-indigo-300 border-indigo-500/50 shadow-sm"
                          : "bg-slate-950/60 text-slate-400 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              {/* Question Count */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Question Count:
                </label>
                <div className="flex gap-2">
                  {[5, 10, 15].map((cnt) => (
                    <button
                      key={cnt}
                      type="button"
                      onClick={() => setQuestionCount(cnt)}
                      className={`px-4 py-1.5 rounded-lg text-xs font-mono font-bold border transition-all ${
                        questionCount === cnt
                          ? "bg-cyan-600/30 text-cyan-300 border-cyan-500/50"
                          : "bg-slate-950/60 text-slate-400 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      {cnt} Questions
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800/80 flex justify-end">
              <button
                onClick={handleStartInterview}
                disabled={evaluating}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/25 transition-all"
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
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden p-6 space-y-5">
            {/* Header info */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Question {currentIndex + 1} of {questions.length}
                </span>
                <span className="text-xs text-slate-400">·</span>
                <span className="text-xs font-medium text-indigo-300 capitalize">{currentQ.topic}</span>
              </div>
              <span className="text-[11px] font-mono text-slate-500 capitalize">
                {currentQ.difficulty}
              </span>
            </div>

            {/* Question Box */}
            <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800">
              <h3 className="text-sm font-semibold text-white leading-relaxed">
                {currentQ.question}
              </h3>

              {currentQ.target_files && currentQ.target_files.length > 0 && (
                <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-500">
                  <span>Target Component:</span>
                  <span className="text-cyan-400 font-medium">
                    {currentQ.target_files.join(", ")}
                  </span>
                </div>
              )}
            </div>

            {/* Answer Form */}
            <form onSubmit={handleSubmitAnswer} className="space-y-3">
              <label className="block text-xs font-semibold text-slate-300">
                Your Answer (grounded in codebase evidence):
              </label>
              <textarea
                rows={5}
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                placeholder="Explain the implementation, patterns, method responsibilities, or error behavior as evidenced by the repository..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 transition-colors shadow-inner"
              />

              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => setStage("setup")}
                  className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  Exit Interview
                </button>

                <button
                  type="submit"
                  disabled={!userAnswer.trim() || evaluating}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-md shadow-emerald-600/20 disabled:opacity-40 transition-all"
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
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden p-6 space-y-5 animate-in fade-in duration-150">
            {/* Header info */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Question {currentIndex + 1} Feedback
                </span>
                <span className="text-xs text-slate-400">·</span>
                <span className="text-xs font-medium text-slate-300">{currentQ.topic}</span>
              </div>

              {/* Score pill */}
              <div className="flex items-center gap-2 font-mono">
                <span className="text-xs text-slate-400">Source overlap score:</span>
                <span
                  className={`text-sm font-bold ${
                    feedback.score >= 80
                      ? "text-emerald-400"
                      : feedback.score >= 60
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}
                >
                  {feedback.score}/100
                </span>
              </div>
            </div>

            {/* Question recap */}
            <div className="text-xs text-slate-400 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
              <span className="font-semibold text-slate-300 block mb-0.5">Question:</span>
              <span>{currentQ.question}</span>
            </div>

            {/* Structured Feedback Sections */}
            <div className="space-y-3 text-xs">
              {/* Correct */}
              <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/20">
                <div className="flex items-center gap-1.5 text-emerald-400 font-bold mb-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Matched source terms:</span>
                </div>
                <p className="text-slate-300 leading-relaxed pl-5">
                  {feedback.what_was_correct}
                </p>
              </div>

              {/* Missing */}
              <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/20">
                <div className="flex items-center gap-1.5 text-amber-400 font-bold mb-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Missing source terms:</span>
                </div>
                <p className="text-slate-300 leading-relaxed pl-5">
                  {feedback.what_was_missing}
                </p>
              </div>

              {/* Grounded Code Explanation */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 font-semibold block mb-1">
                  Relevant source excerpts:
                </span>
                <p className="text-slate-300 leading-relaxed">
                  {feedback.grounded_explanation.replace(/^Relevant source excerpts:\s*/i, "")}
                </p>
              </div>

              {/* Relevant Citations */}
              {feedback.citations && feedback.citations.length > 0 && (
                <div className="pt-2">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                    Repository Evidence (Click to inspect source):
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {feedback.citations.map((c, idx) => (
                      <button
                        key={idx}
                        onClick={() => onInspectCitation(c)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-xs bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-300 hover:text-white transition-colors"
                      >
                        <FileCode className="w-3.5 h-3.5" />
                        <span>{c.file_path}</span>
                        <span className="text-cyan-400 font-bold">
                          :L{c.start_line}-{c.end_line}
                        </span>
                        <ExternalLink className="w-3 h-3 text-slate-400 ml-0.5" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Next button */}
            <div className="pt-2 border-t border-slate-800 flex justify-end">
              <button
                onClick={handleNextQuestion}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-md shadow-indigo-600/20 transition-all"
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
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden p-8 text-center space-y-5 animate-in zoom-in-95 duration-200">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500 to-cyan-500 mx-auto flex items-center justify-center text-white shadow-xl shadow-emerald-500/25">
              <Trophy className="w-7 h-7" />
            </div>

            <div>
              <h2 className="text-lg font-bold text-white">Interview Complete!</h2>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 max-w-sm mx-auto font-mono">
              <span className="text-xs text-slate-400 block mb-1">Average source overlap</span>
              <span className="text-3xl font-extrabold text-emerald-400">{averageScore}%</span>
            </div>

            <div className="pt-2 flex justify-center gap-3">
              <button
                onClick={() => setStage("setup")}
                className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-colors shadow-md shadow-indigo-600/20"
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
