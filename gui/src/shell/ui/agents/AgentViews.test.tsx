import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentsView } from "./AgentsView";
import { LabLocationView } from "./LabLocationView";

const useAgentsMock = vi.hoisted(() => vi.fn());

vi.mock("@shell/data/agents/agents", () => ({ useAgents: useAgentsMock }));

function queryState(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isError: false,
    isFetching: false,
    isLoading: false,
    refetch: vi.fn(),
    ...overrides,
  };
}

describe("agent query states", () => {
  beforeEach(() => useAgentsMock.mockReset());

  it("announces an inventory load failure", () => {
    useAgentsMock.mockReturnValue(
      queryState({ isError: true, error: new Error("control plane unavailable") }),
    );

    render(<AgentsView onBack={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Failed to load agents: control plane unavailable",
    );
  });

  it("uses the shared danger notice for a location load failure", () => {
    useAgentsMock.mockReturnValue(
      queryState({ isError: true, error: new Error("control plane unavailable") }),
    );

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-tone", "danger");
    expect(alert).toHaveTextContent("Failed to load agents: control plane unavailable");
  });

  it("announces loading without treating it as a failure", () => {
    useAgentsMock.mockReturnValue(queryState({ isLoading: true }));
    const inventory = render(<AgentsView onBack={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading agents…");
    inventory.unmount();

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading agents…");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shares the no-agent recovery instruction between both contexts", () => {
    useAgentsMock.mockReturnValue(queryState({ data: [] }));
    const inventory = render(<AgentsView onBack={vi.fn()} />);
    expect(screen.getByText("No agents connected")).toBeInTheDocument();
    expect(screen.getByText(/WORKBENCH_API_WS_URL=/)).toBeInTheDocument();
    inventory.unmount();

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText("No agents connected")).toBeInTheDocument();
    expect(screen.getByText(/WORKBENCH_API_WS_URL=/)).toBeInTheDocument();
  });
});
