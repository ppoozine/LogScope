import type { NextConfig } from "next";

const config: NextConfig = {
  // Next.js 16 blocks dev HMR resources from non-localhost origins by default.
  // Allow loopback IP and common LAN ranges so 127.0.0.1 / 192.168.x / 10.x
  // can connect to the dev WebSocket (`/_next/webpack-hmr`) without 403.
  allowedDevOrigins: ["127.0.0.1", "192.168.0.0/16", "10.0.0.0/8"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default config;
