from enum import Enum


class DependencyMaturity(Enum):
    NONE = 1  # No manifest found
    DECLARED = 2  # Manifest found, no versions (Volatile)
    COMPATIBLE = 3  # Soft pinning/Ranges (Drifting)
    STRICT = 4  # Exact pinning (Locked Surface)
    DETERMINISTIC = 5  # Lockfile with hashes (Locked Graph)

    @property
    def label(self):
        labels = {
            1: "Missing",
            2: "Declared",
            3: "Compatible Range",
            4: "Strictly Pinned",
            5: "Deterministic (Locked)",
        }
        return labels[self.value]

    @property
    def description(self):
        descriptions = {
            1: "No dependency manifest (requirements.txt, etc.) detected.",
            2: "Manifest exists, but versions are unmanaged.",
            3: "Dependencies use ranges (e.g., ~= or ^). Minor drift possible.",
            4: "All top-level dependencies are exactly pinned (==).",
            5: "Full dependency graph is locked with content hashes.",
        }
        return descriptions[self.value]
