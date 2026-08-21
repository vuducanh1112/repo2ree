import { PAGE } from "@core/app-shell/pages";
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CompactWorkflowNav } from "./CompactWorkflowNav";

describe("CompactWorkflowNav", () => {
  it("exposes every workflow step and reports progress", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <CompactWorkflowNav
        page={PAGE.METADATA}
        ree={{
          ...createEmptyReeEditorViewModel(),
          spec: { ...createEmptyReeEditorViewModel().spec, name: "Responsive REE" },
        }}
        badges={{ build: true }}
        onNavigate={onNavigate}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "Open workflow navigation, current step: Provide Metadata",
      }),
    );

    expect(screen.getByRole("navigation", { name: "REE workflow" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2. Provide Metadata, complete" })).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByRole("button", { name: "5. Build Runtime, complete" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(10);

    await user.click(screen.getByRole("button", { name: "6. Generate SBOM, pending" }));
    expect(onNavigate).toHaveBeenCalledWith(PAGE.SBOM);
    expect(screen.queryByRole("navigation", { name: "REE workflow" })).not.toBeInTheDocument();
  });

  it("closes with Escape without navigating", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <CompactWorkflowNav
        page={PAGE.CANVAS}
        ree={createEmptyReeEditorViewModel()}
        badges={{}}
        onNavigate={onNavigate}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Open workflow navigation, current step: Overview" }),
    );
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("navigation", { name: "REE workflow" })).not.toBeInTheDocument();
    expect(onNavigate).not.toHaveBeenCalled();
  });
});
