import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./__tests__/setup.ts"],
    include: ["__tests__/**/*.test.{ts,tsx}"],
    testTimeout: 15000,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["app/**", "components/**", "store/**", "services/**"],
      exclude: ["node_modules", ".next"],
      thresholds: {
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
