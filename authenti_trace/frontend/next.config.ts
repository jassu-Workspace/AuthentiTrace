import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Keep root pinned to this frontend folder so Next.js does not infer a parent lockfile.
    root: process.cwd(),
  },
};

export default nextConfig;
