#!/usr/bin/env bash
# Certificate that `just commit-gate` ran against exactly the content being
# committed.
#
# Running the gate itself from the hook was the obvious design and the wrong
# one: it takes ~50s, and pre-commit captures hook output instead of streaming
# it, so `git commit` sits on an unfinished line with no sign of progress. This
# splits the two halves — the gate runs in your terminal where you can watch it,
# and the hook does a hash comparison to confirm it ran on this content.
#
# Certificates live in .validation-certificates/, whose own .gitignore keeps
# everything but that .gitignore out of the repository. The directory is tracked
# so a fresh clone has one, and so the ignore rule is in force from the first
# commit; the certificates themselves never are, because they describe one
# clone's state.
#
# That ignore rule is the only thing making this safe. The certificate is a hash
# of the working tree, and it sits *in* that tree — an ignored file is invisible
# to the `git add -A` below, so the hash stays stable, but a tracked one would
# change the very thing it measures and could never match twice. `assert_ignored`
# below turns that from a silent trap into a refusal.
#
# --show-toplevel anchors this to the repository root whatever the caller's cwd.
# In a linked `git worktree` it is that worktree's own root, so each worktree
# carries its own certificate — which is what you want, since each has its own
# content.
set -euo pipefail

state_dir="$(git rev-parse --show-toplevel)/.validation-certificates"
stamp="$state_dir/commit-gate-ok"

# Refuse to write a certificate git would track. Cheap insurance against an
# edit to .validation-certificates/.gitignore quietly making every future
# verify fail, with nothing to point at as the cause.
assert_ignored() {
	if ! git check-ignore -q "$stamp"; then
		echo "$stamp is not ignored by git — a tracked certificate changes the tree it" >&2
		echo "measures and can never match. Restore .validation-certificates/.gitignore." >&2
		exit 1
	fi
}

# Content hash of the working tree — what a gate run actually inspected.
# Computed in a throwaway index, because `git add` honours GIT_INDEX_FILE and
# stages into that file alone; the real index is never touched. `git write-tree`
# writes tree objects but changes no ref, so this is inert either way.
worktree_tree() {
	local idx
	idx=$(mktemp)
	GIT_INDEX_FILE="$idx" git read-tree HEAD 2>/dev/null || true
	GIT_INDEX_FILE="$idx" git add -A
	GIT_INDEX_FILE="$idx" git write-tree
	rm -f "$idx"
}

case "${1:-}" in
write)
	mkdir -p "$state_dir"
	assert_ignored
	worktree_tree >"$stamp"
	;;
verify)
	# The staged tree is what the commit will contain. pre-commit has already
	# stashed everything unstaged by the time a hook runs, but this reads the
	# index rather than the working tree, so it does not depend on that.
	staged=$(git write-tree)
	if [ ! -f "$stamp" ]; then
		echo "no commit-gate certificate for this clone — run: just commit-gate" >&2
		exit 1
	fi
	if [ "$(cat "$stamp")" != "$staged" ]; then
		echo "the commit-gate certificate covers different content than you are committing." >&2
		echo "stage everything you mean to commit, then re-run: just commit-gate" >&2
		exit 1
	fi
	;;
*)
	echo "usage: ${0##*/} {write|verify}" >&2
	exit 2
	;;
esac
