/* biome-ignore-all lint/style/useNamingConvention: fixtures intentionally use the backend wire format */

import type { Page, Request, Route } from "@playwright/test";

export const VISUAL_REE_ID = "visual-ree";
const TS = "2026-04-12T09:30:00Z";

const auditStep = {
  evidence: "current",
  payload: "not_applicable",
  reasons: [],
};

const visualRee = {
  ree_id: VISUAL_REE_ID,
  ree: {
    subject: {
      schema_version: 1,
      definition: {
        name: "climate-model-lab",
        catalog: {
          description: "A reproducible regional climate analysis and validation environment.",
          version: "2.4.1",
          website: "https://example.org/climate-model",
          keywords: ["climate", "reproducibility", "python"],
          contributors: [
            {
              identifier: "0000-0002-1825-0097",
              name: "Ada Researcher",
              affiliation_name: "Example Climate Institute",
              affiliation_identifier: "https://ror.org/012345678",
            },
          ],
          corresponding_author_identifier: "0000-0002-1825-0097",
        },
        source: {
          origin_url: "https://github.com/example/climate-model.git",
          source_type: "git",
          requested_ref: "v2.4.1",
        },
        build_runtime: {
          build_runtime_script_path: "overlay/build.sh",
          build_runtime_script_digest: "sha256:build-script",
          build_runtime_script_size: 428,
          runtime_path: "artifacts/climate-runtime.tar",
        },
        test_activation: {
          run_script_path: "overlay/activate.sh",
          run_script_digest: "sha256:activation-script",
          run_script_size: 312,
          verify_script_path: "overlay/verify-activation.sh",
          verify_script_digest: "sha256:verify-activation",
          verify_script_size: 94,
        },
        hardware: {
          cpus: {
            "Intel Xeon Gold 6338": {
              vendor: "Intel",
              quantity: 2,
              cores_per_cpu: 32,
              threads_per_core: 2,
              architecture: "x86_64",
            },
          },
          memory: {
            "DDR4 ECC 32GB": {
              vendor: "Micron",
              quantity: 8,
              capacity_gb: 32,
              memory_type: "DDR4 ECC",
              speed_mt_s: 3200,
            },
          },
          storage: {
            "PM9A3 NVMe": {
              vendor: "Samsung",
              quantity: 1,
              capacity_gb: 1920,
              storage_type: "NVMe SSD",
              interface: "PCIe 4.0",
            },
          },
        },
        experiments: [
          {
            name: "regional-forecast",
            run_script_path: "overlay/experiments/regional-forecast.sh",
            run_script_digest: "sha256:experiment-script",
            run_script_size: 286,
            verify_script_path: "overlay/experiments/regional-forecast-verify.sh",
            verify_script_digest: "sha256:experiment-verify",
            verify_script_size: 102,
            output_paths: ["results/forecast.csv", "results/summary.json"],
          },
        ],
      },
      receipts: {
        source: {
          schema_version: 1,
          run_id: "run-source",
          started_at: TS,
          finished_at: "2026-04-12T09:30:08Z",
          duration_ms: 8000,
          recorded_at: "2026-04-12T09:30:08Z",
          operation: "acquire_source",
          origin_url: "https://github.com/example/climate-model.git",
          source_type: "git",
          requested_ref: "v2.4.1",
          resolved_revision: "8c73d0c4b798c4a7c3b9e35cc857cae01b6d8012",
          observed_swhid: "swh:1:dir:77f2d4ac15b0f86d25af6f5e70c1271e6c7f95b1",
          snapshot_digest: "sha256:source-snapshot",
        },
        evaluation: {
          schema_version: 1,
          run_id: "run-evaluate",
          started_at: TS,
          finished_at: "2026-04-12T09:31:00Z",
          duration_ms: 12000,
          recorded_at: "2026-04-12T09:31:00Z",
          operation: "evaluate_reproducibility",
          snapshot_digest: "sha256:source-snapshot",
          overlay_digest: "sha256:overlay",
          strict: false,
          dependency_level: 2,
          environment_level: 2,
          machine_level: 1,
          dependency_count: 14,
          manifest_count: 2,
          report_path: "artifacts/evaluation.json",
          report_digest: "sha256:evaluation",
          analyzer_version: "1.4.0",
        },
      },
      contents: { entries: [] },
    },
  },
  status: "draft",
  audit: {
    source: auditStep,
    evaluation: auditStep,
    hardware: auditStep,
    runtime: auditStep,
    sbom: auditStep,
    sbom_cross_check: auditStep,
    test_activation: auditStep,
    experiments: [{ name: "regional-forecast", ...auditStep }],
  },
  workbench_image: "ghcr.io/repo2ree/workbench:python-3.12",
  workspace_files: [
    { path: "upstream/README.md", kind: "source", size: 1840, content: "# Climate model\n" },
    {
      path: "upstream/pyproject.toml",
      kind: "source",
      size: 920,
      content: "[project]\nname='climate-model'\n",
    },
    {
      path: "upstream/src/model.py",
      kind: "source",
      size: 6840,
      content: "def forecast():\n    pass\n",
    },
    { path: "artifacts/climate-runtime.tar", kind: "generated", size: 12582912 },
  ],
  ree_files: [
    {
      path: "overlay/build.sh",
      kind: "ree",
      tag: "Overlay",
      size: 428,
      content: "#!/bin/sh\nset -eu\ndocker build .\n",
    },
    {
      path: "overlay/activate.sh",
      kind: "ree",
      tag: "Overlay",
      size: 312,
      content: "#!/bin/sh\nset -eu\npython -m climate_model\n",
    },
    {
      path: "overlay/verify-activation.sh",
      kind: "ree",
      tag: "Overlay",
      size: 94,
      content: "#!/bin/sh\npython --version\n",
    },
    {
      path: "artifacts/sbom.json",
      kind: "ree",
      tag: "Artifact",
      size: 2048,
      content: '{"bomFormat":"CycloneDX"}',
    },
  ],
};

