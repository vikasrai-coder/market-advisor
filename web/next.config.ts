import type { NextConfig } from "next";

const API_BASE = process.env.NODE_ENV === "development"
  ? "http://localhost:8000"
  : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");


const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/health",
        destination: `${API_BASE}/health`,
      },
      {
        source: "/api/:path*",
        destination: `${API_BASE}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
