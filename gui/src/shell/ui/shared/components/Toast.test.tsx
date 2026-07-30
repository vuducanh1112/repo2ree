import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toast } from "./Toast";

describe("Toast", () => {
  it("shows its message", () => {
    render(<Toast message="Bundle published" type="success" onClose={() => {}} />);
    expect(screen.getByText("Bundle published")).toBeInTheDocument();
  });

  it("closes when dismissed", async () => {
    const onClose = vi.fn();
    render(<Toast message="Run failed" type="error" onClose={onClose} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onClose).toHaveBeenCalledOnce();
  });

  describe("auto-dismissal", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("closes itself after four seconds", () => {
      const onClose = vi.fn();
      render(<Toast message="Saved" type="info" onClose={onClose} />);

      vi.advanceTimersByTime(3999);
      expect(onClose).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1);
      expect(onClose).toHaveBeenCalledOnce();
    });

    it("cancels its timer on unmount, so a gone toast cannot close its successor", () => {
      const onClose = vi.fn();
      const { unmount } = render(<Toast message="Saved" type="info" onClose={onClose} />);

      unmount();
      vi.advanceTimersByTime(10_000);

      expect(onClose).not.toHaveBeenCalled();
    });

    it("restarts the countdown when the handler identity changes", () => {
      const first = vi.fn();
      const { rerender } = render(<Toast message="Saved" type="info" onClose={first} />);

      vi.advanceTimersByTime(3000);
      const second = vi.fn();
      rerender(<Toast message="Saved" type="info" onClose={second} />);
      vi.advanceTimersByTime(3000);

      // The effect depends on `onClose`, so a parent that passes an inline
      // arrow re-arms the timer on every render and the toast never leaves.
      expect(first).not.toHaveBeenCalled();
      expect(second).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1000);
      expect(second).toHaveBeenCalledOnce();
    });
  });
});