const agents = {
  agents: [
    {
      agent_id: "agent-oslo",
      hostname: "lab-oslo-01",
      version: "0.8.0",
      docker_mode: "dind",
      connected_at: "2026-04-12T08:00:00Z",
    },
    {
      agent_id: "agent-zurich",
      hostname: "lab-zurich-02",
      version: "0.8.0",
      docker_mode: "host",
      connected_at: "2026-04-12T08:15:00Z",
    },
  ],
};

const images = {
  images: [
    {
      id: "python",
      ref: "ghcr.io/repo2ree/workbench:python-3.12",
      label: "Python 3.12",
      description: "Python, pip, uv, and common build tooling",
    },
    {
      id: "base",
      ref: "ghcr.io/repo2ree/workbench:base",
      label: "Base",
      description: "Minimal reproducibility workbench",
    },
  ],
  default_id: "python",
};

const index = {
  items: [
    {
      subject_digest: "sha256:5d07ab34fa2438fd42f381b67d6ee040e5214cc0f30d86771fdefae44d7df89b",
      name: "climate-model-lab",
      sealed_at: "2026-04-10T14:22:00Z",
      ree_version: "1",
      catalog_metadata: visualRee.ree.subject.definition.catalog,
      archive_attestations: [
        {
          archive: "swh",
          identifier: "swh:1:dir:77f2d4ac15b0f86d25af6f5e70c1271e6c7f95b1",
          record_url: "https://archive.softwareheritage.org",
        },
        {
          archive: "zenodo",
          identifier: "10.5281/zenodo.12345678",
          record_url: "https://zenodo.org/records/12345678",
        },
      ],
    },
    {
      subject_digest: "sha256:c4bcb27259e2e2e79432d748f52ccf1dd84bc1db3dc24f97653968203233ab82",
      name: "ocean-circulation-notebook",
      sealed_at: "2026-03-28T11:05:00Z",
      ree_version: "1",
      catalog_metadata: {
        description: "Ocean analysis",
        version: "1.0.0",
        website: "",
        keywords: [],
        contributors: [],
      },
      archive_attestations: [],
    },
  ],
  next_cursor: null,
};

const runs = {
  runs: [
    {
      run_id: "run-build",
      ree_id: VISUAL_REE_ID,
      operation: "build",
      status: "succeeded",
      created_at: TS,
      started_at: TS,
      finished_at: "2026-04-12T09:32:42Z",
      outputs: {},
    },
    {
      run_id: "run-evaluate",
      ree_id: VISUAL_REE_ID,
      operation: "evaluate",
      status: "succeeded",
      created_at: TS,
      started_at: TS,
      finished_at: "2026-04-12T09:31:00Z",
      outputs: {},
    },
  ],
  next_cursor: null,
};

const evaluateReport = {
  dependency_level: 2,
  environment_level: 2,
  machine_level: 1,
  dependency_summary: { total: 14, locked: 8, pinned: 4, ranged: 2, unpinned: 0, undeclared: 0 },
  dependencies: [],
  threats: [
    {
      id: "floating-base-image",
      category: "environment",
      severity: "medium",
      title: "Base image tag is mutable",
      description: "Pin the runtime image by digest.",
    },
    {
      id: "machine-cpu",
      category: "machine",
      severity: "low",
      title: "CPU architecture is declared",
      description: "Exact instruction extensions are not constrained.",
    },
  ],
  dependency_level_label: "Mostly locked",
  environment_level_label: "Declared",
  machine_level_label: "Described",
  detected_dependencies: "14 dependencies across Python and system packages",
};

