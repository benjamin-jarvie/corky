#!/bin/bash
# The one true way to run Corky's tests. Enforces the two lessons paid for
# in this repo's history: stale bytecode falsifies results (twice), and
# x86/arm64 wheel mismatches break imports.
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
find . -name __pycache__ -not -path "./hw/vendor/*" -exec rm -rf {} + 2>/dev/null || true
PY="arch -arm64 python3"
SUITES_FAST="tests/test_integrity.py tests/test_image_contents.py tests/test_readme_claims.py tests/test_qrchannel.py tests/test_filechannel.py tests/test_property.py tests/test_screen_fit.py tests/test_ui_cost.py tests/test_qr_out.py tests/test_poweroff.py tests/test_display_driver.py tests/test_buttons.py tests/test_keyscan.py"
SUITES_NODE="tests/test_addresses.py tests/e2e_regtest.py tests/e2e_filechannel.py tests/e2e_session.py tests/test_generate.py tests/test_matrix.py tests/test_adversarial.py tests/test_keys.py tests/e2e_keys.py tests/test_no_persistence.py tests/test_export.py tests/test_backup.py"
FAILED=0
# Static checks first, because they are seconds and the suites are minutes.
# They come from requirements-dev.txt, never from the signer's own package
# list; when they are not installed the run says so instead of pretending.
# Invoked through the same interpreter that runs the suites, so a tool
# venv first on PATH can never shadow python3 (it did, once, and 14 suites
# failed for want of Pillow).
if $PY -m ruff --version >/dev/null 2>&1; then
  if $PY -m ruff check corky tests tools m0 >/dev/null 2>&1; then echo "PASS ruff"; else echo "FAIL ruff"; FAILED=1; fi
  if $PY -m vulture corky --min-confidence 60 >/dev/null 2>&1; then echo "PASS vulture"; else echo "FAIL vulture"; FAILED=1; fi
  if $PY -m mypy corky/signer.py corky/qrchannel.py corky/filechannel.py --ignore-missing-imports --check-untyped-defs >/dev/null 2>&1; then echo "PASS mypy (the seam)"; else echo "FAIL mypy (the seam)"; FAILED=1; fi
else
  echo "(not run: ruff, vulture, mypy. python3 -m pip install --user -r requirements-dev.txt, on the DEV machine only.)"
fi
# A failing suite used to print its name and nothing else, so the first
# thing anyone did was run it again by hand. Keep the output and show the
# tail, because TESTING.md says find out why before making it pass.
LOGDIR=$(mktemp -d)
for t in $SUITES_FAST ${RUN_NODE:+$SUITES_NODE}; do
  LOG="$LOGDIR/$(basename "$t").log"
  if $PY "$t" >"$LOG" 2>&1; then
    echo "PASS $t"
  else
    echo "FAIL $t"
    sed 's/^/      | /' "$LOG" | tail -12
    echo "      | full output: $LOG"
    FAILED=1
  fi
done
[ -z "$RUN_NODE" ] && echo "(fast suites only; RUN_NODE=1 ./run_tests.sh adds the bitcoind suites)"
# The Sparrow suites hold the only real-data coverage of the QR surfaces:
# Corky's own decoder reading Corky's own codes proves nothing (TESTING.md
# rule 8). They need a one-time setup.sh that downloads Sparrow and a JDK,
# so they run here when that build exists, and say so when it does not.
if [ -x "tests/sparrow/.build/jdk-25.0.4.1+1/Contents/Home/bin/java" ]; then
  for t in tests/sparrow/test_sparrow_interop.py tests/sparrow/test_qr_airgap.py \
           tests/sparrow/test_export_interop.py; do
    if (cd tests/sparrow && $PY "$(basename "$t")" >/dev/null 2>&1); then
      echo "PASS $t"
    else
      echo "FAIL $t"; FAILED=1
    fi
  done
else
  echo "(not run: tests/sparrow, 81 checks against Sparrow's own library."
  echo "          Run tests/sparrow/setup.sh once to build it. Without it"
  echo "          nothing here reads a QR with anything but our own decoder.)"
fi
echo "(not run here: tests/m1  28 checks + the two legibility rigs;"
echo "               needs its setup.sh and Rosetta on Apple Silicon)"
# The on-device rigs need the board, the hat and the camera, and a human to
# press buttons and aim a lens. Nothing here can stand in for them.
echo "(on the board: tests/hw_buttons.py  8 controls, prompts on the LCD"
echo "               tests/hw_camera.py   viewfinder + decode vs Sparrow"
echo "               m0/m0_gate.py        the memory gate; see m0/FLASH.md)"
exit $FAILED
