"""Analysis capabilities over a repository and the artifacts built from it.

    repository  profiling a source tree and scoring its reproducibility
    sbom        generating, scanning, and cross-checking software inventories
    hbom        profiling the hardware a run actually had available

Each is a capability the operations layer calls into; none of them knows about
commands, handlers, or each other.
"""
