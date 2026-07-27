"""How the API reaches a workbench: command dispatch and the upload handoff.

No routes live here. ``commands`` is what every synchronous route composes
(resolve a handle, span the work, translate a failure); ``uploads`` /
``upload_runs`` / ``archives`` are the byte paths in and out of a workbench.
"""
