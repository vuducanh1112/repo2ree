import type React from "react";
import { LEVELS } from "../../../../constants/levels";
import { PAGE } from "../../../../constants/pages";
import { isWorkflowServiceKey, SERVICES } from "../../../../constants/services";
import type { AppAction } from "../../../../context";
import { explorerActions } from "../../../../context";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import type {
  FileTreeNode,
  Ree,
  WorkflowServiceKey,
  WorkflowServiceRunParamsByKey,
} from "../../../../types";
import type { GenericServiceParams } from "../../../../types/services";
import {
  computeEvaluateLevelFromFiles,
  scanDependencies,
} from "../../../dependencies/dependencyParser";
import { makeLogs } from "../../services/logGenerator";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

interface CreateServiceRunHandlersArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  dispatch: React.Dispatch<AppAction>;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  workspaceServiceMode: "remote" | "mock";
}

type ServiceRunHandlerMap = {
  [K in WorkflowServiceKey]: (params: WorkflowServiceRunParamsByKey[K], newLevel: number) => void;
};

export function createServiceRunHandlers({
  ree,
  virtualFiles,
  dispatch,
  persistWorkspaceFile,
  showToast,
  workspaceServiceMode,
}: CreateServiceRunHandlersArgs): ServiceRunHandlerMap {
  return {
    build: (runParams) => {
      const runtimeTarget = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : null;
      const expectedOutput = String(
        runParams?._expectedOutput ? runParams._expectedOutput : "",
      ).trim();
      const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";
      const isTarball = /\.(tar|tar\.gz|tgz)$/i.test(producedName);
      let producedRuntimePath: string | null = null;
      if (workspaceServiceMode === "mock" && isTarball) {
        persistWorkspaceFile(
          producedName,
          `[mock binary — docker save | gzip output]\nBuilt: ${new Date().toISOString()}\nSize: ~1.2 GB (mock)`,
        );
        producedRuntimePath = producedName;
      }
      if (
        expectedOutput &&
        (workspaceServiceMode === "remote" || producedRuntimePath === expectedOutput)
      ) {
        dispatch(
          explorerActions.setRee((prevRee) => ({
            ...prevRee,
            runtime: expectedOutput,
            _runtimeIncluded: true,
          })),
        );
      } else if (workspaceServiceMode === "mock" && expectedOutput && !producedRuntimePath) {
        showToast(
          `Build finished, but expected runtime file was not produced: ${expectedOutput}`,
          "error",
        );
      }
      showToast(`Build complete${producedName ? ` — ${producedName} produced` : ""}`, "success");
    },
    sbom: () => {
      if (workspaceServiceMode === "remote") {
        dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, sbom: "sbom.json" })));
        showToast("SBOM generated — sbom.json", "success");
        return;
      }

      const sbomContent = JSON.stringify(
        {
          spdxVersion: "SPDX-2.3",
          dataLicense: "CC0-1.0",
          SPDXID: "SPDXRef-DOCUMENT",
          name: `${ree.name || "ree"}-sbom`,
          documentNamespace: `https://example.org/sbom/${ree.name || "ree"}-${Date.now()}`,
          creationInfo: {
            created: new Date().toISOString(),
            creators: ["Tool: syft via REE Explorer"],
          },
          packages: [
            {
              SPDXID: "SPDXRef-numpy",
              name: "numpy",
              versionInfo: "1.26.4",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-pandas",
              name: "pandas",
              versionInfo: "2.2.1",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-scipy",
              name: "scipy",
              versionInfo: "1.12.0",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
            {
              SPDXID: "SPDXRef-biopython",
              name: "biopython",
              versionInfo: "1.83",
              downloadLocation: "NOASSERTION",
              filesAnalyzed: false,
            },
          ],
        },
        null,
        2,
      );
      const fname = "sbom.json";
      persistWorkspaceFile(fname, sbomContent);
      dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, sbom: fname })));
      showToast("SBOM generated — sbom.json", "success");
    },
    activation: () => {
      showToast("Activation test passed — container started cleanly", "success");
    },
    evaluate: (_, newLevel) => {
      const depSummary = (() => {
        const groups = scanDependencies(virtualFiles || []);
        const depCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
        const manifestCount = groups.length;
        return `${depCount} dependenc${depCount === 1 ? "y" : "ies"} across ${manifestCount} manifest file${manifestCount === 1 ? "" : "s"}`;
      })();
      dispatch(
        explorerActions.setRee((prevRee) => ({
          ...prevRee,
          _evalLevel: newLevel,
          repro_level: `L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`,
          detected_dependencies: depSummary,
        })),
      );
      showToast(`L${newLevel} · ${LEVELS[Math.min(newLevel, 7)].label}`, "success");
    },
  };
}

