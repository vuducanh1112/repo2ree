"""Filesystem persistence for the REE aggregate.

One package owns everything that reads or writes an REE directory. Submodules
are imported directly (``from repo2ree_core.persistence.layout import ReeLayout``); this
package re-exports nothing, so the import graph inside it stays readable:

    layout, files           leaves — paths and file operations
    sidecar                  the persisted REE control-record schema
    source_snapshot          immutable source snapshot naming
    directory               REE directory and sidecar persistence
    repository              hydration into the domain aggregate
    receipts                durable receipt history and selection
"""
