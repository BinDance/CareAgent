/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@elder-care/ui', '@elder-care/shared-types'],
  async rewrites() {
    const apiBaseUrl =
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      'http://127.0.0.1:8000';

    return [
      {
        source: '/api/:path*',
        destination: `${apiBaseUrl}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
