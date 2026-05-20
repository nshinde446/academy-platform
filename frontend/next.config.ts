import type { NextConfig } from "next";

// In dev:  unset → proxies /api/* to http://localhost:8000
// On Vercel: set API_BASE_URL=https://api.<yourdomain> in project env vars
const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_BASE_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
