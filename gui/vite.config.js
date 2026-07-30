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
    // Coverage for `make gui-tests`, which always measures. This is the whole of
    // the GUI's coverage — the `node` runtime under the shared artifact root,
    // sibling to the python reports. The Playwright suites record none.
    // reportsDirectory resolves against this config's directory, not the cwd,
    // which is what keeps it correct however vitest is invoked.
    coverage: {
      provider: "v8",
      reportsDirectory: "../test-artifacts/coverage/node/unit",
      reporter: ["html", "text-summary", "lcovonly"],
      // Every file in `include` counts, whether a test imported it or not, so
      // the tier reads ~23%. That is a real gap, not an artifact: there are no
      // component tests yet, and the Playwright suites record no JS coverage, so
      // nothing measures the React shell. Component tests land here and lift it.
      //
      // Under the v8 provider that is what `include` alone already does — `all`
      // measures as a no-op here (true and false give byte-identical totals).
      // It stays because it names the property the number depends on: without
      // that behaviour, coverage reports only imported files and reads ~62%, a
      // figure that *improves when you delete a test*. That was istanbul's
      // default and cost an explicit flag to avoid; keeping the flag states the
      // requirement rather than trusting a provider default to stay put.
      all: true,
      // Extension-scoped: `src/**` unscoped also tries to instrument a stray
      // src/.DS_Store and dies.
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
