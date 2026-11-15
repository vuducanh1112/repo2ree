from __future__ import annotations

from pydantic import BaseModel

from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.history import OperationHistory
from repo2ree_ree.model import Ree
from repo2ree_ree.review import ReviewSet

GET_REE_MANIFEST = "manifest"
GET_REE_DOCUMENT = "show"
GET_REE_DOCUMENT_SUMMARY = "--summary"
GET_REVIEWS = "reviews"
GET_HISTORY = "log"
# Takes the path, relative to the REE root, as its argument: ``cat -- <path>``.
READ_REE_FILE = "cat"
BUILD_ARCHIVE = "bundle"
# Not a query: creates the REE, ``init --name <name>``.
INIT_REE = "init"

QUERIES: dict[str, tuple[type[BaseModel] | None, tuple[str, ...]]] = {
    GET_REE_MANIFEST: (Ree, ()),
    GET_REE_DOCUMENT: (WorkbenchReeDocument, (GET_REE_DOCUMENT_SUMMARY,)),
    GET_REVIEWS: (ReviewSet, ()),
    GET_HISTORY: (OperationHistory, ()),
    READ_REE_FILE: (None, ()),
    BUILD_ARCHIVE: (None, ()),
}