const reviews = {
  reviews: [
    {
      review_id: "review-a13f9c2",
      created_at: "2026-04-12T10:00:00Z",
      updated_at: "2026-04-12T10:08:40Z",
      status: "completed",
      steps: ["source", "build", "activation", "experiments"].map((step) => ({
        step,
        status: "completed",
        started_at: "2026-04-12T10:00:00Z",
        updated_at: "2026-04-12T10:08:40Z",
      })),
      source_comparison: {
        policy: "swhid",
        basis: "independent",
        expected_swhid: "swh:1:dir:77f2d4ac15b0f86d25af6f5e70c1271e6c7f95b1",
        observed_swhid: "swh:1:dir:77f2d4ac15b0f86d25af6f5e70c1271e6c7f95b1",
        verdict: "identical",
      },
      build_comparison: {
        policy: "sbom-closure",
        basis: "independent",
        verdict: "equivalent",
        expected_runtime_digest: "sha256:author-runtime",
        observed_runtime_digest: "sha256:review-runtime",
        expected_sbom_digest: "sha256:author-sbom",
        observed_sbom_digest: "sha256:review-sbom",
        sbom_tool_version: "syft 1.20.0",
        expected_package_total: 2842,
        observed_package_total: 2842,
        matched: 2839,
        missing_count: 0,
        extra_count: 0,
        version_mismatch_count: 3,
        advisory_count: 0,
        missing: [],
        extra: [],
        version_mismatches: [
          {
            ecosystem: "pypi",
            name: "numpy",
            expected_version: "2.1.0",
            observed_version: "2.1.1",
          },
        ],
      },
      activation_outcome: {
        policy: "activation-probe",
        basis: "independent",
        verdict: "passed",
        runtime_digest: "sha256:review-runtime",
        run_exit_code: 0,
        verify_exit_code: 0,
      },
      experiment_comparisons: [
        {
          policy: "verify-script",
          basis: "independent",
          verdict: "reproduced",
          experiment_name: "regional-forecast",
          verify_script_path: "overlay/experiments/regional-forecast-verify.sh",
          expected_verify_script_digest: "sha256:experiment-verify",
          verify_script_digest: "sha256:experiment-verify",
          expected_verify_exit_code: 0,
          observed_verify_exit_code: 0,
          run_exit_code: 0,
          expected_output_digest: "sha256:author-result",
          observed_output_digest: "sha256:review-result",
          runtime_digest: "sha256:review-runtime",
        },
      ],
    },
  ],
};

const scriptTemplates = {
  build: { path: "overlay/build.sh", templates: [] },
  activation: {
    run_script_path: "overlay/activate.sh",
    verify_script_path: "overlay/verify-activation.sh",
    templates: [],
  },
  experiment: {
    run_script_path_pattern: "overlay/experiments/{slug}.sh",
    verify_script_path_pattern: "overlay/experiments/{slug}-verify.sh",
    templates: [],
  },
  verify: [],
};

function responseFor(request: Request): unknown {
  const url = new URL(request.url());
  const path = url.pathname;
  if (request.method() !== "GET")
    throw new Error(`Unexpected visual API mutation: ${request.method()} ${path}`);
  if (path === "/api/v1/agents") return agents;
  if (path === "/api/v1/workbench/images") return images;
  if (path === "/api/v1/script-templates") return scriptTemplates;
  if (path === "/api/v1/ree-index") return index;
  if (path === `/api/v1/rees/${VISUAL_REE_ID}`) return visualRee;
  if (path === `/api/v1/rees/${VISUAL_REE_ID}/runs`) return runs;
  if (path === `/api/v1/rees/${VISUAL_REE_ID}/evaluate/report`) return evaluateReport;
  if (path === `/api/v1/rees/${VISUAL_REE_ID}/receipts/author`) return { receipts: [] };
  if (path === `/api/v1/rees/${VISUAL_REE_ID}/reviews`) return reviews;
  throw new Error(`Unexpected visual API request: ${request.method()} ${path}`);
}

export async function installVisualScenario(page: Page): Promise<void> {
  await page.clock.install({ time: new Date(TS) });
  await page.route("**/api/v1/**", async (route: Route) => {
    try {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(responseFor(route.request())),
      });
    } catch (error) {
      await route.abort("failed");
      throw error;
    }
  });
}
