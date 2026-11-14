import type { NextConfig } from "next";

// L0/L1 最小配置。API 基址经 FLINT_API_BASE 注入（服务器态）。
const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
