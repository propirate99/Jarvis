import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";
const isGithubPages = process.env.GITHUB_PAGES === "true" || process.env.GITHUB_ACTIONS === "true" || isProd;

const BACKEND_URL = process.env.NEXT_PUBLIC_JARVIS_API_URL ?? "http://127.0.0.1:8000";

const rawAllowedOrigins = process.env.JARVIS_ALLOWED_DEV_ORIGINS || "";
const allowedDevOrigins = [
  "localhost",
  "127.0.0.1",
  ...rawAllowedOrigins.split(",").map((o) => o.trim()).filter(Boolean),
];

const nextConfig: NextConfig = {
  // Static export for GitHub Pages
  output: isProd ? "export" : undefined,
  basePath: isGithubPages ? "/Jarvis" : "",
  assetPrefix: isGithubPages ? "/Jarvis/" : undefined,
  images: {
    unoptimized: true,
  },
  allowedDevOrigins,
  ...(!isProd && {
    async rewrites() {
      return [
        // Proxy all /api/* and /health, /chat, /modules etc. to the FastAPI backend.
        // This means the browser always talks to the Next.js server on its own origin,
        // so there is no CORS issue and no hardcoded hostname on the client.
        {
          source: "/api/:path*",
          destination: `${BACKEND_URL}/api/:path*`,
        },
        {
          source: "/health",
          destination: `${BACKEND_URL}/health`,
        },
        {
          source: "/chat/:path*",
          destination: `${BACKEND_URL}/chat/:path*`,
        },
        {
          source: "/modules/:path*",
          destination: `${BACKEND_URL}/modules/:path*`,
        },
        {
          source: "/reset",
          destination: `${BACKEND_URL}/reset`,
        },
        {
          source: "/overview/:path*",
          destination: `${BACKEND_URL}/overview/:path*`,
        },
        {
          source: "/budget/:path*",
          destination: `${BACKEND_URL}/budget/:path*`,
        },
        {
          source: "/assignments/:path*",
          destination: `${BACKEND_URL}/assignments/:path*`,
        },
        {
          source: "/events/:path*",
          destination: `${BACKEND_URL}/events/:path*`,
        },
        {
          source: "/recovery/:path*",
          destination: `${BACKEND_URL}/recovery/:path*`,
        },
        {
          source: "/behaviour/:path*",
          destination: `${BACKEND_URL}/behaviour/:path*`,
        },
        {
          source: "/preferences/:path*",
          destination: `${BACKEND_URL}/preferences/:path*`,
        },
      ];
    },
  }),
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
