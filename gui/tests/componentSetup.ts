// Setup for the `component` project of the `node` tier — the `*.test.tsx` files.
// The `logic` project runs in a node environment and does not load this.
//
// It is also in tsconfig.app.json's `include`, which is what makes the jest-dom
// matchers below visible to `tsc`: the import augments Vitest's `Assertion`
// interface, and a file outside the program augments nothing.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout observer. Components can still exercise their state and
// event behavior; geometry-specific assertions stay in the Chromium project.
class NoopResizeObserver implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = NoopResizeObserver;

// jsdom does not implement SVG coordinate transforms. Canvas effects only
// need an identity matrix here; browser-owned geometry remains covered by the
// Chromium interaction suite.
Object.defineProperty(SVGElement.prototype, "getScreenCTM", {
  configurable: true,
  value: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
});

// React Testing Library auto-cleans only when Vitest's `globals` are on, and
// they are deliberately off here — the suite imports `describe`/`it`/`expect`
// explicitly. So unmount by hand, or a component's DOM outlives its test and
// the next `getByRole` finds two matches.
afterEach(cleanup);
