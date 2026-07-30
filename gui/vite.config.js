import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  resolve: {
    alias: {
      '@core': fileURLToPath(new URL('./src/core', import.meta.url)),
      '@shell': fileURLToPath(new URL('./src/shell', import.meta.url)),
    },
  },
  plugins: [react()],
  test: {
    exclude: ["tests/e2e/**", "tests/demo/**", "node_modules/**", "dist/**"],
    // Coverage for `make gui-tests`, which always measures. The suite runs in node —
    // 57 pure-logic files, no component rendering — so its report is the
    // `node` runtime under the shared artifact root, sibling to the browser V8
    // reports the stack tiers produce. reportsDirectory resolves against this
    // config's directory, not the cwd, which is what keeps it correct however
    // vitest is invoked.
    coverage: {
      provider: "istanbul",
      reportsDirectory: "../test-artifacts/coverage/node/unit",
      reporter: ["html", "text-summary", "lcovonly"],
      // Extension-scoped, and `all` on purpose. Without `all`, istanbul reports
      // only the files some test imported, which reads ~62% — a number that
      // improves when you delete a test. With it, untested files count as zero
      // and the tier reads ~23%: the UI shell is barely touched here, because
      // the browser tier is what exercises it. Same floor-vs-truth caveat the
      // python `unit` tier carries. (`src/**` unscoped also tries to
      // instrument a stray src/.DS_Store and dies.)
      all: true,
      include: ["src/**/*.ts", "src/**/*.tsx"],
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API calls to the backend FastAPI server
      '/api': 'http://localhost:8000'
    }
  }
})
