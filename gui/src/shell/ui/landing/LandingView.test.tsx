import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LandingView } from "./LandingView";

const agentQuery = vi.hoisted(() => ({
  data: [{ id: "agent-1" }],
  isLoading: false,
  isError: false,
}));

vi.mock("@shell/data/agents/agents", () => ({
  useAgents: () => agentQuery,
}));

function renderLanding() {
  const props = {
    onLoad: vi.fn(),
    onViewAgents: vi.fn(),
    onViewReeIndex: vi.fn(),
  };
  render(<LandingView {...props} />);
  return props;
}

describe("LandingView", () => {
  beforeEach(() => {
    agentQuery.data = [{ id: "agent-1" }];
    agentQuery.isLoading = false;
    agentQuery.isError = false;
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

  it("shows truthful readiness for a connected agent", () => {
    renderLanding();
    expect(
      screen.getByText("A connected agent is ready to provision your workbench."),
    ).toBeVisible();
  });

  it("links to agent management when no agent is connected", () => {
    agentQuery.data = [];
    const { onViewAgents } = renderLanding();

    expect(screen.getByText("No workbench agent is connected.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "View agents" }));
    expect(onViewAgents).toHaveBeenCalledOnce();
  });

  it("does not make a readiness claim while loading or after an error", () => {
    agentQuery.isLoading = true;
    const { unmount } = render(
      <LandingView onLoad={vi.fn()} onViewAgents={vi.fn()} onViewReeIndex={vi.fn()} />,
    );
    expect(screen.getByText("Checking for a connected workbench agent…")).toBeVisible();

    unmount();
    agentQuery.isLoading = false;
    agentQuery.isError = true;
    renderLanding();
    expect(screen.getByText("Agent status is unavailable.")).toBeVisible();
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
