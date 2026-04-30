import { emptyHBOM } from "../../domain/hbom/HbomSummary";
import type { Ree } from "../../domain/ree/ReeSpec";

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
    ...emptyHBOM(),
    cpus: {
      "Intel Xeon E5-2680": {
        vendor: "Intel",
        quantity: 1,
        cores_per_cpu: 8,
        threads_per_core: 2,
        architecture: "x86_64",
        extra_info: {},
      },
    },
    memory: {
      "DDR4 ECC 16 GB": {
        vendor: "Samsung",
        quantity: 1,
        capacity_gb: 16,
        memory_type: "DDR4",
        speed_mt_s: 2666,
        extra_info: {},
      },
    },
    extra_info: {
      os: "Debian Bookworm",
    },
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
