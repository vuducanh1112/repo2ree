"""The shared shape of a step, for the handlers that fill it in.

A handler is supposed to be about what makes its operation different. Almost
none of what a step *does* is that: opening the REE, digesting the input slice a
receipt binds, settling a step's status on disk before and after the work,
halting in a way that leaves the record agreeing with what happened. That
ceremony lives here, split the way the two lifecycles are — :mod:`.author` for
the REE an author is building, :mod:`.review` for the parallel tree a reviewer
reproduces it in.

This package sits *beside* ``handlers`` rather than inside it. Both handler
families import it and neither may import the other, so shared machinery cannot
live in either one without becoming the shortcut between them.
"""
