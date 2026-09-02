import type { Lab } from "@core/lab/Lab";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LabLocationView } from "./LabLocationView";
import { LabsView } from "./LabsView";

const useLabsMock = vi.hoisted(() => vi.fn());

vi.mock("@shell/data/labs/labs", () => ({ useLabs: useLabsMock }));
vi.mock("./WorkbenchSetupDrawer", () => ({
  WorkbenchSetupDrawer: ({ lab }: { lab: { label: string } }) => <div>Setup for {lab.label}</div>,
}));

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

describe("lab query states", () => {
  beforeEach(() => useLabsMock.mockReset());

  it("announces an inventory load failure", () => {
    useLabsMock.mockReturnValue(
      queryState({ isError: true, error: new Error("control plane unavailable") }),
    );

    render(<LabsView onBack={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Failed to load labs: control plane unavailable",
    );
  });

  it("uses the shared danger notice for a location load failure", () => {
    useLabsMock.mockReturnValue(
      queryState({ isError: true, error: new Error("control plane unavailable") }),
    );

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("data-tone", "danger");
    expect(alert).toHaveTextContent("Failed to load labs: control plane unavailable");
  });

  it("announces loading without treating it as a failure", () => {
    useLabsMock.mockReturnValue(queryState({ isLoading: true }));
    const inventory = render(<LabsView onBack={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading labs…");
    inventory.unmount();

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading labs…");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shares the no-lab recovery instruction between both contexts", () => {
    useLabsMock.mockReturnValue(queryState({ data: [] }));
    const inventory = render(<LabsView onBack={vi.fn()} />);
    expect(screen.getByText("No labs connected")).toBeInTheDocument();
    expect(screen.getByText(/WORKBENCH_API_WS_URL=/)).toBeInTheDocument();
    inventory.unmount();

    render(
      <MemoryRouter>
        <LabLocationView onBack={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText("No labs connected")).toBeInTheDocument();
    expect(screen.getByText(/WORKBENCH_API_WS_URL=/)).toBeInTheDocument();
  });
});

// ── The lab picker's grid ─────────────────────────────────────────────────

function lab(overrides: Partial<Lab> = {}): Lab {
  return {
    id: "lab-oslo",
    label: "lab-oslo-01",
    description: "",
    lifecycleMode: "provider_managed",
    profiles: [
      {
        id: "standard",
        revision: "1",
        label: "Standard",
        description: "",
        substrate: "docker-nested",
        storagePolicy: "ephemeral",
      },
    ],
    status: "connected",
    available: true,
    ...overrides,
  };
}

function fleet(count: number): Lab[] {
  return Array.from({ length: count }, (_, index) => {
    const n = String(index + 1).padStart(2, "0");
    return lab({ id: `lab-${n}`, label: `lab-${n}` });
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
  beforeEach(() => useLabsMock.mockReset());

  it("names each bay by its state, so the lamp is not the only signal", () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(3) }));
    renderPicker();

    // The bay shows "connected" as an unlabelled lamp; the accessible name is
    // what carries it, and what the e2e selectors match on.
    expect(screen.getAllByRole("button", { name: /available/ })).toHaveLength(3);
    expect(screen.getByRole("button", { name: "lab-02 — available" })).toBeInTheDocument();
  });

  it("opens workbench setup for the lab that was chosen", async () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(3) }));
    renderPicker();

    expect(screen.queryByRole("region", { name: "Set up the workbench" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "lab-02 — available" }));

    const setup = screen.getByRole("region", { name: "Set up the workbench" });
    expect(setup).toHaveTextContent("Setup for lab-02");
    expect(screen.getByRole("button", { name: "lab-02 — available" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("keeps the choice when setup is dismissed", async () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(3) }));
    renderPicker();

    await userEvent.click(screen.getByRole("button", { name: "lab-02 — available" }));
    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("region", { name: "Set up the workbench" })).not.toBeInTheDocument();
    // The lab stays chosen and confirmed in the rail — closing setup is not
    // the same as unpicking the lab.
    expect(screen.getByRole("button", { name: "lab-02 — available" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Specimen pod · assigned")).toBeInTheDocument();
  });

  it("confirms the choice in the detail panel rather than in the grid", async () => {
    useLabsMock.mockReturnValue(
      queryState({
        data: [
          lab({
            profiles: [
              {
                id: "shared",
                revision: "1",
                label: "Shared",
                description: "",
                substrate: "docker-host-socket",
                storagePolicy: "ephemeral",
              },
            ],
          }),
          ...fleet(2),
        ],
      }),
    );
    renderPicker();

    expect(screen.getByText("No lab chosen")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "lab-oslo-01 — available" }));

    expect(screen.getByText("Specimen pod · assigned")).toBeInTheDocument();
    // The wire's docker_mode is rendered as what it costs the author.
    expect(screen.getByText("shared daemon")).toBeInTheDocument();
  });

  it("arms the only connected lab, so a single-lab install is one click", () => {
    useLabsMock.mockReturnValue(queryState({ data: [lab()] }));
    renderPicker();

    expect(screen.getByRole("button", { name: "lab-oslo-01 — available" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Armed, but not committed: setup is opened by an explicit choice, so the
    // single-lab install still gets to see the image options before it runs.
    expect(screen.queryByRole("region", { name: "Set up the workbench" })).not.toBeInTheDocument();
  });

  it("does not arm anything when there is a choice to make", () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(2) }));
    renderPicker();

    expect(screen.getByText("No lab chosen")).toBeInTheDocument();
    expect(screen.queryByText("Specimen pod · assigned")).not.toBeInTheDocument();
  });

  it("filters the fleet down and says what it is showing", async () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(12) }));
    renderPicker();

    expect(screen.getByText("12 labs connected")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox", { name: "Filter labs" }), "lab-07");

    expect(screen.getByText("1 of 12 labs")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /available/ })).toHaveLength(1);
  });

  it("reports a filter that matches nothing instead of showing an empty grid", async () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(4) }));
    renderPicker();

    await userEvent.type(screen.getByRole("searchbox", { name: "Filter labs" }), "nothing");

    expect(screen.getByText(/No lab matches/)).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /available/ })).toHaveLength(0);
  });

  it("pages a fleet too large for one grid", async () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(12) }));
    renderPicker();

    expect(screen.getByText("page 1 / 2")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /available/ })).toHaveLength(8);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Next page" }));

    expect(screen.getByText("page 2 / 2")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /available/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows no pager when the whole fleet fits", () => {
    useLabsMock.mockReturnValue(queryState({ data: fleet(4) }));
    renderPicker();

    expect(screen.queryByRole("navigation", { name: "Lab pages" })).not.toBeInTheDocument();
  });
});
