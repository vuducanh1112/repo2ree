"""The application layer: typed protocol commands in, action results out.

``dispatch`` accepts one command from the wire vocabulary and routes it to the
handler that owns it, exhaustively — the union is closed, so a new command that
nobody handles is a type error rather than a runtime surprise. Handlers
coordinate the capabilities below them (``ree``, ``evidence``, ``bundle``,
``execution``, ``analysis``); nothing below imports back into here.

The *envelope* this once was named for belongs to ``repo2ree_protocol``: this
package is what happens after one is opened.
"""
