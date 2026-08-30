import type { Agent } from "@core/agent/Agent";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
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

// ── The lab picker's grid ─────────────────────────────────────────────────

function lab(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-oslo",
    hostname: "lab-oslo-01",
    version: "0.8.0",
    dockerMode: "dind",
    connectedAt: "2026-07-01T00:00:00Z",
    status: "connected",
    ...overrides,
  };
}

function fleet(count: number): Agent[] {
  return Array.from({ length: count }, (_, index) => {
    const n = String(index + 1).padStart(2, "0");
    return lab({ id: `agent-${n}`, hostname: `lab-${n}` });
  });
}

function renderPicker() {
  return render(
    <MemoryRouter>
      <LabLocationView onBack={vi.fn()} />
    </MemoryRouter>,
  );
}

describe("choosing a lab", () => {
  beforeEach(() => useAgentsMock.mockReset());

  it("names each bay by its state, so the lamp is not the only signal", () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(3) }));
    renderPicker();

    // The bay shows "connected" as an unlabelled lamp; the accessible name is
    // what carries it, and what the e2e selectors match on.
    expect(screen.getAllByRole("button", { name: /connected/ })).toHaveLength(3);
    expect(screen.getByRole("button", { name: "lab-02 — connected" })).toBeInTheDocument();
  });

  it("will not continue until a lab is chosen", async () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(3) }));
    renderPicker();

    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
    expect(screen.getByText("No lab selected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "lab-02 — connected" }));

    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "lab-02 — connected" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("confirms the choice in the detail panel rather than in the grid", async () => {
    useAgentsMock.mockReturnValue(queryState({ data: [lab({ dockerMode: "host" }), ...fleet(2)] }));
    renderPicker();

    expect(screen.getByText("No lab chosen")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "lab-oslo-01 — connected" }));

    expect(screen.getByText("Specimen pod · assigned")).toBeInTheDocument();
    // The wire's docker_mode is rendered as what it costs the author.
    expect(screen.getByText("shared daemon")).toBeInTheDocument();
  });

  it("arms the only connected lab, so a single-agent install is one click", () => {
    useAgentsMock.mockReturnValue(queryState({ data: [lab()] }));
    renderPicker();

    expect(screen.getByRole("button", { name: "lab-oslo-01 — connected" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
  });

  it("does not arm anything when there is a choice to make", () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(2) }));
    renderPicker();

    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("filters the fleet down and says what it is showing", async () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(12) }));
    renderPicker();

    expect(screen.getByText("12 labs connected")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox", { name: "Filter labs" }), "lab-07");

    expect(screen.getByText("1 of 12 labs")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /connected/ })).toHaveLength(1);
  });

  it("reports a filter that matches nothing instead of showing an empty grid", async () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(4) }));
    renderPicker();

    await userEvent.type(screen.getByRole("searchbox", { name: "Filter labs" }), "nothing");

    expect(screen.getByText(/No lab matches/)).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /connected/ })).toHaveLength(0);
  });

  it("pages a fleet too large for one grid", async () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(12) }));
    renderPicker();

    expect(screen.getByText("page 1 / 2")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /connected/ })).toHaveLength(8);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Next page" }));

    expect(screen.getByText("page 2 / 2")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /connected/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows no pager when the whole fleet fits", () => {
    useAgentsMock.mockReturnValue(queryState({ data: fleet(4) }));
    renderPicker();

    expect(screen.queryByRole("navigation", { name: "Lab pages" })).not.toBeInTheDocument();
  });
});
