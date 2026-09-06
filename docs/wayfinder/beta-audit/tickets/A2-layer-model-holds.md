# A2 Does the layer model actually hold, end to end

Type: `wayfinder:task`, AFK.

**Blocked by:** Nothing. Takeable now.

## Question

The whole trust argument is three sentences: Layer 1 transforms secrets
and is zero lines; Layer 2 sees secrets and computes nothing on them;
Layer 3 never touches them. `tests/test_integrity.py` enforces the import
allowlist, and `tests/test_generate.py` enforces the no-RNG rule.

Nothing enforces the middle sentence. "Computes nothing on them" is a
claim about what Layer 2 DOES with a key, and it is checked by reading.

On 2026-09-05 a Layer 2 function put a private key on the command line for
several hours, and a two-axis review found it rather than a test. That is
one failure of the claim. This ticket asks whether there are others.

Trace every path a key takes, from the moment it enters to the moment it
is dropped, and at each step name what holds it, for how long, and what is
done to it. Then say which of those steps a test would catch a change to.

The README publishes the answer as "two moments". Prove the number or
correct it.
