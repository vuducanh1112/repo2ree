import { LEVELS } from "../../constants/levels";
import type { AutomationStepKey, HBOM, Ree } from "../../types";
import type { GenericServiceParams } from "../../types/workflowSteps";
import { emptyHBOM } from "../../utils/hbom";

interface PersistedFilePlan {
  path: string;
  content: string;
}

interface BuildEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch?: Partial<Ree>;
  errorMessage?: string;
  successMessage: string;
}

interface SbomEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch: Partial<Ree>;
  successMessage: string;
}

interface HbomEffectPlan {
  reePatch?: Partial<Ree>;
  successMessage: string;
}

interface EvaluateEffectPlan {
  reePatch: Partial<Ree>;
  successMessage: string;
}

interface ActivationEffectPlan {
  successMessage: string;
}

interface WorkflowServiceEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch?: Partial<Ree>;
  errorMessage?: string;
  successMessage: string;
}

export function planBuildEffect(args: {
  ree: Ree;
  expectedOutput?: string;
  workspaceServiceMode: "remote" | "mock";
  timestamp: string;
}): BuildEffectPlan {
  const runtimeTarget =
    args.ree.runtime && args.ree.runtime !== "__skipped__" ? args.ree.runtime : null;
  const expectedOutput = String(args.expectedOutput || "").trim();
  const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";
  const isTarball = /\.(tar|tar\.gz|tgz)$/i.test(producedName);

  const persistedFile =
    args.workspaceServiceMode === "mock" && isTarball
      ? {
          path: producedName,
          content: `[mock binary — docker save | gzip output]\nBuilt: ${args.timestamp}\nSize: ~1.2 GB (mock)`,
        }
      : undefined;

  if (
    expectedOutput &&
    (args.workspaceServiceMode === "remote" || persistedFile?.path === expectedOutput)
  ) {
    return {
      persistedFile,
      reePatch: {
        runtime: expectedOutput,
        _runtimeIncluded: true,
      },
      successMessage: `Build complete${producedName ? ` — ${producedName} produced` : ""}`,
    };
  }

  return {
    persistedFile,
    errorMessage:
      args.workspaceServiceMode === "mock" && expectedOutput && !persistedFile
        ? `Build finished, but expected runtime file was not produced: ${expectedOutput}`
        : undefined,
    successMessage: `Build complete${producedName ? ` — ${producedName} produced` : ""}`,
  };
}

function buildMockHbom(): HBOM {
  return {
    ...emptyHBOM(),
    cpus: {
      "Intel Xeon Mock Host": {
        vendor: "Intel",
        quantity: 2,
        cores_per_cpu: 24,
        threads_per_core: 2,
        architecture: "x86_64",
        extra_info: { logical_cpus: 96, profile_source: "mock" },
      },
    },
    memory: {
      "Installed Memory": {
        vendor: "",
        quantity: 1,
        capacity_gb: 256,
        memory_type: "DDR5",
        speed_mt_s: 0,
        extra_info: { aggregate: true, profile_source: "mock" },
      },
    },
    storage: {
      "Mock NVMe": {
        vendor: "Mock",
        quantity: 1,
        capacity_gb: 2048,
        storage_type: "NVMe",
        interface: "PCIe",
        extra_info: { profile_source: "mock" },
      },
    },
    gpus: {},
    network: {},
    extra_info: { profiled_on: "mock-host" },
  };
}

export function planHbomEffect(workspaceServiceMode: "remote" | "mock"): HbomEffectPlan {
  if (workspaceServiceMode === "remote") {
    return {
      successMessage: "HBOM profiled from the current machine",
    };
  }

  return {
    reePatch: {
      hardware_description: buildMockHbom(),
    },
    successMessage: "HBOM profiled from the mock machine",
  };
}

export function planSbomEffect(args: {
  ree: Ree;
  workspaceServiceMode: "remote" | "mock";
  timestamp: string;
  namespaceSuffix: string;
}): SbomEffectPlan {
  if (args.workspaceServiceMode === "remote") {
    return {
      reePatch: { sbom: "sbom.json" },
      successMessage: "SBOM generated — sbom.json",
    };
  }

  const content = JSON.stringify(
    {
      spdxVersion: "SPDX-2.3",
      dataLicense: "CC0-1.0",
      SPDXID: "SPDXRef-DOCUMENT",
      name: `${args.ree.name || "ree"}-sbom`,
      documentNamespace: `https://example.org/sbom/${args.ree.name || "ree"}-${args.namespaceSuffix}`,
      creationInfo: {
        created: args.timestamp,
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

  return {
    persistedFile: {
      path: "sbom.json",
      content,
    },
    reePatch: { sbom: "sbom.json" },
    successMessage: "SBOM generated — sbom.json",
  };
}

export function planEvaluateEffect(args: {
  newLevel: number;
  dependencyCount: number;
  manifestCount: number;
}): EvaluateEffectPlan {
  const label = LEVELS[Math.min(args.newLevel, 7)].label;
  const depSummary = `${args.dependencyCount} dependenc${args.dependencyCount === 1 ? "y" : "ies"} across ${args.manifestCount} manifest file${args.manifestCount === 1 ? "" : "s"}`;

  return {
    reePatch: {
      _evalLevel: args.newLevel,
      repro_level: `L${args.newLevel} · ${label}`,
      detected_dependencies: depSummary,
    },
    successMessage: `L${args.newLevel} · ${label}`,
  };
}

export function planActivationEffect(): ActivationEffectPlan {
  return {
    successMessage: "Activation test passed — container started cleanly",
  };
}

export function planWorkflowServiceEffect(args: {
  key: AutomationStepKey;
  params: GenericServiceParams;
  ree: Ree;
  newLevel: number;
  workspaceServiceMode: "remote" | "mock";
  timestamp: string;
  namespaceSuffix: string;
  dependencyCount: number;
  manifestCount: number;
}): WorkflowServiceEffectPlan {
  if (args.key === "build") {
    return planBuildEffect({
      ree: args.ree,
      expectedOutput: args.params._expectedOutput ? String(args.params._expectedOutput) : "",
      workspaceServiceMode: args.workspaceServiceMode,
      timestamp: args.timestamp,
    });
  }

  if (args.key === "hbom") {
    return planHbomEffect(args.workspaceServiceMode);
  }

  if (args.key === "sbom") {
    return planSbomEffect({
      ree: args.ree,
      workspaceServiceMode: args.workspaceServiceMode,
      timestamp: args.timestamp,
      namespaceSuffix: args.namespaceSuffix,
    });
  }

  if (args.key === "activation") {
    return planActivationEffect();
  }

  return planEvaluateEffect({
    newLevel: args.newLevel,
    dependencyCount: args.dependencyCount,
    manifestCount: args.manifestCount,
  });
}
