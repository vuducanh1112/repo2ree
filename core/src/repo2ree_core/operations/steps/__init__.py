"""The shared shape of a step, for the handlers that fill it in.

A handler is supposed to be about what makes its operation different. Almost
none of what a step *does* is that: opening the REE, digesting the input slice a
receipt binds, settling a step's status on disk before and after the work,
halting in a way that leaves the manifest agreeing with what happened. That
ceremony lives here, in :mod:`.review` — the reviewer's steps, which advance an
attempt's own lifecycle and have that bookkeeping to share. The author's steps
have no such counterpart: an authoring handler commits one receipt to the REE
manifest and is done, so what it would inherit is a precondition check it is
clearer writing out.

This package sits *beside* ``handlers`` rather than inside it. Both handler
families may import it and neither may import the other, so shared machinery
cannot live in either one without becoming the shortcut between them.
"""
