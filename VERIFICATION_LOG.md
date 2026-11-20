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

## 4. Kernel check (full build) — running since 19:14
### Run 2 — 288 cores (2 × Xeon 6985P-C), 1 TB RAM, fresh build

- **17:49:55** fresh `lake build` (all 11 default targets) with `LEAN_NUM_THREADS=288`, as requested.
  Lake itself became the bottleneck: ~225 cores of lake's own CPU (load ~450) while only 7–47 `lean`
  processes ran, i.e. 30–50 modules/min. `perf` on an earlier attempt at the same setting (run 2a: 15–29 `lean`
  processes, 33–50 modules/min) showed lake's ~270 worker threads spending 85 % of their time in
  `lean_st_ref_take` on its single shared build-store reference (per-module transitive-import walks).
  Run 1 on 128 cores had reached ~400 modules/min with plain `lake build`.
- **18:01** lake stopped after ~11 min (log archived as `logs/build.run2b.log`, no `EXIT`); 670 modules it had
  compiled were kept.
- **18:01:36** replaced by `tools/sched.py`: parses the imports of all 175,187 modules (753,569 local import
  edges, no cycles, critical path 203 modules), keeps 288 `lean` processes running (critical-path first,
  96 GB free-memory floor) and passes the lakefile's exact options (`-D` options, `--tstack=400000`,
  `synthInstance.maxHeartbeats=400000` for `GroundTheory.LocalFields/GlobalFields`). Same toolchain binary,
  same per-module kernel checking as lake; it only replaces lake's scheduler. Measured 18:01:40→18:05:50:
  670→6,341 modules, ≈1,350 modules/min, 288 `lean` processes, CPU 82.5 % user + 16 % sys, 165 GB RAM.
- **Incident — run 2c discarded (19:13).** `sched.py` invoked `lean` without `-R/--root`, so with the project
  directory as working directory Lean named every module `src.<Path>` instead of `<Path>` (Lake passes the
  module name explicitly in its per-module setup file). Names Lean derives from the module name changed with it:
  auto-generated instance names got a `_src` suffix instead of Lake's `_formalism`/`_development`/…, and private
  names gained a `src` component. Symptom: `Development.AbelianVarietyTheory.Definitions.AutomorphicMembership.OmPinsTr`
  refers to `instNumberFieldSubtypeComplexMemIntermediateFieldRatF_formalism` by name and failed
  (`Unknown identifier`), blocking 425 downstream modules; 84 of a random 2,000 built `.olean`s contained `_src`
  names. Reproduced on a scratch module (`instInhabitedForallNatBool_src` without `-R`,
  `instInhabitedForallNatBool_formalism` with `-R`). Diagnosed by the dashboard session, confirmed here.
  The ~105,700 modules built in run 2c were deleted (logs kept in `logs/run2c/`).
- **19:14:52** rebuild from scratch (`ALREADY_BUILT 0`) with `-R <srcDir>` added to every `lean` call. Spot check after
  2 min: 3,356 new `.olean`s, no `_src` instance names, Lake-style `_<library>` suffixes present.
- Status: Rebuild from scratch 19:14 UTC with --root fix (-R srcDir); sched.py, 288 parallel lean processes. Run 2c discarded: module names were src.<Path> (1 failed, 425 blocked)

| UTC | modules done | modules/min (last 5 min) | `lean` procs | load |
|---|---|---|---|---|
| 18:23:56 | 32,035 | 1581 | 288 | 351.36 |
| 18:28:56 | 39,532 | 1499 | 288 | 344.86 |
| 18:33:56 | 46,704 | 1434 | 288 | 334.60 |
| 18:38:56 | 53,922 | 1443 | 288 | 343.68 |
| 18:43:56 | 61,246 | 1464 | 287 | 332.95 |
| 18:48:57 | 68,499 | 1445 | 288 | 337.04 |
| 18:53:57 | 75,871 | 1474 | 288 | 332.12 |
| 18:58:57 | 83,107 | 1447 | 288 | 338.21 |
| 19:03:57 | 90,294 | 1437 | 288 | 335.05 |
| 19:08:57 | 97,445 | 1430 | 288 | 335.48 |
| 19:13:58 | 104,722 | 1455 | 288 | 341.64 |

### Run 1 — earlier 128-core / 503 GB machine (from 17:11)

- Command: `lake build` (all 11 default targets), output in `logs/build.log`.
- Lake schedules one `lean` process per ready module across all 128 cores; load average reached 122 within two minutes.
- Progress is published to the dashboard every 120 s.
- Run 1's record ends here: sections 5–7 were still pending when that machine's session ended. Run 2 redoes everything from a fresh build.

## 5. Axiom audit — pending

## 6. Statement audit — pending

## 7. Independent replay — pending

Tool: the kernel replay checker shipped with the toolchain itself, `leanchecker` (Lean v4.33.1,
`src/lean/LeanChecker.lean`; the upstreamed successor of `lean4checker`). For each module it imports the
module's dependencies from their `.olean`s and re-adds every constant of the module to that environment
through the kernel (`Lean.Environment.replay`), so a constant that reached an `.olean` without kernel checking
(environment hacking, `debug.skipKernelTC`, tampered files) is rejected.

The shipped CLI takes module-name *prefixes* and rescans every `.olean` on the search path once per argument
(measured: ~4 s per argument with 14k `.olean`s; ~190k here), so driving 175k modules through it is
impractical. `replayexact` (`results/tools/ReplayExact.lean`) contains leanchecker's `replayFromImports`
verbatim, compiled against the same toolchain, and only changes the driver: an exact module list, every failure
reported. It runs on the exact import closure of `Main` as recorded in the `.olean` headers
(`ModClosure.lean`), core `Init`/`Std`/`Lean`/`Lake` excluded (they ship with the toolchain), in chunks of 100
modules over 256 parallel processes. Mathlib and the other packages (prebuilt cache, never compiled here) are
replayed too.

Smoke tests before the build finished (also re-run by the chain into
[`results/negative_control.txt`](results/negative_control.txt)): a 2-line module that adds
`bogusFalse : False := True.intro` with `debug.skipKernelTC` compiles, and `#print axioms` on a theorem using it
reports **no axioms**; shipped `leanchecker` and `replayexact` both reject it (`(kernel) declaration type
mismatch`). Both pass a correct control module and Mathlib modules (`Mathlib.Logic.Basic`,
`Mathlib.NumberTheory.LSeries.RiemannZeta`, 21 modules of `Mathlib.NumberTheory.LSeries`).

Supplementary: `leanchecker --fresh Main` (re-adds every constant of the whole closure, Mathlib included, to an empty environment, single-threaded): queued after the parallel replay.
