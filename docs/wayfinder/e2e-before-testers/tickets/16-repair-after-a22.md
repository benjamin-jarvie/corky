# 16 Repair what the A-22 cut left broken, and the log file

Labels: wayfinder:task (AFK)
Blocked by: none
Status: resolved 2026-09-05

## Question

Four scripts outside `run_tests.sh` still call the deleted shim or the
removed codex32 screen, so they cannot run:

- `tests/sparrow/harness.py`: `signer.open_session(rpc, MNEMONIC)` and a
  `shim` path insert. The 58 Sparrow interop checks cannot run today.
- `m0/m0_gate.py`: the same call. The M0 gate must stay runnable for the CM4.
- `tests/m4lite_mainnet.py` and `tests/m4lite_taproot.py`: import
  `bip39_shim`.
- `tools/render_screens.py`: `screens.codex32_entry`.

Port each to the xprv the mnemonic produced, as the main suites were.

Also: `m0/bitcoin.conf` and `/etc/corky-bitcoin.conf` carry
`debuglogfile=0`. Core reads that as a log file named `0`, and on the board
a 10KB file named `0` sits in the ramdisk with Core's full log in it. Core's
own first lines warn the log may contain privacy-sensitive information. It
is in RAM and dies at power-off, but it grows inside a 128MB ramdisk and
was never meant to exist. The fix is `nodebuglogfile=1`. Re-run the M0 gate
after, because its report said it used these exact values.

## Answer (built, 2026-09-05)

All four scripts run again.

- **`tests/sparrow/harness.py`** was ported in ticket 12, which is what
  unblocked the Sparrow interop suites. The 58 existing checks and the 16
  new export checks all run.
- **`m0/m0_gate.py`** now opens its session with the xprv that the old
  mnemonic produced, so the gate measures the same wallet it always did.
  Its report line changed from "shim + importdescriptors" to
  "importdescriptors", because there is no shim to time.
- **`tests/m4lite_mainnet.py` and `tests/m4lite_taproot.py`** took their
  burner key from a mnemonic in a scratchpad file belonging to a session
  that ended weeks ago, so they could not have run even before A-22. They
  now take an xprv, as a file named on the command line or in
  `CORKY_BURNER_XPRV`, and say so when neither is given. The recorded
  2026-08-19 result stands: tx 19d1180b, block 963255.
- **`tools/render_screens.py`** called `screens.seed_entry` and
  `screens.codex32_entry`, both gone. It now renders the current set,
  including the keys list, one key's menu, the export chooser and an
  address page, at both panel sizes.

**The log file** was the other item on this list and was fixed with ticket
08: `debuglogfile=0` named a log file called `0` in the datadir, and the
conf now carries `nodebuglogfile=1`, pinned by a test.

Not done: re-running the M0 gate on the board. It reads `/proc/meminfo`, so
it cannot run on the Mac at all. Ticket 18 runs it.
