import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function POST() {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
    
    // Path to sample-repos/calculator.zip
    const zipPath = path.resolve(process.cwd(), "..", "sample-repos", "calculator.zip");

    if (!fs.existsSync(zipPath)) {
      return NextResponse.json(
        { error: `Sample ZIP file not found at ${zipPath}` },
        { status: 404 }
      );
    }

    const fileBuffer = fs.readFileSync(zipPath);
    const blob = new Blob([fileBuffer], { type: "application/zip" });
    const formData = new FormData();
    formData.append("file", blob, "calculator.zip");

    const response = await fetch(`${backendUrl}/api/repositories/upload`, {
      method: "POST",
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
