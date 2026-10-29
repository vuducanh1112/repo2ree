from __future__ import annotations

from pydantic import BaseModel

from repo2ree_protocol.document import WorkbenchReeDocument
from repo2ree_protocol.history import OperationHistory
from repo2ree_ree.model import Ree
from repo2ree_ree.review import ReviewSet

GET_REE_MANIFEST = "get-ree-manifest"
GET_REE_DOCUMENT = "get-ree-document"
GET_REE_DOCUMENT_SUMMARY = "--summary"
GET_REVIEWS = "get-reviews"
GET_HISTORY = "get-history"
READ_REE_FILE = "read-ree-file"
READ_REE_FILE_PATH = "--path"
BUILD_ARCHIVE = "build-archive"

QUERIES: dict[str, tuple[type[BaseModel] | None, tuple[str, ...]]] = {
    GET_REE_MANIFEST: (Ree, ()),
    GET_REE_DOCUMENT: (WorkbenchReeDocument, (GET_REE_DOCUMENT_SUMMARY,)),
    GET_REVIEWS: (ReviewSet, ()),
    GET_HISTORY: (OperationHistory, ()),
    READ_REE_FILE: (None, (READ_REE_FILE_PATH,)),
    BUILD_ARCHIVE: (None, ()),
}
