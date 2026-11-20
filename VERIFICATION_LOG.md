# Verification log

All times UTC, 2026-11-20. Machine: 128 cores, 503 GB RAM, Linux.

## 1. Download — done (17:07)

- `curl` × 14 in parallel (`xargs -P14`); 13 × 18,000,000 B + 5,275,554 B = 239,275,554 B in under one second.
- Per-part hashes in [`parts.sha256`](parts.sha256). Concatenated archive:
  `sha256 9631b4f020199e580ba86178cb56c6e9b09f690c2369a80dc4334aa93f49c7fc`, `gzip -t` OK.
- Contents: 175,187 `.lean` files plus `lakefile.toml`, `lake-manifest.json`, `lean-toolchain`. No symlinks or hard links.

| Directory | Files |
|---|---|
| `Development` | 141,928 |
| `Formalism` | 18,254 |
| `GroundTheory` | 8,507 |
| `ReciprocityTheory` | 3,845 |
| `CompanionTheory` | 2,027 |
| `PositivityTheory` | 449 |
| `Lemmata` | 167 |
| `BuildAid`, `Supplements`, `Statements.lean`, `Main.lean` | 10 |

## 2. Static audit — done (17:08–17:10)

Parallel `grep` (128 workers) over every source file.

| Construct | Occurrences |
|---|---|
| `sorry` / `admit` | 0 |
| `axiom` | 0 |
| `native_decide`, `ofReduceBool`, `trustCompiler` | 0 |
| `implemented_by`, `extern`, `unsafe`, `opaque` | 0 |
| `debug.skipKernelTC` | 0 |
| `initialize`, `IO.` | 0 |
| `macro` (tactic/term abbreviations) | 87 |
| `run_tac` | 32 |
| `run_cmd` | 5 |
| `elab` | 4 |
| `addDecl` | 2 |

Reviewed by hand:

- `BuildAid/D1–D5.lean`: `run_cmd` adds namespaces to the `LibrarySuggestions` deny-list. Affects premise selection only.
- `kexactB`, `kcopy` (custom tactics) assign a goal metavariable directly, skipping the elaborator's defeq check.
  The resulting proof term is still type-checked by the kernel when the theorem is added.
- `CutCptCopy.lean`: `cpt_copy_thms` copies declarations under renamed constants via `addDecl`, which goes through the kernel.
- `lakefile.toml` is declarative (no build-time Lean code). Notable options: `maxHeartbeats = 4000000`, `--tstack=400000`.

None of these can make the kernel accept a false statement, but they are the reason step 4 (axioms) and
step 6 (independent replay) matter.

## 3. Toolchain — done (17:10–17:11)

- `elan` 4.4.0, Lean `4.33.1` (commit `819816b2e0a3`).
- `lake exe cache get`: 8,690 prebuilt Mathlib files in 73 s. Mathlib HEAD = `0df444a360ea…` as pinned.
- `lake-manifest.json` semantically identical to the one shipped in the archive.

## 4. Kernel check (`lake build`) — running since 17:11

- Command: `lake build` (all 11 default targets), output in `logs/build.log`.
- Lake schedules one `lean` process per ready module across all 128 cores; load average reached 122 within two minutes.
- Progress is published to the dashboard every 120 s.

## 5. Axiom audit — pending

## 6. Statement audit — pending

## 7. Independent replay — pending
