/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/health",
        destination: "http://127.0.0.1:8000/api/health",
      },
    ];
  },
};

export default nextConfig;
