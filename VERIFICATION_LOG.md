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

## 4. Kernel check (full build) — done (19:14–21:15)
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
- **21:16** `#print axioms` (34 s) and `StatementAudit.lean` (37 s) finished. The independent axiom walk ran at
  only ~130 constants/s: `AxiomWalk.lean` evaluated `env.header.moduleNames` once per visited constant, and
  `env.header` costs ~12 ms per access on this ~186k-module environment. That expression only feeds the
  per-package `byRoot` statistics; axiom collection, the `missing` check and the verdict do not use it.
- **21:44** chain stopped and restarted with the fix (`modNames := env.header.moduleNames` read once before the
  loop; the original binary is kept as `axiomwalk.v1`). `#print axioms` and the statement audit were re-run as
  part of the restart. A test copy of the fixed walk finished `riemannHypothesis` (1,478,219 reachable constants)
  in about 5.5 min instead of an estimated 3 h.
- **22:16** by the operator's decision only Phase 4 (the full replay) runs; the 59-module shipped-`leanchecker`
  cross-check and the negative-control re-run were dropped. `chain.sh` (bash process only) was stopped while its
  replay kept running, and `chain_tail.sh` took over: replay summary and commit, then the supplementary
  `leanchecker --fresh Main`, whose dashboard phase is posted only when it has finished.
- **22:22** by the operator's decision `leanchecker --fresh Main` is not run either: the run ends with Phase 4.
  `chain_tail.sh` (bash process only) was restarted without that step; the replay kept running throughout.
- **Result:** `EXIT 0`, built=175187/175187 failed=0 blocked=0 not_run=0, wall time 2:00:33 for the `sched.py` phase.
- Failed modules (`✖` lines): 0. Modules with any warning: 104066. Warning lines mentioning `sorry`: 0.
- Details: [`results/build_summary.txt`](results/build_summary.txt); throughput samples every 5 min: [`results/throughput_run2.txt`](results/throughput_run2.txt).

| UTC | modules done | modules/min (last 5 min) | `lean` procs | load |
|---|---|---|---|---|
| 18:23:56 | 32,035 | 1581 | 288 | 351.36 |
| 18:33:56 | 46,704 | 1434 | 288 | 334.60 |
| 18:43:56 | 61,246 | 1464 | 287 | 332.95 |
| 18:53:57 | 75,871 | 1474 | 288 | 332.12 |
| 19:03:57 | 90,294 | 1437 | 288 | 335.05 |
| 19:13:58 | 104,722 | 1455 | 288 | 341.64 |
| 19:23:58 | 13,550 | 1486 | 288 | 400.23 |
| 19:33:58 | 30,078 | 1730 | 288 | 356.42 |
| 19:43:59 | 46,510 | 1545 | 288 | 341.64 |
| 19:53:59 | 62,387 | 1603 | 288 | 345.58 |
| 20:04:00 | 78,447 | 1597 | 288 | 334.28 |
| 20:14:00 | 94,173 | 1552 | 288 | 347.82 |
| 20:24:01 | 110,080 | 1570 | 288 | 338.22 |
| 20:34:01 | 125,646 | 1540 | 288 | 336.21 |
| 20:44:02 | 140,813 | 1546 | 288 | 330.08 |
| 20:54:02 | 155,768 | 1465 | 288 | 329.57 |
| 21:04:03 | 169,539 | 1338 | 288 | 334.20 |
| 21:14:03 | 175,184 | 7 | 1 | 1.95 |

### Run 1 — earlier 128-core / 503 GB machine (from 17:11)

- Command: `lake build` (all 11 default targets), output in `logs/build.log`.
- Lake schedules one `lean` process per ready module across all 128 cores; load average reached 122 within two minutes.
- Progress is published to the dashboard every 120 s.
- Run 1's record ends here: sections 5–7 were still pending when that machine's session ended. Run 2 redoes everything from a fresh build.

## 5. Axiom audit — done (21:44–21:50)

Two independent methods. (1) `#print axioms` (`audit/Audit.lean`). In Lean 4.33 this reads axiom
lists that each `.olean` pre-computes at export time and silently skips unknown constants, so
(2) `AxiomWalk.lean` (compiled, in `results/tools/`) walks the bodies of every constant reachable
from each theorem in the fully imported environment and fails on any missing constant.

