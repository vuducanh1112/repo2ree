"""The product's side of the behaviour contract in ``contracts/behaviour``.

Owners record every state change through the typed records in ``events``; the writer
keeps the journal rules (one file per epoch, contiguous sequence numbers, durable
lines). ``repo2ree_conformance`` judges what they wrote. Nothing here is generated from
the specification, and the specification's rules never run in the product.
"""

from repo2ree_protocol.behaviour import events
from repo2ree_protocol.behaviour.reader import JournalFile, journal_file, journal_files, positions, records_after
from repo2ree_protocol.behaviour.writer import VOCABULARY, Journal, close_journal, journal, open_journal

__all__ = [
    "VOCABULARY",
    "Journal",
    "JournalFile",
    "close_journal",
    "events",
    "journal",
    "journal_file",
    "journal_files",
    "open_journal",
    "positions",
    "records_after",
]
