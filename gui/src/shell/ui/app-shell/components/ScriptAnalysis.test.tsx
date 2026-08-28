/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { ScriptAnalysis } from "./ScriptAnalysis";

function report(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 1,
    engine_version: "1",
    target: { kind: "build", path: "ree-scripts/build_script.sh" },
    findings: [],
    tiers: [{ tier: "contract", status: "ran" }],
    ...overrides,
  };
}

const FINDING = {
  code: "exit_status_masked_by_pipe",
  tier: "contract",
  severity: "warning",
  blocking: false,
  message: "The command is piped, so a failing run can be recorded as a pass.",
  path: "ree-scripts/build_script.sh",
  line: 4,
};

function renderPanel(
  props: Partial<React.ComponentProps<typeof ScriptAnalysis>> = {},
  services = fakeApiServices(),
) {
  return renderWithShell(
    <ScriptAnalysis
      target={{ kind: "build" }}
      source="docker build .\n"
      dirty
      runtimePath="runtime.tar"
      {...props}
    />,
    { reeId: "ree-1", services },
  );
}

describe("ScriptAnalysis", () => {
  it("shows nothing while checks are disabled", () => {
    const { container } = renderPanel({ disabled: true });
    expect(container).toBeEmptyDOMElement();
  });

  it("reports a clean draft as checked, not as unchecked", async () => {
    const checkScriptDraft = vi.fn().mockResolvedValue(report());
    renderPanel({}, fakeApiServices({ ree: { checkScriptDraft } }));

    expect(await screen.findByText("No findings")).toBeInTheDocument();
    expect(screen.getByText("as you type")).toBeInTheDocument();
  });

  it("lists what it found, with the line it found it on", async () => {
    const checkScriptDraft = vi.fn().mockResolvedValue(report({ findings: [FINDING] }));
    renderPanel({}, fakeApiServices({ ree: { checkScriptDraft } }));

    expect(await screen.findByText("1 warning")).toBeInTheDocument();
    expect(screen.getByText("L4")).toBeInTheDocument();
    expect(screen.getByText("exit_status_masked_by_pipe")).toBeInTheDocument();
  });

  it("says which tier did not run rather than looking clean", async () => {
    // A bench without shellcheck must not be mistaken for a clean script.
    const checkScriptDraft = vi.fn().mockResolvedValue(
      report({
        tiers: [
          { tier: "contract", status: "ran" },
          { tier: "shell", status: "unavailable", detail: "shellcheck is not installed" },
        ],
      }),
    );
    renderPanel({}, fakeApiServices({ ree: { checkScriptDraft } }));

    expect(await screen.findByText(/shellcheck is not installed/)).toBeInTheDocument();
  });

  it("asks the workbench once the editor is clean, and says so", async () => {
    // Only the saved path can carry the tiers that need a process.
    const lintReeScripts = vi
      .fn()
      .mockResolvedValue({ reports: [report({ findings: [FINDING] })], missing_scripts: [] });
    renderPanel({ dirty: false }, fakeApiServices({ ree: { lintReeScripts } }));

    expect(await screen.findByText("on the saved script")).toBeInTheDocument();
    expect(lintReeScripts).toHaveBeenCalled();
  });

  it("reports a failed check instead of claiming the script is clean", async () => {
    const checkScriptDraft = vi.fn().mockRejectedValue(new Error("offline"));
    renderPanel({}, fakeApiServices({ ree: { checkScriptDraft } }));

    expect(await screen.findByText(/Checks unavailable: offline/)).toBeInTheDocument();
  });

  it("asks to be taken to the line a finding names", async () => {
    const onFocusLine = vi.fn();
    const checkScriptDraft = vi.fn().mockResolvedValue(report({ findings: [FINDING] }));
    renderPanel({ onFocusLine }, fakeApiServices({ ree: { checkScriptDraft } }));

    await userEvent.click(
      await screen.findByRole("button", { name: /exit_status_masked_by_pipe/ }),
    );
    await waitFor(() => expect(onFocusLine).toHaveBeenCalledWith(4));
  });
});
