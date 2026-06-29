/** @type {import('next').NextConfig} */
const API = process.env.API_URL || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend so the browser stays same-origin.
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

module.exports = nextConfig;
