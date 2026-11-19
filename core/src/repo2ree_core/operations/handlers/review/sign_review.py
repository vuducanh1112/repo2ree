"""Sign a review: a Sigstore bundle, signed elsewhere, whose statement names the reviewed seal and carries the
review's record as its predicate.

The bundle is made where the reviewer's identity is, never here: core sees no credential, only the bundle. It is
kept for a review of a sealed REE that is not running, when its statement names the seal the review names, under
the review predicate type, with the record exactly as the review holds it as its predicate. A review is signed once,
and changes no more after: its steps refuse it (``refuse_signed_review``).
"""

from __future__ import annotations

import json

from repo2ree_core.evidence.review.store import read_review_record
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import SignReviewArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import SignReviewOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.signature import (
    REVIEW_PREDICATE_TYPE,
    UnreadableSignatureError,
    review_signature_path,
    signed_statement,
)


def handle_sign_review(args: SignReviewArgs, *, layout: ReeLayout, log: LogSink) -> ActionResult:
    review = layout.review(args.review_id)
    record = read_review_record(review)
    if record is None:
        return ActionResult.failed("precondition", f"no review {args.review_id}")
    staged = layout.upload_staging_file(args.upload_token)
    if not staged.is_file():
        return ActionResult.failed("precondition", f"no staged bundle {args.archive_name}")
    if record.status == "running":
        return ActionResult.failed("precondition", f"review {args.review_id} is running: sign it once it settles")
    seal = record.subject.ree_digest
    if seal is None:
        return ActionResult.failed(
            "precondition", f"review {args.review_id} is of a draft: only a review of a sealed REE is signed"
        )
    path = review_signature_path()
    target = review.root / path
    if target.exists():
        return ActionResult.failed("precondition", f"review {args.review_id} is signed already, at {path}")
    content = staged.read_bytes()
    try:
        statement = signed_statement(content)
    except UnreadableSignatureError as exc:
        return ActionResult.failed("validation", f"{args.archive_name}: {exc}")
    if str(seal) not in statement.digests:
        named = ", ".join(sorted(statement.digests))
        return ActionResult.failed("validation", f"{args.archive_name} signs {named}, not the reviewed seal {seal}")
    if statement.predicate_type != REVIEW_PREDICATE_TYPE:
        return ActionResult.failed(
            "validation",
            f"{args.archive_name} claims {statement.predicate_type}, not a review ({REVIEW_PREDICATE_TYPE})",
        )
    if statement.predicate != json.loads(review.metadata.read_bytes()):
        return ActionResult.failed(
            "validation", f"{args.archive_name} signs another record than review {args.review_id} holds"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, content)
    staged.unlink(missing_ok=True)
    log("system", "info", f"review {args.review_id} signed: {path}")
    outputs = SignReviewOutputs(review_id=args.review_id, path=path, ree_digest=seal)
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))
