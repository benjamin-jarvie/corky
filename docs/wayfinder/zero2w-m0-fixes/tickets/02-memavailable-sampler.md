# 02 MemAvailable needs a sampler thread

Labels: wayfinder:task (AFK)
Blocked by: none

## Question

m0_gate.py samples MemAvailable twice: after funding and after signing.
The true low point can fall between samples, for example during descriptor
import or mid-sign. The gate then overstates headroom against the 100MB
pass line. What sampling gives the real low-water mark?

Fix: a daemon thread samples MemAvailable every 200ms from before bitcoind
starts until teardown; the report takes the minimum of the thread's floor
and the two existing spot samples.

## Resolution (2026-08-31)

Done. `_watch_low_water()` daemon thread samples MemAvailable every 200ms
from before bitcoind starts until the finally block stops it. The report
takes the minimum of the thread floor and the two existing spot samples,
so the number can only get more honest. On macOS every sample is None and
the dev-run branch prints as before. Verified by a full dev run.

Closed. Trello BB-22.
