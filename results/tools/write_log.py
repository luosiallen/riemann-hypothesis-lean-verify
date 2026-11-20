#!/usr/bin/env python3
"""Regenerate sections 4-7 of repo/VERIFICATION_LOG.md (run 2) from events.json and repo/results/*.
Everything above '## 4.' is left untouched; run-1 history for section 4 is kept verbatim."""
import json, os, re, time
R = "/home/allenluo/rhv"; RES = R + "/repo/results"; VL = R + "/repo/VERIFICATION_LOG.md"
RUN1_SEC4 = """- Command: `lake build` (all 11 default targets), output in `logs/build.log`.
- Lake schedules one `lean` process per ready module across all 128 cores; load average reached 122 within two minutes.
- Progress is published to the dashboard every 120 s.
- Run 1's record ends here: sections 5–7 were still pending when that machine's session ended. Run 2 redoes everything from a fresh build."""

def rd(p):
    try: return open(p, encoding="utf-8", errors="replace").read()
    except OSError: return ""
def hm(ts): return time.strftime("%H:%M", time.gmtime(ts)) if ts else "?"
ev = {p["id"]: p for p in json.load(open(R + "/events.json"))["phases"]}
def head(pid, title):
    p = ev.get(pid, {}); st = p.get("state", "pending")
    when = ""
    if st == "running": when = f" since {hm(p.get('start'))}"
    elif st in ("done", "failed"): when = f" ({hm(p.get('start'))}–{hm(p.get('end'))})"
    return f"{title} — {st}{when}", p.get("note", "")

out = []
# ---------------- 4. build ----------------
h, note = head("build", "## 4. Kernel check (full build)")
out.append(h + "\n")
bs = rd(RES + "/build_summary.txt")
def grab(pat, s=bs):
    m = re.search(pat, s, re.M); return m.group(1) if m else None
out.append("""### Run 2 — 288 cores (2 × Xeon 6985P-C), 1 TB RAM, fresh build

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
""")
if bs:
    summ = grab(r"^SUMMARY (.*)$"); wall = grab(r"^Elapsed \(wall clock\).*?: (\S+)$"); code = grab(r"^EXIT (\S+)")
    out.append(f"- **Result:** `EXIT {code}`, {summ}, wall time {wall} for the `sched.py` phase.\n")
    out.append(f"- Failed modules (`✖` lines): {grab(r'^failed_lines=(\d+)')}. Modules with any warning: "
               f"{grab(r'^modules_with_warnings=(\d+)')}. Warning lines mentioning `sorry`: "
               f"{grab(r'^warning_lines_mentioning_sorry=(\d+)')}.\n")
    out.append("- Details: [`results/build_summary.txt`](results/build_summary.txt); throughput samples every 5 min: "
               "[`results/throughput_run2.txt`](results/throughput_run2.txt).\n")
elif note:
    out.append(f"- Status: {note}\n")
