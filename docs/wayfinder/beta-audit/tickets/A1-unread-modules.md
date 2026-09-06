# A1 Read the four modules nothing has read

Type: `wayfinder:task`, AFK. **Blocks A5, A6.**

**Blocked by:** Nothing. Takeable now.

## Question

617 lines ship on the device that no review in this project has opened:

| module | lines | what it carries |
|---|---|---|
| `qrchannel.py` | 361 | every byte in and out by camera and panel |
| `filechannel.py` | 110 | every byte in and out by stick or card |
| `hal.py` | 119 | the display and the buttons |
| `splash.py` | 27 | the first frame |

The two-axis review reads a diff, and these were not in it. The design
pass named them and did not open them either.

Read them against the same standards the review applies: PLAN's
amendments as laws, TESTING.md's rules, CONTEXT.md's vocabulary, and the
layer model. Report per module: what its interface is, whether anything in
it touches key material, what it does when its input is hostile or absent,
and what has never been executed.

Not a rewrite. The output is findings with line numbers, each reproduced
before it is written down.
