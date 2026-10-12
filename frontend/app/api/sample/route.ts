import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function POST(request: Request) {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
    const origin = request.headers.get("origin");
    const host = request.headers.get("host") || new URL(request.url).host;
    let sameOrigin = !origin;
    if (origin) {
      try {
        sameOrigin = new URL(origin).host === host;
      } catch {
        sameOrigin = false;
      }
    }
    if (request.headers.get("sec-fetch-site") === "cross-site" || !sameOrigin) {
      return NextResponse.json({ error: "Cross-site requests are not allowed" }, { status: 403 });
    }
    const headers = new Headers();
    const cookie = request.headers.get("cookie");
    if (cookie) headers.set("cookie", cookie);
    const authResponse = await fetch(`${backendUrl}/api/auth/status`, { headers, cache: "no-store" });
    const auth = await authResponse.json();
    if (!authResponse.ok || !auth.authenticated) {
      return NextResponse.json({ error: "Sign in to access RepoLens" }, { status: 401 });
    }
    
    const zipPath = process.env.SAMPLE_REPOSITORY_ZIP
      ? path.resolve(process.env.SAMPLE_REPOSITORY_ZIP)
      : [path.join(process.cwd(), "sample-repos", "calculator.zip"), path.join(process.cwd(), "..", "sample-repos", "calculator.zip")].find((candidate) => fs.existsSync(candidate)) || "";

    if (!fs.existsSync(zipPath)) {
      return NextResponse.json(
        { error: "Sample repository is not available on this server" },
        { status: 404 }
      );
    }

    const fileBuffer = fs.readFileSync(zipPath);
    const blob = new Blob([fileBuffer], { type: "application/zip" });
    const formData = new FormData();
    formData.append("file", blob, "calculator.zip");

    const response = await fetch(`${backendUrl}/api/repositories/upload`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: "Upload failed" }));
      return NextResponse.json(err, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load sample repository" },
      { status: 500 }
    );
  }
}
