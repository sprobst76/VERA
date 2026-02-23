/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://192.168.0.144:31367",
    NEXT_PUBLIC_DEMO_HOSTNAME: process.env.NEXT_PUBLIC_DEMO_HOSTNAME || "",
  },
};

export default nextConfig;
