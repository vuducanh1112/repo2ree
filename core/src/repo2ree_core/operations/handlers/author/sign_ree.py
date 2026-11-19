"""Add a signature to a sealed REE: a Sigstore bundle, signed elsewhere, over the seal's digest.

The bundle is made where the signer's identity is, never here: core sees no credential, only the bundle. It is
kept when its statement names the seal's digest under the claim's predicate type, beside what the seal covers,
and never written over: a claim is signed once.
"""

from __future__ import annotations

from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import SignReeArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import SignOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.signature import PREDICATE_TYPES, UnreadableSignatureError, signature_path, signed_statement


def handle_sign_ree(args: SignReeArgs, *, layout: ReeLayout, log: LogSink) -> ActionResult:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "no REE here: run `ree initialize-ree` first")
    staged = layout.upload_staging_file(args.upload_token)
    if not staged.is_file():
        return ActionResult.failed("precondition", f"no staged bundle {args.archive_name}")
    seal = store.read_ree().seal
    if seal is None:
        return ActionResult.failed("precondition", "only a sealed REE is signed: run `ree seal-ree` first")
    path = signature_path(args.claim)
    target = layout.root / path
    if target.exists():
        return ActionResult.failed("precondition", f"the REE is signed for {args.claim} already, at {path}")
    content = staged.read_bytes()
    try:
        statement = signed_statement(content)
    except UnreadableSignatureError as exc:
        return ActionResult.failed("validation", f"{args.archive_name}: {exc}")
    if str(seal.ree_digest) not in statement.digests:
        named = ", ".join(sorted(statement.digests))
        return ActionResult.failed("validation", f"{args.archive_name} signs {named}, not the seal {seal.ree_digest}")
    if statement.predicate_type != PREDICATE_TYPES[args.claim]:
        return ActionResult.failed(
            "validation",
            f"{args.archive_name} claims {statement.predicate_type}, not {args.claim} ({PREDICATE_TYPES[args.claim]})",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, content)
    staged.unlink(missing_ok=True)
    log("system", "info", f"REE signed for {args.claim}: {path}")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=SignOutputs(claim=args.claim, path=path, ree_digest=seal.ree_digest).model_dump(mode="json"),
    )
