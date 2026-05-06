import type { LogLine } from "../../../core/ree/ReeTypes";
import type {
  ReeAssemblyParam,
  ReeAssemblyParamValue,
} from "../../../core/ree-assembly/assemblyStepTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import { Ic } from "../../shared/components/Icon";

interface ReactivationStep {
  key: ReactivationStepKey;
  label: string;
  icon: (s?: number) => JSX.Element;
  color: string;
  desc: string;
  params?: ReeAssemblyParam[];
  logLines: (ree: ReeEditorViewModel, params?: ReactivationParams) => LogLine[];
}

export type ReactivationStepKey = "acquire_source" | "build_runtime" | "test_activation";
export type ReactivationParams = Record<string, ReeAssemblyParamValue>;

export const REACTIVATION_STEPS: ReactivationStep[] = [
  {
    key: "acquire_source",
    label: "Acquire Source",
    icon: Ic.archive,
    color: "#0891b2",
    desc: "Acquire source when it is not included in the uploaded review package.",
    logLines: (ree) =>
      ree.sourceIncluded
        ? [
            { type: "info", msg: "Source already included in uploaded archive." },
            { type: "ok", msg: "Source acquisition skipped ✓" },
          ]
        : [
            { type: "info", msg: "Acquiring source snapshot…" },
            { type: "info", msg: `  Origin: ${ree.origin_url || "(not set)"}` },
            { type: "info", msg: `  SWHID:  ${ree.swhid || "(not set)"}` },
            { type: "info", msg: `  DOI:    ${ree.zenodo_doi || "(not set)"}` },
            { type: "ok", msg: "Source snapshot acquired ✓" },
          ],
  },
  {
    key: "build_runtime",
    label: "Build Runtime",
    icon: Ic.cpu,
    color: "#7c3aed",
    desc: "Execute the build script from scratch with --no-cache to reconstruct the container image.",
    params: [
      {
        key: "no_cache",
        label: "No cache",
        type: "bool",
        default: true,
        hint: "Pass --no-cache to docker build",
      },
      {
        key: "platform",
        label: "Platform",
        type: "select",
        default: "linux/amd64",
        options: ["linux/amd64", "linux/arm64"],
        hint: "Target platform",
      },
    ],
    logLines: (ree, params) => [
      { type: "info", msg: `Platform: ${params?.platform || "linux/amd64"}` },
      { type: "info", msg: `No-cache: ${params?.no_cache !== false ? "yes" : "no"}` },
      { type: "info", msg: `Running: bash ${ree.build_runtime_script}` },
      { type: "info", msg: "DOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest ." },
      { type: "info", msg: "[1/6] FROM python:3.11.7-slim-bookworm" },
      { type: "info", msg: "[2/6] WORKDIR /app" },
      { type: "info", msg: "[3/6] COPY . ." },
      { type: "info", msg: "[4/6] RUN pip install --no-cache-dir -r requirements.txt" },
      { type: "info", msg: "  numpy==1.26.4 … installed" },
      { type: "info", msg: "  pandas==2.2.1 … installed" },
      { type: "info", msg: "  scipy==1.12.0 … installed" },
      { type: "info", msg: '[5/6] CMD ["python", "src/main.py"]' },
      { type: "info", msg: "Saving image as runtime.tar.gz …" },
      { type: "ok", msg: "Build complete — runtime.tar.gz produced (1.2 GB)" },
    ],
  },
  {
    key: "test_activation",
    label: "Test Activation",
    icon: Ic.shield,
    color: "#16a34a",
    desc: "Load the rebuilt runtime and run the activation script to verify the environment starts cleanly.",
    logLines: (ree) => [
      { type: "info", msg: `Running: bash ${ree.activation_script}` },
      { type: "info", msg: "docker load < runtime.tar.gz" },
      { type: "info", msg: "Loaded image: ree:latest" },
      { type: "info", msg: `docker run --rm --entrypoint="" ree:latest echo ok` },
      { type: "ok", msg: "ok" },
      { type: "ok", msg: "Activation test passed — container starts cleanly ✓" },
    ],
  },
];

export type { ReactivationStep };
