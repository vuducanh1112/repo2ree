import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toggle } from "./Toggle";

const tint = "var(--stage-seal-line)";

describe("Toggle", () => {
  it("exposes its state as a pressed button rather than as styling", async () => {
    const { rerender } = render(<Toggle on={false} tint={tint} onChange={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");

    rerender(<Toggle on={true} tint={tint} onChange={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("reports a click without changing its own state", async () => {
    const onChange = vi.fn();
    render(<Toggle on={false} tint={tint} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onChange).toHaveBeenCalledOnce();
    // The toggle is controlled: it stays off until the parent says otherwise.
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
  });

  it("does not report clicks while disabled", async () => {
    const onChange = vi.fn();
    render(<Toggle on={false} tint={tint} disabled onChange={onChange} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("names itself from `title` so it is addressable without a visible label", () => {
    render(<Toggle on={true} tint={tint} title="Show archived runs" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Show archived runs" })).toBeInTheDocument();
  });
});