interface ExecuteServiceRunArgs {
  key: string;
  params: GenericServiceParams;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  dispatch: React.Dispatch<AppAction>;
  showToast: ShowToast;
  serviceRunHandlers: ServiceRunHandlerMap;
  workspaceService: IWorkspaceService<FileTreeNode>;
  workspaceId: string;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export async function executeServiceRunAction({
  key,
  params,
  ree,
  level,
  virtualFiles,
  dispatch,
  showToast,
  serviceRunHandlers,
  workspaceService,
  workspaceId,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunArgs): Promise<WorkspaceServiceLogEntry> {
  dispatch(explorerActions.setActionStates((prevStates) => ({ ...prevStates, [key]: "loading" })));

  if (workspaceService.startWorkflowRun && workspaceService.getWorkflowRun) {
    const runParams =
      key === "activation"
        ? {
            ...params,
            activation_script: ree.activation_script,
          }
        : params;
    let runId: string | null = null;
    try {
      const run = await workspaceService.startWorkflowRun(workspaceId, key, runParams);
      runId = run.runId;
      onRunStarted?.(key, run.runId);
      const polledRun = await pollWorkflowRun(workspaceService, {
        workspaceId,
        runId: run.runId,
        onUpdate: (update) => {
          dispatch(
            explorerActions.setServiceLogs((prevLogs) => ({
              ...prevLogs,
              [key]: { lines: update.lines, ts: update.ts },
            })),
          );
        },
      });
      const lines = polledRun.lines;
      const ts = polledRun.ts;

      dispatch(
        explorerActions.setServiceLogs((prevLogs) => ({ ...prevLogs, [key]: { lines, ts } })),
      );
      dispatch(explorerActions.setActionStates((prevStates) => ({ ...prevStates, [key]: "done" })));
      dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, [key]: true })));
      dispatch(
        explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, [key]: ts })),
      );

      if (polledRun.status === "failed" || polledRun.status === "canceled") {
        showToast(`${key} ${polledRun.status}`, "error");
        return { lines, ts };
      }

      if (key === "build" || key === "sbom") {
        try {
          const workspace = await workspaceService.getWorkspace(workspaceId);
          dispatch(explorerActions.setVirtualFiles(workspace.files));
        } catch {
          // Keep run success status; UI can still show logs even if refresh fails.
        }
      }

      const isEvaluateRun = key === PAGE.EVALUATE;
      const newLevel = isEvaluateRun ? computeEvaluateLevelFromFiles(virtualFiles || []) : level;

      if (isWorkflowServiceKey(key)) {
        if (key === "evaluate") {
          serviceRunHandlers.evaluate(
            params as WorkflowServiceRunParamsByKey["evaluate"],
            newLevel,
          );
        } else if (key === "build") {
          serviceRunHandlers.build(params as WorkflowServiceRunParamsByKey["build"], newLevel);
        } else if (key === "sbom") {
          serviceRunHandlers.sbom(params as WorkflowServiceRunParamsByKey["sbom"], newLevel);
        } else {
          serviceRunHandlers.activation(
            params as WorkflowServiceRunParamsByKey["activation"],
            newLevel,
          );
        }
        return { lines, ts };
      }

      if (key === "create") {
        dispatch(explorerActions.setLocked(true));
        showToast("REE created — fields locked", "success");
      } else if (key === "swh") {
        const swhid = `swh:1:dir:${Math.random().toString(16).slice(2, 14)}`;
        dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, swhid })));
        showToast("Archived at Software Heritage — SWHID assigned", "success");
      } else if (key === "zenodo") {
        const doi = `10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`;
        dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, zenodo_doi: doi })));
        showToast("Published on Zenodo — DOI assigned", "success");
      } else if (key === "dataverse") {
        const doi = `doi:10.5072/DVN/${Math.floor(Math.random() * 900000 + 100000)}`;
        dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, dataverse_doi: doi })));
        showToast("Dataset published on Dataverse — DOI assigned", "success");
      } else {
        const svc = SERVICES.find((service) => service.key === key);
        showToast(`${svc?.label ?? key} completed`, "success");
      }

      return { lines, ts };
    } finally {
      if (runId) {
        onRunFinished?.(key);
      }
    }
  }

  await new Promise((resolve) => setTimeout(resolve, 1600 + Math.random() * 700));

  const isEvaluateRun = key === PAGE.EVALUATE;
  const newLevel = isEvaluateRun ? computeEvaluateLevelFromFiles(virtualFiles || []) : level;
  const lines = makeLogs(key, ree, params, newLevel);
  const ts = new Date().toISOString();

  dispatch(explorerActions.setServiceLogs((prevLogs) => ({ ...prevLogs, [key]: { lines, ts } })));
  dispatch(explorerActions.setActionStates((prevStates) => ({ ...prevStates, [key]: "done" })));
  onRunFinished?.(key);
  dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, [key]: true })));
  dispatch(explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, [key]: ts })));

  if (isWorkflowServiceKey(key)) {
    if (key === "evaluate") {
      serviceRunHandlers.evaluate(params as WorkflowServiceRunParamsByKey["evaluate"], newLevel);
    } else if (key === "build") {
      serviceRunHandlers.build(params as WorkflowServiceRunParamsByKey["build"], newLevel);
    } else if (key === "sbom") {
      serviceRunHandlers.sbom(params as WorkflowServiceRunParamsByKey["sbom"], newLevel);
    } else {
      serviceRunHandlers.activation(
        params as WorkflowServiceRunParamsByKey["activation"],
        newLevel,
      );
    }
    return { lines, ts };
  }

  if (key === "create") {
    dispatch(explorerActions.setLocked(true));
    showToast("REE created — fields locked", "success");
  } else if (key === "swh") {
    const swhid = `swh:1:dir:${Math.random().toString(16).slice(2, 14)}`;
    dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, swhid })));
    showToast("Archived at Software Heritage — SWHID assigned", "success");
  } else if (key === "zenodo") {
    const doi = `10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`;
    dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, zenodo_doi: doi })));
    showToast("Published on Zenodo — DOI assigned", "success");
  } else if (key === "dataverse") {
    const doi = `doi:10.5072/DVN/${Math.floor(Math.random() * 900000 + 100000)}`;
    dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, dataverse_doi: doi })));
    showToast("Dataset published on Dataverse — DOI assigned", "success");
  } else {
    const svc = SERVICES.find((service) => service.key === key);
    showToast(`${svc?.label ?? key} completed`, "success");
  }

  return { lines, ts };
}
