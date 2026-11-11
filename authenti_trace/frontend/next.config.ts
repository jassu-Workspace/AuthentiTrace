import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server output for the Docker image (frontend/Dockerfile)
  output: "standalone",
  // The /api proxy must see paths exactly as sent: the backend's routes end in a slash (/api/v1/jobs/)
  skipTrailingSlashRedirect: true,
  turbopack: {
    // Keep root pinned to this frontend folder so Next.js does not infer a parent lockfile.
    root: process.cwd(),
  },
};

export default nextConfig;
