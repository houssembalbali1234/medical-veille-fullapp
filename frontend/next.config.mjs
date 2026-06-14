/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  eslint: {
    ignoreDuringBuilds: true,   // ← désactive ESLint pendant npm run build
  },
};
export default nextConfig;
