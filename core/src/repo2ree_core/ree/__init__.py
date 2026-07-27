"""The persisted REE aggregate: its on-disk layout, its state, and its bundle.

One package owns everything that reads or writes an REE directory. Submodules
are imported directly (``from repo2ree_core.ree.layout import ReeLayout``); this
package re-exports nothing, so the import graph inside it stays readable:

    layout, files           leaves — paths and file operations
    workspace/{model,inventory}
    bundle/{plan,manifest}  pure planning and payload construction
    store                   REE state persistence
    workspace/views         read views over a stored REE
    bundle/{seal,restore}   bundle assembly and its inverse
"""
