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
    // One tier, two environments, split by extension. `.test.ts` is pure logic
    // and runs in node; `.test.tsx` renders components and needs a DOM.
    //
    // The split is not a preference. jsdom costs ~1.7s of environment setup per
    // file, so switching it on globally took the suite from 2.9s to 11s — and it
    // broke `scriptTemplates/paths.test.ts`, which reads a contract fixture off
    // disk through `import.meta.url` and cannot resolve it once that URL is
    // `http://`. Node tests want node.
    //
    // Projects split the *run*, not the measurement: `coverage` stays here, at
    // the root, and both projects report into the one scope below. So this stays
    // a single tier with a single number, which is what `make gui-tests` means.
    projects: [
      {
        extends: true,
        test: { name: "logic", include: ["src/**/*.test.ts"], environment: "node" },
      },
      {
        extends: true,
        test: {
          name: "component",
          include: ["src/**/*.test.tsx"],
          environment: "jsdom",
          setupFiles: ["./tests/componentSetup.ts"],
        },
      },
    ],
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
      // the tier reads ~29%. That is a real gap, not an artifact: the React
      // shell is only beginning to be covered, and the Playwright suites record
      // no JS coverage, so nothing else measures it. Component tests land in the
      // `component` project above and lift this number.
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
