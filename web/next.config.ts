import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
   experimental: {
    serverComponentsExternalPackages: [],
  },
};

export default nextConfig;