"""Filesystem persistence for the REE aggregate.

One package owns everything that reads or writes an REE directory. Submodules
are imported directly (``from repo2ree_core.persistence.layout import ReeLayout``); this
package re-exports nothing, so the import graph inside it stays readable:

    layout, files           leaves — paths and file operations
    ree_manifest            the one encoding of the REE manifest
    directory               REE directory and manifest persistence
    repository              hydration into the domain aggregate
"""
