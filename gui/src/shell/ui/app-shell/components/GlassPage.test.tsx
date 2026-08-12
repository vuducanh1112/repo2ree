import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GlassPageHeader } from "./GlassPageHeader";
import { GlassPanelFooter } from "./GlassPanelFooter";
import { GlassSectionHeader } from "./GlassSectionHeader";
import { GlassSubPanel } from "./GlassSubPanel";

describe("GlassPageHeader", () => {
  it("titles the page as a heading, not as styled text", () => {
    render(
      <GlassPageHeader icon={<svg aria-hidden />} title="Build Runtime" subtitle="Build it." />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Build Runtime" })).toBeInTheDocument();
  });

  it("carries the page's tone as one custom property, not three colours", () => {
    // The `iconTint` object this replaces made every call site restate the
    // border and the glow; they are derived from the tint now.
    const { container } = render(
      <GlassPageHeader
        icon={<svg aria-hidden />}
        tint="var(--stage-build-line)"
        title="Build Runtime"
        subtitle="Build it."
      />,
    );
    const icon = container.querySelector("[data-tinted]") as HTMLElement;
    expect(icon.style.getPropertyValue("--page-tint")).toBe("var(--stage-build-line)");
  });

  it("falls back to the default chrome when a page has no stage of its own", () => {
    const { container } = render(
      <GlassPageHeader icon={<svg aria-hidden />} title="Files" subtitle="Browse." />,
    );
    expect(container.querySelector("[data-tinted]")).toBeNull();
  });
});

describe("GlassSectionHeader", () => {
  it("nests under the page title as a level-2 heading", () => {
    render(<GlassSectionHeader icon={<svg aria-hidden />} title="Catalog" />);
    expect(screen.getByRole("heading", { level: 2, name: "Catalog" })).toBeInTheDocument();
  });

  it("omits the subtitle line rather than rendering an empty one", () => {
    const { container } = render(<GlassSectionHeader icon={<svg aria-hidden />} title="Catalog" />);
    expect(container.textContent).toBe("Catalog");
  });
});

describe("GlassPanelFooter", () => {
  it("shows its hint and its trailing action", () => {
    render(
      <GlassPanelFooter action={<button type="button">Next: Seal</button>}>
        Deposit can proceed before sealing.
      </GlassPanelFooter>,
    );
    expect(screen.getByText("Deposit can proceed before sealing.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next: Seal" })).toBeInTheDocument();
  });

  it("switches to the standalone bar shape when asked", () => {
    const { container } = render(<GlassPanelFooter bar>Optional step.</GlassPanelFooter>);
    expect(container.firstChild).toHaveAttribute("data-shape", "bar");
  });

  it("welds to the panel above it by default", () => {
    const { container } = render(<GlassPanelFooter>Optional step.</GlassPanelFooter>);
    expect(container.firstChild).not.toHaveAttribute("data-shape");
  });
});

describe("GlassSubPanel", () => {
  it("wraps its section and takes nothing else", () => {
    // It used to accept a `style` object; no caller ever passed one, so the
    // hole closed rather than being re-typed.
    const { container } = render(
      <GlassSubPanel>
        <p>section</p>
      </GlassSubPanel>,
    );
    expect(container.firstChild).toHaveTextContent("section");
    expect((container.firstChild as HTMLElement).getAttribute("style")).toBeNull();
  });
});
