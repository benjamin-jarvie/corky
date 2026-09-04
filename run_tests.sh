#!/bin/bash
# The one true way to run Corky's tests. Enforces the two lessons paid for
# in this repo's history: stale bytecode falsifies results (twice), and
# x86/arm64 wheel mismatches break imports.
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
find . -name __pycache__ -not -path "./hw/vendor/*" -exec rm -rf {} + 2>/dev/null || true
PY="arch -arm64 python3"
SUITES_FAST="tests/test_integrity.py tests/test_readme_claims.py tests/test_qrchannel.py tests/test_filechannel.py tests/test_property.py tests/test_screen_fit.py tests/test_ui_cost.py tests/test_qr_out.py tests/test_poweroff.py tests/test_display_driver.py"
SUITES_NODE="tests/test_addresses.py tests/e2e_regtest.py tests/e2e_filechannel.py tests/e2e_session.py tests/test_generate.py tests/test_matrix.py tests/test_adversarial.py"
FAILED=0
for t in $SUITES_FAST ${RUN_NODE:+$SUITES_NODE}; do
  if $PY "$t" >/dev/null 2>&1; then echo "PASS $t"; else echo "FAIL $t"; FAILED=1; fi
done
[ -z "$RUN_NODE" ] && echo "(fast suites only; RUN_NODE=1 ./run_tests.sh adds the bitcoind suites)"
# The interop suites are not run here: they need a one-time setup.sh that
# downloads Sparrow and a JDK, and tests/m1 needs Rosetta on Apple Silicon.
# Say so, because silence reads as "this is all the coverage there is".
echo "(not run here: tests/sparrow  38+20 checks vs Sparrow's own library"
echo "               tests/m1       28 checks + the two legibility rigs"
echo "               both need their setup.sh first; see TESTING.md rule 8)"
# The on-device rigs need the board, the hat and the camera, and a human to
# press buttons and aim a lens. Nothing here can stand in for them.
echo "(on the board: tests/hw_buttons.py  8 controls, prompts on the LCD"
echo "               tests/hw_camera.py   viewfinder + decode vs Sparrow"
echo "               m0/m0_gate.py        the memory gate; see m0/FLASH.md)"
exit $FAILED
