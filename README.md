# meowbolge 🐈‍⬛

Generator of **classic Malbolge** programs that print arbitrary text.
Verification is always against a real interpreter — never against a model.

```
 /\_/\
( o.o )
 > ^ <
```
*(actual output of `examples/gatito.malbolge`, verified on 3 backends)*

## The idea

Writing Malbolge is not writing instructions. The opcode comes out of

    op = (mem[c] + c) % 94

so it is not decided by the cell: it is decided by the cell **and its position**.
At each position the required opcode is forced by solving `mem[c] = (op - c) mod 94`.
Generating Malbolge means solving one congruence per step.

The state is not guessed blindly: each candidate is accepted ONLY if the real
interpreter emits exactly what was asked for. Fast proposals yes, shortcuts no.

## Usage

```powershell
py meowbolge.py "meow"            # imprime el programa en stdout
py examples/make_gatito.py        # regenera/verifica textos multi-línea
```

Environment variables:

| Variable | Default |
|---|---|
| `MEOWBOLGE_INTERPRETER` | canonical in-repo interpreter (absolute path) |
| `MEOWBOLGE_ENGINE_C` | optional: malbolge.exe for extra verification |
| `MEOWBOLGE_ORACLE_DIR` | optional: malbolge-oracle directory |

## How it works (v2)

For each character, in order:

1. **Direct** — if `a` already holds, a single OUT.
2. **Fast path (state-guided search)** — a level-by-level BFS over the state
   `(a, d)` with dedup and a bounded beam, simulating the machine rules EXACTLY
   (post-execution encryption, unconditional advance of `d`, ROT/CRAZY writes
   over `mem[d]`). It returns MANY candidate routes ordered by length; real
   verification decides which one survives.
   - Tier A: MOVD only towards known past cells (exact simulation).
   - Tier B: far jumps allowed except the nearby source window
     (approximate; the verifier discards divergences).
3. **Brute force** — exhaustive enumeration as a fallback (the original v1).

## The kitten

`examples/gatito.malbolge` (750 cells, 652 steps, clean HALT) was generated as a
chain: meowbolge-v2 solved the friendly characters; the hard ones (`/`) fell
outside the proposer's stable range in CPython and the fallback used
[Malbolge-Translator](https://github.com/DannyBaanks/Malbolge-Translator)
(seed 42, 0.95 s, 35,756 evaluations). Triple verification with no discrepancies:
canonical interpreter + independent oracle + C engine.
Full evidence with hashes: `evidence/gatito_evidence.json`.

Honest lesson: the border between "fast guidance" and "heavy search" is Zig
territory — the arsenal has `frontier_scan`, which evaluates a billion programs
in hours; meowbolge-python stays in the hundreds of thousands.

## Status

- ✅ v2 generator with fast path + mandatory real verification
- ✅ ASCII kitten verified on 3 backends
- ⚠️ "hard" characters may require the external fallback or more muscle
- ❌ no license yet; laboratory code
