import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./AppRoutes";

vi.mock("../landing/LandingView", () => ({
  LandingView: (props: {
    onLoad: (path: string) => void;
    onViewAgents: () => void;
    onViewReeIndex: () => void;
  }) => (
    <div>
      <button type="button" onClick={() => props.onLoad("/workspace?reeId=loaded")}>
        Load
      </button>
      <button type="button" onClick={props.onViewAgents}>
        Agents
      </button>
      <button type="button" onClick={props.onViewReeIndex}>
        Index
      </button>
    </div>
  ),
}));
vi.mock("../agents/LabLocationView", () => ({
  LabLocationView: ({ onBack }: { onBack: () => void }) => (
    <button type="button" onClick={onBack}>
      Lab back
    </button>
  ),
}));
vi.mock("../agents/AgentsView", () => ({
  AgentsView: ({ onBack }: { onBack: () => void }) => (
    <button type="button" onClick={onBack}>
      Agents back
    </button>
  ),
}));
vi.mock("../ree-index/ReeIndexView", () => ({
  ReeIndexView: ({ onBack }: { onBack: () => void }) => (
    <button type="button" onClick={onBack}>
      Index back
    </button>
  ),
}));
vi.mock("../app-shell/AppShellView", () => ({
  AppShellView: ({ onBack }: { onBack: () => void }) => (
    <button type="button" onClick={onBack}>
      Workspace back
    </button>
  ),
}));

function Location() {
  const location = useLocation();
  return <output>{`${location.pathname}${location.search}`}</output>;
}

function renderRoute(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppRoutes reportError={vi.fn()} />
      <Location />
    </MemoryRouter>,
  );
}

describe("AppRoutes", () => {
  it.each([
    ["/explorer", "/workspace"],
    ["/not-a-route", "/"],
  ])("redirects %s to %s", (route, expected) => {
    renderRoute(route);
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it("announces a lazy route while its chunk loads", () => {
    renderRoute("/lab-location");
    const loadingView = screen.getByText("Loading view…").closest("main");
    expect(loadingView).toHaveAttribute("role", "status");
    expect(loadingView).toHaveAttribute("aria-live", "polite");
  });

  it.each([
    ["/lab-location", "Lab back"],
    ["/agents", "Agents back"],
    ["/ree-index", "Index back"],
    ["/workspace?reeId=loaded", "Workspace back"],
    ["/workspace", "Workspace back"],
  ])("returns from %s to landing", async (route, button) => {
    renderRoute(route);
    fireEvent.click(await screen.findByRole("button", { name: button }));
    expect(screen.getByText("/")).toBeInTheDocument();
  });

  it.each([
    ["Load", "/workspace?reeId=loaded"],
    ["Agents", "/agents"],
    ["Index", "/ree-index"],
  ])("navigates from landing through %s", (button, expected) => {
    renderRoute("/");
    fireEvent.click(screen.getByRole("button", { name: button }));
    expect(screen.getByText(expected)).toBeInTheDocument();
  });
});
