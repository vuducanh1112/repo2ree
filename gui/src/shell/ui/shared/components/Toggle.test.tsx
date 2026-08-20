import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toggle } from "./Toggle";

const tint = "var(--stage-seal-line)";
const ariaLabel = "Include source in bundle";

describe("Toggle", () => {
  it("exposes its state as a pressed button rather than as styling", async () => {
    const { rerender } = render(
      <Toggle on={false} ariaLabel={ariaLabel} tint={tint} onChange={() => {}} />,
    );
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");

    rerender(<Toggle on={true} ariaLabel={ariaLabel} tint={tint} onChange={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("reports a click without changing its own state", async () => {
    const onChange = vi.fn();
    render(<Toggle on={false} ariaLabel={ariaLabel} tint={tint} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onChange).toHaveBeenCalledOnce();
    // The toggle is controlled: it stays off until the parent says otherwise.
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
  });

  it("does not report clicks while disabled", async () => {
    const onChange = vi.fn();
    render(<Toggle on={false} ariaLabel={ariaLabel} tint={tint} disabled onChange={onChange} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("uses a stable accessible name independently of its tooltip", () => {
    render(
      <Toggle on={true} ariaLabel={ariaLabel} tint={tint} title="Included" onChange={() => {}} />,
    );
    expect(screen.getByRole("button", { name: ariaLabel })).toBeInTheDocument();
  });
});
