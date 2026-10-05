import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeMentor-RAG — Retrieval-Augmented AI Tutor for Codebase Understanding",
  description:
    "Deep codebase intelligence powered by AST-aware Tree-sitter chunking, dense vector retrieval, lexical BM25, code knowledge graph expansion, and multi-tier AI tutoring.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-full">
        {children}
      </body>
    </html>
  );
}
