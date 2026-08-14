import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAgentUptimeClock } from "./useAgentUptimeClock";

describe("useAgentUptimeClock", () => {
  afterEach(() => vi.useRealTimers());

  it("ticks only while a view has agent uptimes to display", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-14T12:00:00Z"));
    const clock = renderHook(({ enabled }) => useAgentUptimeClock(enabled), {
      initialProps: { enabled: false },
    });
    const initialNow = clock.result.current;

    act(() => vi.advanceTimersByTime(2000));
    expect(clock.result.current).toBe(initialNow);

    clock.rerender({ enabled: true });
    act(() => vi.advanceTimersByTime(1000));
    expect(clock.result.current).toBe(initialNow + 3000);

    clock.rerender({ enabled: false });
    act(() => vi.advanceTimersByTime(2000));
    expect(clock.result.current).toBe(initialNow + 3000);
  });
});
