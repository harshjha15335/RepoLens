import type { NextConfig } from "next";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  distDir: process.env.REPOLENS_BUILD_DIR || ".next",
  allowedDevOrigins: process.env.REPOLENS_PREVIEW_HOST
    ? [process.env.REPOLENS_PREVIEW_HOST]
    : [],
  experimental: {
    // Local CPU generation can exceed the proxy's default 30-second limit.
    // Keep this above the backend's 120-second model response timeout.
    proxyTimeout: 150_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
