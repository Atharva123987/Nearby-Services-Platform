import { copyFileSync, mkdirSync } from "node:fs";
import type { NextConfig } from "next";

// The module worker imports its sibling by filename, so serve both assets together.
mkdirSync("public/maplibre", { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(
    require.resolve(`maplibre-gl/dist/${file}`),
    `public/maplibre/${file}`,
  );
}

const nextConfig: NextConfig = {
  async redirects() {
    return [{ source: "/nearby", destination: "/", permanent: true }];
  },
  // Self-contained server bundle for the Docker image.
  output: "standalone",
};

export default nextConfig;
