import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("starts at the value it was given", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 400));
    expect(result.current).toBe("a");
  });

  it("settles only after the value has stopped changing", () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 400), {
      initialProps: { value: "a" },
    });

    rerender({ value: "b" });
    act(() => void vi.advanceTimersByTime(399));
    expect(result.current).toBe("a");

    act(() => void vi.advanceTimersByTime(1));
    expect(result.current).toBe("b");
  });

  it("collapses a run of changes into one settle", () => {
    // The point of the hook: a typed sentence is one check, not thirty.
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 400), {
      initialProps: { value: "a" },
    });

    for (const value of ["ab", "abc", "abcd"]) {
      rerender({ value });
      act(() => void vi.advanceTimersByTime(100));
    }
    expect(result.current).toBe("a");

    act(() => void vi.advanceTimersByTime(400));
    expect(result.current).toBe("abcd");
  });
});
