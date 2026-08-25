import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
  type ReeEditorViewModelPatch,
} from "@core/ree-editor/reeEditorViewModel";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithShell } from "../../../../../../tests/support/renderApp";
import { PageArchive } from "./ArchivePage";

function renderArchive(reeOverrides: ReeEditorViewModelPatch = {}) {
  const onRun = vi.fn();
  const onGo = vi.fn();
  renderWithShell(
    <PageArchive
      ree={patchReeEditorViewModel(createEmptyReeEditorViewModel(), reeOverrides)}
      artifactStatus={{}}
      badges={{}}
      logs={{}}
      actionStates={{}}
      onRun={onRun}
      onGo={onGo}
    />,
  );
  return { onRun, onGo };
}

describe("PageArchive workflow", () => {
  it("explains missing prerequisites and keeps deposit unavailable", () => {
    renderArchive();
    expect(screen.getByText("Prereqs pending")).toBeInTheDocument();
    expect(screen.getByText("Source available", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deposit to Software Heritage" })).toBeDisabled();
  });

  it("collects destination parameters and submits a ready deposit", async () => {
    const user = userEvent.setup();
    const { onRun } = renderArchive({ source: { sourceAvailable: true } });
    await user.selectOptions(screen.getByLabelText("Visit type", { exact: false }), "tar");
    await user.click(screen.getByTitle("No"));
    await user.click(screen.getByRole("button", { name: "Deposit to Software Heritage" }));

    expect(onRun).toHaveBeenCalledWith("swh", {
      // biome-ignore lint/style/useNamingConvention: archive wire parameter
      visit_type: "tar",
      // biome-ignore lint/style/useNamingConvention: archive wire parameter
      metadata_only: true,
    });
  });

  it("switches repository requirements without duplicating workflow navigation", async () => {
    const user = userEvent.setup();
    renderArchive({ spec: { name: "Demo", sbom: "sbom.json" } });
    await user.click(screen.getByRole("button", { name: "Zenodo" }));
    expect(screen.getByRole("button", { name: "Deposit to Zenodo" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Next:/ })).not.toBeInTheDocument();
  });
});
