"""The REE's portable form: what a bundle contains and how it is built back.

Sits above both ``ree`` (the persisted aggregate it packages) and ``evidence``
(the receipts it publishes into the archive), which is why it is a sibling of
those packages rather than living inside ``ree``: a bundle is an artifact
*derived from* an REE, not part of one.

    plan              pure — the ZIP writer and its layout decisions
    seal, restore     shell — assembling the archive and its inverse
"""
