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
      // BioMax/ZKTeco devices push to a fixed /iclock/* path. Proxy it to the
      // backend so devices can use the public app host as their server URL.
      {
        source: "/iclock/:path*",
        destination: `${API_BASE_URL}/iclock/:path*`,
      },
    ];
  },
};

export default nextConfig;
