# Generated views of what a run actually did, from the spans the test tiers
# already capture. The suites report whether the flow passed; these show the
# shape it took — the runtime counterpart of the import diagrams in
# architecture.mk and the domain views in domain.mk, and the same bargain:
# a gate answers "did the rule hold", a picture answers "is this the system
# we meant".
#
# Reads a capture, never produces one. The trace files come from the test tiers
# (api-integration writes per-test slices under test-artifacts/traces/), so a
# journal is only as current as the last run of the suite that made it.

.PHONY: journals

# A third subdirectory of dist/diagrams, beside architecture/ and domain/: the
# three answer what the code imports, what an REE is, and what a run did, and
# they are one family of generated pictures rather than a family plus an
# outlier. Restated with ?= so this file stands on its own regardless of include
# order. Gitignored either way — local analysis artifacts, not files to review
# in a diff.
DIAGRAM_DIR ?= dist/diagrams
JOURNAL_DIR ?= $(DIAGRAM_DIR)/journals

# The capture every journal is drawn from. One test drives every authoring
# stage in a single run, so one file holds every workflow — which is what lets
# the recipe loop over traces rather than name them.
JOURNAL_TRACE ?= test-artifacts/traces/api-integration/by-test/api_tests_integration_test_api_full_pipeline.py_test_full_authoring_pipeline.ndjson

# Zones name the component that emitted a span. They are given here rather than
# derived because a span name is not authority for its package — the mapping is
# domain knowledge, and this is the one place that holds it.
JOURNAL_ZONES = \
	--zone "api=ree.,run.,POST ,GET ,PUT ,DELETE " \
	--zone "supervisor=workbench." \
	--zone "agent=agent." \
	--zone "executor cli=executor." \
	--zone "core=command.,script.,runnable."

# One page per workflow: the whole path for that operation, api to core.
# Script-level spans are dropped — at this altitude the question is which
# component hands what to which, and a build script's own subprocesses answer a
# different one. (``trace_journal.py --only`` draws that finer view when it is
# wanted; nothing here generates it yet.)
#
# A page is named for its operation, and an REE may run one twice — the pipeline
# test builds, edits the build script, and rebuilds to show a receipt going
# stale. Both runs used to land on `build.html`, so the first was rendered and
# then overwritten with no warning, and the surviving page was the rebuild while
# claiming to be the build. Repeats are numbered in the order they ran, so
# `build.html` is still the first one and nothing silently disappears.
#
# Numbered in the awk that already selects the roots rather than in the loop
# below: it is the one place that sees every name before any page is written.
journals:
	@test -f $(JOURNAL_TRACE) || { \
		echo "no capture at $(JOURNAL_TRACE)" >&2; \
		echo "run: make e2e-bundles && pytest api/tests/integration" >&2; \
		exit 1; \
	}
	@mkdir -p $(JOURNAL_DIR)
	@python scripts/trace_journal.py $(JOURNAL_TRACE) 2>/dev/null \
		| awk '$$4 ~ /^run\./ { name = substr($$4, 5); n = ++seen[name]; \
			print $$1, (n == 1 ? name : name "-" n) }' \
		| while read -r trace name; do \
			python scripts/trace_journal.py $(JOURNAL_TRACE) -f graph --trace $$trace \
				--exclude "docker." --exclude "process.exec" $(JOURNAL_ZONES) \
				--title "$$name — across components" \
				-o $(JOURNAL_DIR)/$$name.html; \
		done
