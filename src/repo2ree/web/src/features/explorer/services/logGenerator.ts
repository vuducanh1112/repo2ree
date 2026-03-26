import { LEVELS } from "../../../constants/levels";
import type { LogLine, Ree } from "../../../types";

type LogLineType = LogLine["type"];

/**
 * Generate mock service log output by key and REE state.
 * Used for UI demo/preview of service execution flows.
 */
export function makeLogs(
  key: string,
  ree: Ree,
  params: Record<string, unknown>,
  newLevel: number,
): LogLine[] {
  const makeLogLine = (type: LogLineType, msg: string): LogLine => ({ type, msg });
  const maps: Record<string, LogLine[]> = {
    create: [
      makeLogLine("info", "Validating REE fields..."),
      makeLogLine("info", `  name:              ${ree.name || "(empty)"}`),
      makeLogLine("info", `  origin_url:        ${ree.origin_url || "(empty)"}`),
      makeLogLine("info", `  build_script:      ${ree.build_runtime_script || "(empty)"}`),
      makeLogLine("info", `  sbom:              ${ree.sbom || "(empty)"}`),
      makeLogLine("info", `  activation:        ${ree.activation_script || "(empty)"}`),
      makeLogLine("info", "Registering REE object..."),
      makeLogLine("ok", `REE id: ree-${Math.random().toString(16).slice(2, 10)}`),
      makeLogLine("ok", "Manifest ready for download."),
    ],
    evaluate: [
      makeLogLine("info", `Strict mode:      ${params.strict ? "yes" : "no"}`),
      makeLogLine("info", `SWHID check:      ${params.swhid_check !== false ? "yes" : "no"}`),
      makeLogLine("info", "Scanning repository structure..."),
      makeLogLine("info", `  runtime:         ${ree.runtime || "not set"}`),
      makeLogLine("info", `  sbom:            ${ree.sbom || "not set"}`),
      makeLogLine("info", `  build_script:    ${ree.build_runtime_script || "not set"}`),
      makeLogLine("info", `  activation:      ${ree.activation_script || "not set"}`),
      ree.swhid
        ? makeLogLine("ok", `SWHID resolves: ${ree.swhid}`)
        : makeLogLine("warn", "No SWHID — not yet archived"),
      makeLogLine("info", "Computing score..."),
      makeLogLine("ok", `Reproducibility level: L${newLevel} (${LEVELS[newLevel].label})`),
    ],
    build: [
      makeLogLine("info", `Platform:  ${params.platform || "linux/amd64"}`),
      makeLogLine("info", `No-cache:  ${params.no_cache !== false ? "yes" : "no"}`),
      makeLogLine("info", `Reading ${ree.build_runtime_script || "build_runtime.sh"}...`),
      makeLogLine("info", "Pulling base image: python:3.11.7-slim-bookworm"),
      makeLogLine(
        "info",
        "$ DOCKER_BUILDKIT=1 docker build --no-cache --platform=" +
          (params.platform || "linux/amd64") +
          " -t ree:latest .",
      ),
      makeLogLine("out", "Step 1/5 : FROM python:3.11.7-slim-bookworm"),
      makeLogLine("out", "Step 2/5 : WORKDIR /app"),
      makeLogLine("out", "Step 3/5 : COPY requirements.txt ."),
      makeLogLine("out", "Step 4/5 : RUN pip install --no-cache-dir -r requirements.txt"),
      makeLogLine("out", "Step 5/5 : COPY src/ ./src/"),
      makeLogLine("info", "$ docker save ree:latest | gzip > runtime.tar.gz"),
      makeLogLine(
        "ok",
        "Build complete. Output: " +
          (ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "runtime.tar.gz"),
      ),
      makeLogLine("ok", "runtime.tar.gz written. Build successful."),
    ],
    sbom: [
      makeLogLine("info", `Format:    ${params.format || "spdx-json"}`),
      makeLogLine("info", `Target:    ${ree.runtime || "(not set)"}`),
      makeLogLine(
        "info",
        "$ syft " +
          (ree.runtime || "runtime.tar.gz") +
          " -o " +
          (params.format || "spdx-json") +
          "=sbom.spdx.json",
      ),
      makeLogLine("out", " ✔ Loaded image layers"),
      makeLogLine("out", " ✔ Parsed image configuration"),
      makeLogLine("out", " ✔ Catalogued contents"),
      makeLogLine("out", "   ├── numpy 1.26.4"),
      makeLogLine("out", "   ├── pandas 2.2.1"),
      makeLogLine("out", "   ├── scipy 1.12.0"),
      makeLogLine("out", "   ├── biopython 1.83"),
      makeLogLine("out", "   └── ... 42 packages total"),
      makeLogLine("info", "Writing sbom.spdx.json..."),
      makeLogLine("ok", "SBOM generated: sbom.spdx.json"),
    ],
    activation: [
      makeLogLine("info", `Timeout: ${params.timeout || "60"}s`),
      makeLogLine("info", `Reading ${ree.activation_script || "activation_test.sh"}...`),
      makeLogLine("info", `$ docker load < ${ree.runtime || "runtime.tar.gz"}`),
      makeLogLine("out", "Loaded image: ree:latest"),
      makeLogLine("info", '$ docker run --rm --entrypoint="" ree:latest echo ok'),
      makeLogLine("out", "ok"),
      makeLogLine("ok", "Container started and exited cleanly. Activation test passed."),
    ],
    swh: [
      makeLogLine("info", `Visit type:     ${params.visit_type || "git"}`),
      makeLogLine("info", `Metadata only:  ${params.metadata_only ? "yes" : "no"}`),
      makeLogLine("info", "Preparing immutable source snapshot archive..."),
      makeLogLine("info", `Snapshot: ${ree._sourceSnapshotArchive || "source-original.tar.gz"}`),
      makeLogLine("info", "Connecting to Software Heritage API..."),
      makeLogLine("info", `Depositing: ${ree.origin_url || ree.name}`),
      makeLogLine("info", "Waiting for ingestion confirmation..."),
      makeLogLine("info", "Computing SWHID from tree hash..."),
      makeLogLine("ok", "Deposit accepted."),
      makeLogLine("ok", `SWHID: swh:1:dir:${Math.random().toString(16).slice(2, 14)}`),
    ],
    zenodo: [
      makeLogLine("info", `Access level:   ${params.access || "open"}`),
      makeLogLine("info", `Community:      ${params.community || "(none)"}`),
      makeLogLine("info", "Creating deposition on Zenodo..."),
      makeLogLine("info", `Uploading SBOM: ${ree.sbom || "sbom.spdx.json"}`),
      makeLogLine("info", `Uploading manifest: ${ree.name || "ree"}.manifest.json`),
      makeLogLine("info", "Setting metadata (title, creators, description)..."),
      makeLogLine("info", "Publishing deposition..."),
      makeLogLine("ok", "Deposition published."),
      makeLogLine("ok", `DOI: 10.5281/zenodo.${Math.floor(Math.random() * 9000000 + 1000000)}`),
    ],
    dataverse: [
      makeLogLine("info", `Server:     ${params.server || "https://dataverse.harvard.edu"}`),
      makeLogLine("info", `Dataverse:  ${params.dataverse || "root"}`),
      makeLogLine("info", "Creating dataset..."),
      makeLogLine("info", "Uploading files..."),
      makeLogLine("info", "Setting metadata fields..."),
      makeLogLine("info", "Publishing dataset..."),
      makeLogLine("ok", "Dataset published."),
      makeLogLine("ok", `Handle: hdl:1902.1/${Math.floor(Math.random() * 90000 + 10000)}`),
    ],
  };
  return maps[key] || [makeLogLine("ok", "Done.")];
}
