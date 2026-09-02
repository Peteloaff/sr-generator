/** @type {import('next').NextConfig} */

// The desktop build (scripts/build_desktop.ps1) sets STATIC_EXPORT=1 so Next
// emits a pure static site into `out/` that FastAPI can serve with no Node
// runtime. Vercel keeps its normal build.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig = {
  reactStrictMode: true,
  ...(staticExport
    ? { output: "export", images: { unoptimized: true }, trailingSlash: true }
    : {}),
};

export default nextConfig;
