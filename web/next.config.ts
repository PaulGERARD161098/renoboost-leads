import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Expose le SHA du commit déployé (fourni par Vercel) au bundle client, pour
  // afficher la version exacte en ligne (page de connexion + header).
  env: {
    NEXT_PUBLIC_BUILD_SHA: process.env.VERCEL_GIT_COMMIT_SHA ?? "",
  },
};

export default nextConfig;
