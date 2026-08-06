# Generated views of what a run actually did, from the spans the test tiers
# already capture. The suites report whether the flow passed; these show the
# shape it took — the runtime counterpart of the import diagrams in
# architecture.mk, and the same bargain: a gate answers "did the rule hold",
# a picture answers "is this the system we meant".
#
# Reads a capture, never produces one. The trace files come from the test tiers
# (api-integration writes per-test slices under test-artifacts/traces/), so a
# journal is only as current as the last run of the suite that made it.

.PHONY: journals

# Gitignored like dist/diagrams: local analysis artifacts, not files to review
# in a diff.
JOURNAL_DIR ?= dist/journals

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
journals:
	@test -f $(JOURNAL_TRACE) || { \
		echo "no capture at $(JOURNAL_TRACE)" >&2; \
		echo "run: make e2e-bundles && pytest api/tests/integration" >&2; \
		exit 1; \
	}
	@mkdir -p $(JOURNAL_DIR)
	@python scripts/trace_journal.py $(JOURNAL_TRACE) 2>/dev/null \
		| awk '$$4 ~ /^run\./ {print $$1, $$4}' \
		| while read -r trace root; do \
			python scripts/trace_journal.py $(JOURNAL_TRACE) -f graph --trace $$trace \
				--exclude "docker." --exclude "process.exec" $(JOURNAL_ZONES) \
				--title "$${root#run.} — across components" \
				-o $(JOURNAL_DIR)/$${root#run.}.html; \
		done
