#!/bin/bash
# The one true way to run Corky's tests. Enforces the two lessons paid for
# in this repo's history: stale bytecode falsifies results (twice), and
# x86/arm64 wheel mismatches break imports.
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
find . -name __pycache__ -not -path "./hw/vendor/*" -exec rm -rf {} + 2>/dev/null || true
PY="arch -arm64 python3"
SUITES_FAST="tests/test_integrity.py tests/test_image_contents.py tests/test_readme_claims.py tests/test_qrchannel.py tests/test_filechannel.py tests/test_property.py tests/test_screen_fit.py tests/test_ui_cost.py tests/test_qr_out.py tests/test_poweroff.py tests/test_display_driver.py tests/test_buttons.py tests/test_keyscan.py tests/test_menu_wiring.py tests/test_scroll.py tests/test_splash.py tests/test_backup_check.py tests/test_channels.py tests/test_key_persistence.py tests/test_harden_reversible.py"
SUITES_NODE="tests/test_addresses.py tests/e2e_regtest.py tests/e2e_filechannel.py tests/e2e_session.py tests/test_generate.py tests/test_matrix.py tests/test_adversarial.py tests/test_keys.py tests/e2e_keys.py tests/test_no_persistence.py tests/test_export.py"
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
SPARROW=0
if [ -x "tests/sparrow/.build/jdk-25.0.4.1+1/Contents/Home/bin/java" ]; then
  for t in tests/sparrow/test_sparrow_interop.py tests/sparrow/test_qr_airgap.py \
           tests/sparrow/test_export_interop.py tests/sparrow/test_recovery.py; do
    SLOG="$LOGDIR/$(basename "$t").log"
    if (cd tests/sparrow && $PY "$(basename "$t")" >"$SLOG" 2>&1); then
      # Report the count the suite OBSERVED, never one written down here.
      # Three hardcoded totals in two files were all wrong at once (audit
      # A8, 2026-09-06): 86 and 81 for a set that runs 132.
      N=$(grep -oE "PASS +[0-9]+" "$SLOG" | tail -1 | grep -oE "[0-9]+")
      SPARROW=$((SPARROW + ${N:-0}))
      echo "PASS $t${N:+  ($N checks)}"
    else
      echo "FAIL $t"
      sed 's/^/      | /' "$SLOG" | tail -12
      echo "      | full output: $SLOG"
      FAILED=1
    fi
  done
  echo "     tests/sparrow total: $SPARROW checks against Sparrow's own library"
else
  echo "(not run: tests/sparrow, the only checks that read a QR with"
  echo "          anything but our own decoder. Run tests/sparrow/setup.sh"
  echo "          once to build it; the run then prints its own count.)"
fi
echo "(not run here: tests/m1  20 checks + the two legibility rigs;"
echo "               needs its setup.sh and Rosetta on Apple Silicon)"
# 152 lines of test that nothing ran and nothing mentioned, so nobody knew
# they were there (audit A6, 2026-09-06). They spend real mainnet sats, so
# they cannot join a suite; saying so is the whole fix.
echo "(real money:   tests/m4lite_mainnet.py, tests/m4lite_taproot.py"
echo "               a funded burner UTXO on MAINNET. Needs CORKY_BURNER_XPRV"
echo "               or an xprv file as argv[1]. Last run 2026-08-19:"
echo "               tx 19d1180b, block 963255.)"
# The on-device rigs need the board, the hat and the camera, and a human to
# press buttons and aim a lens. Nothing here can stand in for them.
echo "(on the board: tests/hw_buttons.py  8 controls, prompts on the LCD"
echo "               tests/hw_camera.py   viewfinder + decode vs Sparrow"
echo "               m0/m0_gate.py        the memory gate; see m0/FLASH.md)"
exit $FAILED
