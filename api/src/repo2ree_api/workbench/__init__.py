"""How the API reaches a workbench: command dispatch and the upload handoff.

No routes live here, and nothing here starts a run. ``commands`` is what every
synchronous route composes (resolve a handle, span the work, translate a
failure); ``uploads`` and ``archives`` are the byte paths in and out of a
workbench. Handing staged bytes to an REE *does* start a run, so that half lives
a layer up in :mod:`repo2ree_api.authoring.upload_runs`.
"""
