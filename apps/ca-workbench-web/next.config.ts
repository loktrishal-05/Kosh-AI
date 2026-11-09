import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.TAXSETU_API ?? "https://taxsetu-ai.vercel.app"}/api/:path*` }];
  },
};
export default config;
