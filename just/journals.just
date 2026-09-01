JOURNAL_TRACE := env("JOURNAL_TRACE", "test-artifacts/traces/api-integration/by-test/api_tests_integration_test_api_full_pipeline.py_test_full_authoring_pipeline.ndjson")

# Journals derive one cross-component page per captured run trace. The trace is
# an integration-test artifact; absence is an error, never an empty success.

# Generate one cross-component journal page per captured workflow.
[group('Diagrams')]
journals:
    #!/usr/bin/env bash
    set -euo pipefail
    journal_trace={{ quote(JOURNAL_TRACE) }}
    test -f "$journal_trace" || {
      printf 'no capture at %s\n' "$journal_trace" >&2
      echo "run: just e2e-bundles && pytest api/tests/integration" >&2
      exit 1
    }
    mkdir -p {{ quote(JOURNAL_DIR) }}
    python scripts/diagrams/trace_journal.py "$journal_trace" 2>/dev/null \
      | awk '$4 ~ /^run\./ { name = substr($4, 5); n = ++seen[name]; print $1, (n == 1 ? name : name "-" n) }' \
      | while read -r trace name; do
          python scripts/diagrams/trace_journal.py "$journal_trace" -f graph --trace "$trace" \
            --exclude 'docker.' --exclude 'process.exec' \
            --zone 'api=ree.,run.,POST ,GET ,PUT ,DELETE ' \
            --zone 'supervisor=workbench.' \
            --zone 'agent=agent.' \
            --zone 'executor cli=executor.' \
            --zone 'core=command.,script.,runnable.' \
            --title "$name — across components" \
            -o {{ quote(JOURNAL_DIR) }}/"$name".html
        done
