import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

class NoopResizeObserver implements ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = NoopResizeObserver;

Object.defineProperty(SVGElement.prototype, "getScreenCTM", {
  configurable: true,
  value: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
});

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

if (typeof Range.prototype.getClientRects !== "function") {
  Range.prototype.getClientRects = collapsedRects;
  Range.prototype.getBoundingClientRect = () => new DOMRect();
  Element.prototype.getClientRects = collapsedRects;
}

afterEach(cleanup);
