# A10 What the earlier maps left open

Type: `wayfinder:task`, HITL. **Needs the board and Ben's phone.**

**Blocked by:** Nothing, and it needs the board and Ben's phone.

## Question

Two maps are still open and their items are beta blockers, not
housekeeping. This ticket is where they get weighed rather than
duplicated: read them, decide which block a beta, and record that.

From `export-and-policies`:

- **N1**, the card cannot be removed because the OS is on it, which is M3.
- **N4**, `butlers-playground` is 26 commits behind, so the encrypted file
  backup exists only in this repo's history. 50 conflict hunks.
- **N5**, whether a RAM image fits at all: 374MB estimated of 447.
- **R6**, M0 fails at 81MB against 100 required.
- **T1, T2, T3**, whether each coordinator's camera reads our QR and
  whether the address matches. The board is on and Ben has the phone.

From `e2e-before-testers`:

- **18**, the board run with the Sparrow laptop.
- **22**, the phone proofs.
- **23**, docs, PINS and the review for testers.

R6 is the one that decides the shape of the beta. 81MB of headroom on a
250-input stress case either gets fixed by the hardened image or the beta
ships with a stated input limit.
