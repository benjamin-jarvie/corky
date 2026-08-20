#!/bin/bash
# The one true way to run Corky's tests. Enforces the two lessons paid for
# in this repo's history: stale bytecode falsifies results (twice), and
# x86/arm64 wheel mismatches break imports.
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
find . -name __pycache__ -not -path "./hw/vendor/*" -exec rm -rf {} + 2>/dev/null || true
PY="arch -arm64 python3"
SUITES_FAST="tests/test_integrity.py tests/test_readme_claims.py shim/test_shim.py tests/test_codex32.py tests/test_seedqr.py tests/test_qrchannel.py tests/test_filechannel.py tests/test_property.py"
SUITES_NODE="tests/test_addresses.py tests/e2e_regtest.py tests/e2e_filechannel.py tests/e2e_session.py tests/test_generate.py tests/test_matrix.py tests/test_adversarial.py"
FAILED=0
for t in $SUITES_FAST ${RUN_NODE:+$SUITES_NODE}; do
  if $PY "$t" >/dev/null 2>&1; then echo "PASS $t"; else echo "FAIL $t"; FAILED=1; fi
done
[ -z "$RUN_NODE" ] && echo "(fast suites only; RUN_NODE=1 ./run_tests.sh adds the bitcoind suites)"
exit $FAILED
