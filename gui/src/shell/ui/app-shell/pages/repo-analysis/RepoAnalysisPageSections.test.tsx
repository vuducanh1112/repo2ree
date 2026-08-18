import type { DependencyGroup } from "@core/evaluate/dependencyPresentation";
import type { ReproducibilityReport, Threat } from "@core/evaluate/Threat";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  RepoAnalysisAxesCard,
  RepoAnalysisDependenciesCard,
  RepoAnalysisMissingInputs,
  RepoAnalysisRunControls,
  RepoAnalysisThreatsCard,
  RepoAnalysisWorkspaceAside,
} from "./RepoAnalysisPageSections";

const report: ReproducibilityReport = {
  dependencyLevel: 1,
  dependencyLevelLabel: "Declared",
  environmentLevel: 0,
  environmentLevelLabel: "Uncaptured",
  machineLevel: 2,
  machineLevelLabel: "Detailed",
  dependencySummary: { manifests: 1, total: 1, pinned: 1, ranged: 0, unpinned: 0, locked: 0 },
  dependencies: [],
  sbomCrossCheck: null,
  threats: [],
};

const depGroups: DependencyGroup[] = [
  {
    path: "requirements.txt",
    ecosystem: "pypi",
    packages: [
      {
        name: "requests",
        version: "2",
        status: "pinned",
        scope: null,
        runtimePresence: null,
        observedVersion: null,
      },
    ],
  },
];

const threats: Threat[] = [
  {
    id: "dependency",
    category: "dependency",
    severity: "high",
    blocking: true,
    title: "Dependency threat",
    detail: "detail",
    remediation: "pin it",
    affected: Array.from({ length: 10 }, (_, index) => `package-${index}`),
  },
  {
    id: "machine",
    category: "machine",
    severity: "low",
    blocking: false,
    title: "Machine threat",
    detail: "detail",
    remediation: "describe it",
    affected: [],
  },
];

describe("repository analysis sections", () => {
  it("renders run, rerun, running, and cancel controls", () => {
    const onRun = vi.fn();
    const onCancel = vi.fn();
    const { rerender } = render(
      <RepoAnalysisRunControls
        running={false}
        runDone={false}
        disabled={false}
        onRun={onRun}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run Evaluate" }));
    rerender(
      <RepoAnalysisRunControls
        running={false}
        runDone
        disabled={false}
        onRun={onRun}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByRole("button", { name: "Re-run Evaluate" })).toBeInTheDocument();
    rerender(
      <RepoAnalysisRunControls
        running
        runDone
        disabled={false}
        onRun={onRun}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(onRun).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("shows missing inputs with and without a navigation callback", () => {
    const onGo = vi.fn();
    const missing = [{ field: "sourceAvailable" as const, label: "Source" }];
    const { rerender } = render(<RepoAnalysisMissingInputs missing={missing} onGoFields={onGo} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onGo).toHaveBeenCalledOnce();
    rerender(<RepoAnalysisMissingInputs missing={[]} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders awaiting and populated axis states", () => {
    const { rerender } = render(<RepoAnalysisAxesCard hasReport={false} report={null} />);
    expect(screen.getByText(/No Evaluate output yet/)).toBeInTheDocument();
    rerender(<RepoAnalysisAxesCard hasReport report={report} />);
    expect(screen.getAllByText("Declared")).not.toHaveLength(0);
    expect(screen.getByText("Detailed")).toBeInTheDocument();
  });

  it("renders dependency preflight, empty results, singular groups, and counts", () => {
    const { rerender } = render(
      <RepoAnalysisDependenciesCard
        hasRun={false}
        depGroups={[]}
        containerCount={0}
        nixCount={0}
      />,
    );
    expect(screen.getByText("requirements.txt")).toBeInTheDocument();
    rerender(
      <RepoAnalysisDependenciesCard hasRun depGroups={[]} containerCount={0} nixCount={0} />,
    );
    expect(screen.getByText("No manifest files found")).toBeInTheDocument();
    rerender(
      <RepoAnalysisDependenciesCard hasRun depGroups={depGroups} containerCount={1} nixCount={1} />,
    );
    expect(screen.getByText("1 manifest group")).toBeInTheDocument();
    expect(screen.getByText("Container files: 1")).toBeInTheDocument();
  });

  it("renders every threat state and dimension", () => {
    const { rerender } = render(
      <RepoAnalysisThreatsCard hasReport={false} threats={[]} loading={false} />,
    );
    expect(screen.getByText(/Run Evaluate to surface/)).toBeInTheDocument();
    rerender(<RepoAnalysisThreatsCard hasReport threats={[]} loading />);
    expect(screen.getByText("Loading report…")).toBeInTheDocument();
    rerender(<RepoAnalysisThreatsCard hasReport threats={[]} loading={false} />);
    expect(screen.getByText(/No reproducibility threats/)).toBeInTheDocument();
    rerender(<RepoAnalysisThreatsCard hasReport threats={threats} loading={false} />);
    expect(screen.getByText("Dependency threat")).toBeInTheDocument();
    expect(screen.getByText("Machine threat")).toBeInTheDocument();
    expect(screen.getByText("+2 more")).toBeInTheDocument();
    expect(screen.getByText(/blocking next level/)).toBeInTheDocument();
  });

  it.each([true, false])("renders workspace source state %s", (sourceLoadedInWorkspace) => {
    render(
      <RepoAnalysisWorkspaceAside
        sourceLoadedInWorkspace={sourceLoadedInWorkspace}
        containerCount={1}
        nixCount={2}
        manifestCount={3}
        fileCount={4}
      />,
    );
    expect(screen.getByText(sourceLoadedInWorkspace ? "Loaded" : "Not loaded")).toBeInTheDocument();
  });
});
