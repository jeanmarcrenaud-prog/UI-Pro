/** @type {import('next').NextConfig} */
const path = require('path')

// API target for rewrites. Local dev: http://localhost:8000 (default).
// Docker compose: set to the `api` service name via env var.
const apiTarget = process.env.API_PROXY_URL || 'http://localhost:8000'

const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ['192.168.0.113'],
  turbopack: {
    root: path.resolve(__dirname, '.'),
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${apiTarget}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${apiTarget}/health`,
      },
      {
        source: '/ws/:path*',
        destination: `${apiTarget}/ws/:path*`,
      },
    ]
  },
}

module.exports = nextConfig