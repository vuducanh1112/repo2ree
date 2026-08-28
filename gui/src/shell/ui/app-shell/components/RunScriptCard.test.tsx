/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { RunScriptCard } from "./RunScriptCard";
import { ScriptAnalysis } from "./ScriptAnalysis";

// The seam this file exists for: the analysis panel discovers the findings, but
// the editor is the thing that can point at the line. The card wires the two
// together, so only a test that renders both can show that a finding actually
// lands on the line it names.

const SCRIPT = "#!/usr/bin/env bash\ndocker build .\nexit 0\n";

const FINDING = {
  code: "exit_status_masked_by_pipe",
  tier: "contract",
  severity: "warning",
  blocking: false,
  message: "The command is piped, so a failing run can be recorded as a pass.",
  path: "overlay/build.sh",
  line: 2,
};

function savedReport(findings: unknown[]) {
  return {
    reports: [
      {
        schema_version: 1,
        engine_version: "1",
        target: { kind: "build", path: "overlay/build.sh" },
        findings,
        tiers: [{ tier: "contract", status: "ran" }],
      },
    ],
    missing_scripts: [],
  };
}

function renderCard(findings: unknown[]) {
  const lintReeScripts = vi.fn().mockResolvedValue(savedReport(findings));
  renderWithShell(
    <RunScriptCard
      label="Build script"
      currentContent={SCRIPT}
      onSave={vi.fn()}
      renderAnalysis={(content, dirty, focusLine) => (
        <ScriptAnalysis
          target={{ kind: "build" }}
          source={content}
          dirty={dirty}
          runtimePath="runtime.tar"
          onFocusLine={focusLine}
        />
      )}
    />,
    { reeId: "ree-1", services: fakeApiServices({ ree: { lintReeScripts } }) },
  );
}

describe("RunScriptCard", () => {
  it("draws a finding on the line of the script it names", async () => {
    renderCard([FINDING]);

    await screen.findByText("1 warning");
    await waitFor(() => expect(document.querySelectorAll(".cm-lintRange-warning")).toHaveLength(1));
    // The second line is the one the finding named.
    const marked = document.querySelector(".cm-lintRange-warning");
    expect(marked?.closest(".cm-line")?.textContent).toBe("docker build .");
  });

  it("leaves the script unmarked when the checks come back clean", async () => {
    renderCard([]);

    await screen.findByText("No findings");
    expect(document.querySelectorAll(".cm-lintRange")).toHaveLength(0);
  });

  it("takes the editor to the line when the finding is clicked", async () => {
    renderCard([FINDING]);

    await userEvent.click(
      await screen.findByRole("button", { name: /exit_status_masked_by_pipe/ }),
    );

    await waitFor(() => expect(window.getSelection()?.toString()).toBe("docker build ."));
  });
});
