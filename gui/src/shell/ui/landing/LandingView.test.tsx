import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LandingView } from "./LandingView";

const labQuery = vi.hoisted(() => ({
  data: [{ id: "lab-1" }],
  isLoading: false,
  isError: false,
}));

vi.mock("@shell/data/labs/labs", () => ({
  useLabs: () => labQuery,
}));

function renderLanding() {
  const props = {
    onLoad: vi.fn(),
    onViewLabs: vi.fn(),
    onViewReeIndex: vi.fn(),
  };
  render(<LandingView {...props} />);
  return props;
}

describe("LandingView", () => {
  beforeEach(() => {
    labQuery.data = [{ id: "lab-1" }];
    labQuery.isLoading = false;
    labQuery.isError = false;
    vi.unstubAllEnvs();
  });

  it("opens the existing create and load flows", () => {
    const { onLoad } = renderLanding();

    fireEvent.click(screen.getByRole("button", { name: "Create a new REE" }));
    fireEvent.click(screen.getByRole("button", { name: "Load existing REE" }));

    expect(onLoad).toHaveBeenNthCalledWith(1, "/lab-location");
    expect(onLoad).toHaveBeenNthCalledWith(2, "/lab-location?load=1");
  });

  it("opens the REE index from the utility navigation", () => {
    const { onViewReeIndex } = renderLanding();
    fireEvent.click(screen.getByRole("button", { name: "REE index" }));
    expect(onViewReeIndex).toHaveBeenCalledOnce();
  });

  it("shows truthful readiness for a connected lab", () => {
    renderLanding();
    expect(screen.getByText("A connected lab is ready to provision your workbench.")).toBeVisible();
  });

  it("links to lab management when no lab is connected", () => {
    labQuery.data = [];
    const { onViewLabs } = renderLanding();

    expect(screen.getByText("No lab is connected.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "View labs" }));
    expect(onViewLabs).toHaveBeenCalledOnce();
  });

  it("does not make a readiness claim while loading or after an error", () => {
    labQuery.isLoading = true;
    const { unmount } = render(
      <LandingView onLoad={vi.fn()} onViewLabs={vi.fn()} onViewReeIndex={vi.fn()} />,
    );
    expect(screen.getByText("Checking for a connected lab…")).toBeVisible();

    unmount();
    labQuery.isLoading = false;
    labQuery.isError = true;
    renderLanding();
    expect(screen.getByText("Lab status is unavailable.")).toBeVisible();
  });

  it("keeps GitHub disabled until a destination is configured", () => {
    renderLanding();
    expect(screen.getByTitle("GitHub link not configured")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("uses the configured GitHub destination", () => {
    vi.stubEnv("VITE_GITHUB_URL", "https://github.com/example/repo2ree");
    renderLanding();
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/example/repo2ree",
    );
  });
});