tp = rd(R + "/kv/throughput.log").strip().splitlines()
rows = [l.split() for l in tp if l and not l.startswith("#") and "EXIT" not in l][1:]  # first sample has no previous point
if rows:
    out.append("\n| UTC | modules done | modules/min (last 5 min) | `lean` procs | load |\n|---|---|---|---|---|\n")
    step = max(1, len(rows) // 12)
    for r in rows[::step] + ([rows[-1]] if (len(rows) - 1) % step else []):
        out.append(f"| {r[0]} | {int(r[1]):,} | {r[2]} | {r[3]} | {r[4]} |\n")
out.append("\n### Run 1 — earlier 128-core / 503 GB machine (from 17:11)\n\n" + RUN1_SEC4 + "\n\n")

# ---------------- 5. axioms ----------------
h, note = head("axioms", "## 5. Axiom audit")
out.append(h + "\n\n")
au, aw = rd(RES + "/audit.log"), rd(RES + "/axiom_walk.txt")
if au:
    out.append("Two independent methods. (1) `#print axioms` (`audit/Audit.lean`). In Lean 4.33 this reads axiom\n"
               "lists that each `.olean` pre-computes at export time and silently skips unknown constants, so\n"
               "(2) `AxiomWalk.lean` (compiled, in `results/tools/`) walks the bodies of every constant reachable\n"
               "from each theorem in the fully imported environment and fails on any missing constant.\n\n"
               "| Theorem | `#print axioms` | Independent walk (reachable constants) |\n|---|---|---|\n")
    for t in ["riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re",
              "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive"]:
        m = re.search(r"'%s' depends on axioms: \[([^\]]*)\]" % t, au)
        pa = m.group(1) if m else ("none" if f"'{t}' does not depend on any axioms" in au else "**missing**")
        w = re.search(r"WALK %s: reachable=(\d+) axioms=\[([^\]]*)\] missing=(\d+)" % t, aw)
        wa = f"{w.group(2)} ({int(w.group(1)):,}; missing {w.group(3)})" if w else "**missing**"
        out.append(f"| `{t}` | {pa} | {wa} |\n")
    out.append(f"\nVerdict: {note}. Raw output: [`results/audit.log`](results/audit.log), "
               "[`results/axiom_walk.txt`](results/axiom_walk.txt).\n\n")
elif note: out.append(note + "\n\n")

# ---------------- 6. statement ----------------
h, note = head("statement", "## 6. Statement audit")
out.append(h + "\n\n")
sa = rd(RES + "/statement_audit.txt")
if sa:
    out.append("`StatementAudit.lean` (in `results/tools/`, run against the built `Main`) checks, by machine:\n\n")
    for pat, desc in [(r"^ORIGIN_OK .*$", None), (r"^STATEMENTS_IMPORTS_OK .*$", None),
                      (r"^STMT_DEPS_OK .*$", None), (r"^THM_TYPE_OK .*$", None)]:
        for l in re.findall(pat, sa, re.M): out.append(f"- `{l.strip()}`\n")
    for l in re.findall(r"^.*(?:ORIGIN_BAD|IMPORTS_BAD|DEPS_BAD|TYPE_BAD).*$", sa, re.M): out.append(f"- **{l.strip()}**\n")
    out.append("- `example : RiemannZetaZerosOnLine = RiemannHypothesis := rfl` "
               + ("type-checks.\n" if "STATEMENT_AUDIT_EXIT 0" in sa else "— see errors in the raw output.\n"))
    pr = rd(RES + "/package_revs.txt")
    m = re.search(r"^mathlib (\S+) dirty=(\d+)", pr, re.M)
    if m: out.append(f"- Mathlib checkout `{m.group(1)[:12]}`, {m.group(2)} modified files (all packages: [`results/package_revs.txt`](results/package_revs.txt)).\n")
    out.append("\nDefinitions as printed by Lean (`#print`), for reading by a human:\n\n```\n")
    body, cap = [], False
    for l in sa.splitlines():
        if re.match(r"^(@\[.*\] )?(noncomputable )?(def|theorem) ", l): cap = True
        elif re.match(r"^[A-Z_]+(_OK|_BAD)\b|^/|^STATEMENT|^\S+\.lean:", l): cap = False
        if cap: body.append(l)
    out.append("\n".join(body[:80]) + "\n```\n\n")
    out.append(f"Verdict: {note}. Raw output: [`results/statement_audit.txt`](results/statement_audit.txt).\n\n")
elif note: out.append(note + "\n\n")

# ---------------- 7. replay ----------------
h, note = head("replay", "## 7. Independent replay")
out.append(h + "\n\n")
out.append("""Tool: the kernel replay checker shipped with the toolchain itself, `leanchecker` (Lean v4.33.1,
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

""")
rs = rd(RES + "/replay_summary.txt")
if rs:
    out.append("```\n" + "\n".join(rs.splitlines()[:12]) + "\n```\n\n")
    xc = rd(RES + "/leanchecker_crosscheck.txt")
    lines = [l for l in xc.splitlines() if " rc=" in l]
    bad = [l for l in lines if " rc=0 " not in l + " "]
    if not lines:
        out.append("By the operator's decision (22:15 UTC), the planned 59-module cross-check with the shipped "
                   "`leanchecker` binary and the re-run of the negative control were dropped: Phase 4 replays every "
                   "module of the closure with leanchecker's own `replayFromImports` (verbatim copy).\n\n")
    else: out.append(f"Cross-check with the shipped `leanchecker` binary itself on {len(lines)} modules (`Main`, `Statements`, "
               f"`Supplements`, `CutCptCopy`/`CutMainCpt` and every module using `kexactB`/`kcopy`/`cpt_copy_thms`): "
               f"{len(lines)-len(bad)} passed, {len(bad)} failed ([`results/leanchecker_crosscheck.txt`](results/leanchecker_crosscheck.txt)).\n\n")
    out.append(f"Verdict: {note}.\n\n")
elif note: out.append(f"Status: {note}\n\n")
out.append("`leanchecker --fresh Main` (single-threaded re-check of the whole closure in an empty environment) was "
           "not run, by the operator's decision (22:22 UTC).\n")

txt = rd(VL)
i = txt.find("## 4.")
new = (txt[:i] if i >= 0 else txt.rstrip() + "\n\n") + "".join(out)
open(VL, "w", encoding="utf-8").write(new)
print("VERIFICATION_LOG.md sections 4-7 regenerated", time.strftime("%H:%M:%S", time.gmtime()))
