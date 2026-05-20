/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ['192.168.0.113'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
        has: [{ type: 'method', methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'] }],
      },
      {
        source: '/health',
        destination: 'http://localhost:8000/health',
      },
      {
        source: '/ws/:path*',
        destination: 'http://localhost:8000/ws/:path*',
      },
    ]
  },
}

module.exports = nextConfig