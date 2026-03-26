import type { IWorkspaceService, LogEntry, ReeProject } from "./workspaceService";

export interface DummyWorkspaceFileNode {
  id: string;
  name: string;
  type: "file" | "folder";
  content?: string;
  tag?: string;
  children?: DummyWorkspaceFileNode[];
}

type ResetMode = "download" | "upload" | "clear";

interface WorkspaceResetPayload<TSourceType = string> {
  mode?: ResetMode;
  source?: string;
  sourceType?: TSourceType;
  archiveName?: string;
}

interface CreateInMemoryDummyWorkspaceServiceOptions<TFile, TSourceType = string> {
  getWorkspaceFiles: () => TFile[];
  updateWorkspaceFiles: (updater: (previous: TFile[]) => TFile[]) => void;
  upsertFile: (previous: TFile[], path: string, content: string) => TFile[];
  runScript: (scriptKey: string) => Promise<LogEntry>;
  clearWorkspace: () => void;
  loadWorkspaceFromUpload: (archiveName: string) => void;
  loadWorkspaceFromDownload: (source: string, sourceType: TSourceType) => void;
  getDefaultSource: () => string;
  getDefaultSourceType: () => TSourceType;
}

export function cloneDummyWorkspaceTree(nodes: DummyWorkspaceFileNode[]): DummyWorkspaceFileNode[] {
  return (nodes || []).map((node) => ({
    ...node,
    children: node.children ? cloneDummyWorkspaceTree(node.children) : undefined,
  }));
}

export function makeDummyWorkspaceFromOrigin(
  seedFiles: DummyWorkspaceFileNode[],
  originUrl: string,
  sourceType: string,
  sourceTag: string,
): DummyWorkspaceFileNode[] {
  const seed = cloneDummyWorkspaceTree(seedFiles);
  const repoName = (originUrl.split("/").filter(Boolean).pop() || "repo").replace(
    /\.(git|tar\.gz|tgz|zip)$/i,
    "",
  );

  if (sourceType === "tarball") {
    return [
      {
        id: `src-${Date.now()}`,
        name: repoName || "repo",
        type: "folder",
        tag: sourceTag,
        children: [
          ...seed,
          {
            id: `src-meta-${Date.now()}`,
            name: "EXTRACTION_NOTE.txt",
            type: "file",
            tag: sourceTag,
            content: `Extracted from tarball source: ${originUrl}`,
          },
        ],
      },
    ];
  }

  return [
    {
      id: `src-${Date.now()}`,
      name: repoName || "repo",
      type: "folder",
      tag: sourceTag,
      children: seed,
    },
  ];
}

export function makeDummyWorkspaceFromArchiveUpload(
  seedFiles: DummyWorkspaceFileNode[],
  archiveName: string,
  sourceTag: string,
): DummyWorkspaceFileNode[] {
  const root = archiveName.replace(/\.(tar\.gz|tgz|tar|zip)$/i, "") || "repo";
  return [
    {
      id: `up-${Date.now()}`,
      name: root,
      type: "folder",
      tag: sourceTag,
      children: [
        ...cloneDummyWorkspaceTree(seedFiles),
        {
          id: `up-note-${Date.now()}`,
          name: "EXTRACTION_NOTE.txt",
          type: "file",
          tag: sourceTag,
          content: `Extracted from uploaded archive: ${archiveName}`,
        },
      ],
    },
  ];
}

