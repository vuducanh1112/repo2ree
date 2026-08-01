"""Compatibility imports for receipt persistence.

Receipt persistence belongs to the REE store and now lives in
``repo2ree_core.ree.receipts``. Evidence code remains responsible for
interpreting those durable facts.
"""

from repo2ree_core.ree.receipts import (
    author_receipt_path,
    load_author_receipts,
    load_receipts,
    persist_snapshot_digest,
    prune_author_experiment_receipts,
    published_receipts,
    record_receipt,
    stat_table,
    write_materialize_marker,
)

__all__ = [
    "author_receipt_path",
    "load_author_receipts",
    "load_receipts",
    "persist_snapshot_digest",
    "prune_author_experiment_receipts",
    "published_receipts",
    "record_receipt",
    "stat_table",
    "write_materialize_marker",
]