| Theorem | `#print axioms` | Independent walk (reachable constants) |
|---|---|---|
| `riemannHypothesis` | propext, Classical.choice, Quot.sound | propext, Classical.choice, Quot.sound (1,478,219; missing 0) |
| `riemannZeta_eq_zero_re` | propext, Classical.choice, Quot.sound | propext, Classical.choice, Quot.sound (1,478,221; missing 0) |
| `LFunction_ne_zero_of_half_lt_re` | propext, Classical.choice, Quot.sound | propext, Classical.choice, Quot.sound (1,478,211; missing 0) |
| `LFunction_eq_zero_re` | propext, Classical.choice, Quot.sound | propext, Classical.choice, Quot.sound (1,478,224; missing 0) |
| `LFunction_eq_zero_re_of_isPrimitive` | propext, Classical.choice, Quot.sound | propext, Classical.choice, Quot.sound (1,478,214; missing 0) |

Verdict: All 5 theorems: only Classical.choice,Quot.sound,propext (#print axioms and independent body walk agree). Raw output: [`results/audit.log`](results/audit.log), [`results/axiom_walk.txt`](results/axiom_walk.txt).

## 6. Statement audit — done (21:44–21:50)

`StatementAudit.lean` (in `results/tools/`, run against the built `Main`) checks, by machine:

- `ORIGIN_OK RiemannHypothesis ← Mathlib.NumberTheory.LSeries.RiemannZeta`
- `ORIGIN_OK riemannZeta ← Mathlib.NumberTheory.LSeries.RiemannZeta`
- `ORIGIN_OK DirichletCharacter ← Mathlib.NumberTheory.DirichletCharacter.Basic`
- `ORIGIN_OK DirichletCharacter.LFunction ← Mathlib.NumberTheory.LSeries.DirichletContinuation`
- `ORIGIN_OK DirichletCharacter.IsPrimitive ← Mathlib.NumberTheory.DirichletCharacter.Basic`
- `ORIGIN_OK Complex.re ← Mathlib.Data.Complex.Basic`
- `ORIGIN_OK NeZero ← Init.Data.NeZero`
- `ORIGIN_OK RiemannZetaZerosOnLine ← Statements`
- `ORIGIN_OK DirichletLNonvanishingRightOfHalf ← Statements`
- `ORIGIN_OK DirichletLZerosOnLine ← Statements`
- `ORIGIN_OK PrimitiveDirichletLZerosOnLine ← Statements`
- `STATEMENTS_IMPORTS_OK [Init, Init, Mathlib]`
- `STMT_DEPS_OK RiemannZetaZerosOnLine: 34 external constants (Mathlib/core), auxiliary in Statements: [RiemannZetaZerosOnLine._proof_1]`
- `STMT_DEPS_OK DirichletLNonvanishingRightOfHalf: 38 external constants (Mathlib/core), auxiliary in Statements: [RiemannZetaZerosOnLine._proof_1]`
- `STMT_DEPS_OK DirichletLZerosOnLine: 33 external constants (Mathlib/core), auxiliary in Statements: [RiemannZetaZerosOnLine._proof_1]`
- `STMT_DEPS_OK PrimitiveDirichletLZerosOnLine: 34 external constants (Mathlib/core), auxiliary in Statements: [RiemannZetaZerosOnLine._proof_1]`
- `THM_TYPE_OK riemannHypothesis : RiemannHypothesis (theorem in Main)`
- `THM_TYPE_OK riemannZeta_eq_zero_re : RiemannZetaZerosOnLine (theorem in Main)`
- `THM_TYPE_OK LFunction_ne_zero_of_half_lt_re : DirichletLNonvanishingRightOfHalf (theorem in Main)`
- `THM_TYPE_OK LFunction_eq_zero_re : DirichletLZerosOnLine (theorem in Main)`
- `THM_TYPE_OK LFunction_eq_zero_re_of_isPrimitive : PrimitiveDirichletLZerosOnLine (theorem in Main)`
- `example : RiemannZetaZerosOnLine = RiemannHypothesis := rfl` type-checks.
- Mathlib checkout `0df444a360ea`, 0 modified files (all packages: [`results/package_revs.txt`](results/package_revs.txt)).

Definitions as printed by Lean (`#print`), for reading by a human:

```
def RiemannHypothesis : Prop :=
∀ (s : ℂ), riemannZeta s = 0 → (¬∃ n, s = -2 * (↑n + 1)) → s ≠ 1 → s.re = 1 / 2
def riemannZeta : ℂ → ℂ :=
HurwitzZeta.hurwitzZetaEven 0
def DirichletCharacter.LFunction : {N : ℕ} → [NeZero N] → DirichletCharacter ℂ N → ℂ → ℂ :=
fun {N} [NeZero N] χ s => ZMod.LFunction (⇑χ) s
def DirichletCharacter.IsPrimitive.{u_1} : {R : Type u_1} →
  [inst : CommMonoidWithZero R] → {n : ℕ} → DirichletCharacter R n → Prop :=
fun {R} [CommMonoidWithZero R] {n} χ => χ.conductor = n
def RiemannZetaZerosOnLine : Prop :=
∀ (s : ℂ), riemannZeta s = 0 → (¬∃ n, s = -2 * (↑n + 1)) → s ≠ 1 → s.re = 1 / 2
def DirichletLNonvanishingRightOfHalf : Prop :=
∀ (N : ℕ) [inst : NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
  1 / 2 < s.re → χ ≠ 1 ∨ s ≠ 1 → DirichletCharacter.LFunction χ s ≠ 0
def DirichletLZerosOnLine : Prop :=
∀ (N : ℕ) [inst : NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
  0 < s.re → s.re < 1 → DirichletCharacter.LFunction χ s = 0 → s.re = 1 / 2
def PrimitiveDirichletLZerosOnLine : Prop :=
∀ (N : ℕ) [inst : NeZero N] (χ : DirichletCharacter ℂ N),
  χ.IsPrimitive → ∀ (s : ℂ), 0 < s.re → s.re < 1 → DirichletCharacter.LFunction χ s = 0 → s.re = 1 / 2
```

Verdict: Mathlib RiemannHypothesis/riemannZeta/LFunction/IsPrimitive (Mathlib 0df444a, clean); RiemannZetaZerosOnLine = RiemannHypothesis by rfl; Statements imports only Mathlib; theorem types exact. Raw output: [`results/statement_audit.txt`](results/statement_audit.txt).

## 7. Independent replay — done (21:50–22:49)

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

Smoke tests before the build finished: a 2-line module that adds
`bogusFalse : False := True.intro` with `debug.skipKernelTC` compiles, and `#print axioms` on a theorem using it
reports **no axioms**; shipped `leanchecker` and `replayexact` both reject it (`(kernel) declaration type
mismatch`). Both pass a correct control module and Mathlib modules (`Mathlib.Logic.Basic`,
`Mathlib.NumberTheory.LSeries.RiemannZeta`, 21 modules of `Mathlib.NumberTheory.LSeries`).

```
tool=replayexact (verbatim leanchecker replayFromImports, Lean v4.33.1)
closure_noncore_modules=183877 core_modules_skipped=2323
replayed_ok=183877 failed=0 not_ok=0
wall_seconds=3557 sum_module_seconds=816978
ok_by_root={'Development': 141928, 'Formalism': 18254, 'GroundTheory': 8507, 'Mathlib': 8312, 'ReciprocityTheory': 3845, 'CompanionTheory': 2027, 'PositivityTheory': 449, 'Batteries': 192, 'Lemmata': 167, 'Aesop': 132, 'Qq': 14, 'Plausible': 13, 'ProofWidgets': 13, 'ImportGraph': 10, 'BuildAid': 5, 'LeanSearchClient': 4, 'Supplements': 3, 'Statements': 1, 'Main': 1}
slowest=GroundTheory.PAdicHodge.BCrisGalois 391.2s, Development.WeilBound.CoreStatements.PadicHodgeComparison.EtaleCohomologyComparison.BocksteinBaseChange.TiltSectionUnits.FcIsUnitSub 343.6s, Development.AbelianVarietyTheory.Proofs.UniformizationProofs.ExistsUniqueTwistedSectionOfCompatibleLevels 289.8s, Development.AbelianVarietyTheory.Proofs.IwasawaDecomposition.FormsRe 275.3s, Development.AbelianVarietyTheory.Proofs.CoherentCohomologyProofs.PushComparisonBijectiveOfIsClosedEmbedding 250.4s, GroundTheory.ArithmeticGeometry.SchemeCohomology.ProperCohomology.FormalTower 224.6s, GroundTheory.PAdicHodge.BCrisTensorK 211.3s, Development.AbelianVarietyTheory.Definitions.GaloisGeometry.SectionOfFreeOnUnitComp 198.3s, GroundTheory.PAdicHodge.BCrisNewton 176.7s, Development.AutomorphicSpectrum.Proofs.GeometryProofs.IsEigFrameOfFrPt 167.7s
VERDICT OK
```

By the operator's decision (22:15 UTC), the planned 59-module cross-check with the shipped `leanchecker` binary and the re-run of the negative control were dropped: Phase 4 replays every module of the closure with leanchecker's own `replayFromImports` (verbatim copy).

Verdict: 183877 modules of Main's import closure re-checked by the kernel (replayexact), 0 failures (59 min).

`leanchecker --fresh Main` (single-threaded re-check of the whole closure in an empty environment) was not run, by the operator's decision (22:22 UTC).