export const MOCK_FILES: DummyWorkspaceFileNode[] = [
  {
    id: "1",
    name: "src",
    type: "folder",
    children: [
      {
        id: "11",
        name: "main.py",
        type: "file",
        content: `#!/usr/bin/env python3\n\ndef main():\n    print("REE v1.0")\n\nif __name__ == "__main__":\n    main()`,
      },
      {
        id: "12",
        name: "pipeline.py",
        type: "file",
        content: `class Pipeline:\n    def __init__(self, config):\n        self.config = config\n        self.steps = []\n\n    def run(self):\n        for step in self.steps:\n            step.execute()`,
      },
      {
        id: "13",
        name: "utils",
        type: "folder",
        children: [
          {
            id: "131",
            name: "hash.py",
            type: "file",
            content: `import hashlib\n\ndef sha256_file(path):\n    h = hashlib.sha256()\n    with open(path, "rb") as f:\n        for chunk in iter(lambda: f.read(8192), b""):\n            h.update(chunk)\n    return h.hexdigest()`,
          },
        ],
      },
    ],
  },
  {
    id: "2",
    name: "build_runtime.sh",
    type: "file",
    content: `#!/bin/bash\nset -euo pipefail\nDOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest .\ndocker save ree:latest | gzip > runtime.tar.gz\necho "Build complete."`,
  },
  {
    id: "3",
    name: "activation_test.sh",
    type: "file",
    content: `#!/bin/bash\nset -euo pipefail\n# Load the runtime tarball and verify the environment activates\ndocker load < runtime.tar.gz\ndocker run --rm --entrypoint="" ree:latest echo "ok"\necho "Activation test passed."`,
  },
  {
    id: "4",
    name: "sbom.spdx.json",
    type: "file",
    content: `{\n  "spdxVersion": "SPDX-2.3",\n  "dataLicense": "CC0-1.0",\n  "name": "ree-sbom"\n}`,
  },
  {
    id: "5",
    name: "Dockerfile",
    type: "file",
    content: `FROM python:3.11.7-slim-bookworm\nWORKDIR /app\nCOPY . .\nRUN pip install --no-cache-dir -r requirements.txt\nCMD ["python", "src/main.py"]`,
  },
  {
    id: "6",
    name: "README.md",
    type: "file",
    content: `# genomics-pipeline-v2\n\nA fully reproducible genomics pipeline environment.`,
  },
  {
    id: "7",
    name: "requirements.txt",
    type: "file",
    content: `numpy==1.26.4\npandas==2.2.1\nscipy==1.12.0\nbiopython==1.83\npysam==0.22.0\nclick>=8.0\ntqdm\nloguru==0.7.2\npytest==8.1.1\ncoverage`,
  },
  {
    id: "8",
    name: "pyproject.toml",
    type: "file",
    content: `[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n\n[project]\nname = "genomics-pipeline"\nversion = "2.0.0"\nrequires-python = ">=3.11"\ndependencies = [\n  "numpy>=1.26",\n  "pandas>=2.0",\n  "snakemake==8.4.6",\n  "pulp==2.8.0",\n]\n\n[project.optional-dependencies]\ndev = [\n  "pytest>=8.0",\n  "mypy",\n  "ruff",\n]`,
  },
  {
    id: "9",
    name: "environment.yml",
    type: "file",
    content: `name: genomics-pipeline\nchannels:\n  - conda-forge\n  - bioconda\n  - defaults\ndependencies:\n  - python=3.11.7\n  - samtools=1.19.2\n  - bwa=0.7.17\n  - gatk4=4.5.0.0\n  - bcftools=1.19\n  - htslib\n  - pip:\n    - pysam==0.22.0\n    - biopython==1.83`,
  },
  { id: "10", name: "runtime.tar.gz", type: "file", content: "(binary content)" },
];

function parseWorkspaceResetPayload<TSourceType = string>(
  newSource: string,
  fallbackSourceType: TSourceType,
): WorkspaceResetPayload<TSourceType> {
  try {
    return newSource ? JSON.parse(newSource) : {};
  } catch {
    return { mode: "download", source: newSource, sourceType: fallbackSourceType };
  }
}

export function createInMemoryDummyWorkspaceService<TFile, TSourceType = string>(
  options: CreateInMemoryDummyWorkspaceServiceOptions<TFile, TSourceType>,
): IWorkspaceService<TFile> {
  return {
    getWorkspace: async (id: string): Promise<ReeProject<TFile>> => ({
      id,
      files: options.getWorkspaceFiles(),
    }),
    updateFile: async (_id: string, path: string, content: string): Promise<void> => {
      options.updateWorkspaceFiles((previous) => options.upsertFile(previous, path, content));
    },
    runScript: async (_id: string, scriptKey: string): Promise<LogEntry> => {
      return options.runScript(scriptKey);
    },
    resetWorkspace: async (_id: string, newSource: string): Promise<void> => {
      const parsedSource = parseWorkspaceResetPayload(newSource, options.getDefaultSourceType());
      const mode = parsedSource.mode || "clear";

      if (mode === "clear") {
        options.clearWorkspace();
        return;
      }

      if (mode === "upload") {
        options.loadWorkspaceFromUpload(parsedSource.archiveName || "source.tar.gz");
        return;
      }

      const source = parsedSource.source || options.getDefaultSource();
      const sourceType = parsedSource.sourceType || options.getDefaultSourceType();
      if (!source) return;
      options.loadWorkspaceFromDownload(source, sourceType);
    },
  };
}
