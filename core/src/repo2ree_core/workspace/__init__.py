"""The mutable execution tree under an REE's ``workspace/`` directory.

A workspace is derived by copying ``upstream/`` and applying ``overlay/``. It
is safe to discard and recreate; durable authored inputs and promoted outputs
live elsewhere in the REE directory.
"""
