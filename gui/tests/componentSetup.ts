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

// jsdom implements Range but not its geometry, and CodeMirror measures the
// document through `Range.getClientRects` — on every animation frame, and again
// whenever a pointer lands in the editor and it has to turn coordinates back
// into a document position. Without this the script editor still behaves
// correctly — text, marks and selection are all asserted in the jsdom project —
// but each measure pass throws an uncaught TypeError out of a
// requestAnimationFrame or timer callback, where no test can catch it.
//
// One collapsed rect rather than none: CodeMirror binary-searches these rects,
// and an empty list sends that search off the end of its own child array. A
// zero-size rect is equally honest about a layout engine that laid nothing out,
// and keeps the search on a defined path. Real geometry is the Chromium
// project's to assert.
function collapsedRects(): DOMRectList {
  const rect = new DOMRect();
  return {
    length: 1,
    0: rect,
    item: (index: number) => (index === 0 ? rect : null),
    [Symbol.iterator]: function* () {
      yield rect;
    },
  } as unknown as DOMRectList;
}

// The interaction project runs this setup too, but Chromium already provides
// real geometry. Only install the fallback where Range geometry is absent.
if (typeof Range.prototype.getClientRects !== "function") {
  Range.prototype.getClientRects = collapsedRects;
  Range.prototype.getBoundingClientRect = () => new DOMRect();
  Element.prototype.getClientRects = collapsedRects;
}

// React Testing Library auto-cleans only when Vitest's `globals` are on, and
// they are deliberately off here — the suite imports `describe`/`it`/`expect`
// explicitly. So unmount by hand, or a component's DOM outlives its test and
// the next `getByRole` finds two matches.
afterEach(cleanup);
