import type { Ree } from "../types";

export const DEMO_REE: Ree = {
  name: "genomics-pipeline-v2",
  swhid: "",
  origin_url: "https://github.com/lab/genomics-pipeline",
  source_type: "git",
  detected_dependencies: "",
  repro_level: "",
  runtime: "",
  build_runtime_script: "build_runtime.sh",
  sbom: "",
  activation_script: "activation_test.sh",
  hardware_description: {
    arch: "x86_64",
    memory: "16 GB",
    os: "Debian Bookworm",
    cpu: "Intel Xeon E5-2680",
  },
  _sourceAvailable: false,
  _sourceIncluded: true,
};

export const SEALED_DEMO_REE: Ree = {
  ...DEMO_REE,
  swhid: "swh:1:dir:4b825dc642cb6eb9a060e54bf8d69288fbee4904",
  runtime: "runtime.tar.gz",
  sbom: "sbom.spdx.json",
  zenodo_doi: "10.5281/zenodo.1234567",
  _evalLevel: 7,
  _sealedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
  _sealHash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  _sourceIncluded: true,
  _runtimeIncluded: true,
};
