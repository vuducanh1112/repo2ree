export const BASE_HINTS: Record<string, string> = {
  "docker-export": "Build image, save as runtime.tar.gz",
  "docker-image-only": "Build image, reference by tag",
  "nix-docker": "Nix build → Docker load → export",
  "conda-pack": "Pack conda env to tar.gz",
  "venv-pip": "Pack Python venv to tar.gz",
};
