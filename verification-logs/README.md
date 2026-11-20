# Raw logs of verification run 2

Everything the server printed while checking the project, so anyone can audit the run.
Paths are shortened (`~/rhv/...`); nothing else is edited. Checksums: `SHA256SUMS`.

| File | What it is |
|---|---|
| `build.log.gz` | Phase 1. One line per module: ✔ built, ⚠ built with warnings, ✖ failed, with wall time. Ends with `SUMMARY` and `EXIT 0`. |
| `warnings.log.xz` | Phase 1. Every warning Lean printed (linter, deprecation, …). Search it for `sorry`: there are none. |
| `sched_stats.txt` | Final counters of the parallel scheduler (done / failed / blocked). |
| `replay_all.txt.gz` | Phase 4. One `OK <module> <ms>` line per module of `Main`'s import closure re-checked by the kernel (`replayexact`, a verbatim copy of `leanchecker`'s replay), plus any `FAIL` lines. |
| `replay_modules.txt.gz` | The module list that was replayed (Main's closure minus Init/Std/Lean/Lake). |
| `chain.log` | The post-compile pipeline: audits, replay, cross-check, commits, with UTC timestamps. |
| `phases.json` | Start/end time (Unix seconds, UTC) and result note of every phase. |
| `discarded-run-2c/` | The earlier attempt that ran `lean` without `-R src` (wrong module names). Kept for the record; not used. |

Verdicts and the audit outputs themselves are in [`../results/`](../results): `audit.log` (`#print axioms`),
`axiom_walk.txt`, `statement_audit.txt`, `package_revs.txt`, `replay_summary.txt`, and the checker sources in
`results/tools/`.

## Checking it yourself

```bash
sha256sum -c SHA256SUMS
zcat build.log.gz | tail -4                       # SUMMARY built=175187/175187 failed=0 … EXIT 0
zcat build.log.gz | grep -c '^✖'                  # 0 failed modules
xzcat warnings.log.xz | grep -ci 'declaration uses .sorry.'   # 0
zcat replay_all.txt.gz | grep -c '^OK '           # modules re-checked by the kernel
zcat replay_all.txt.gz | grep -c '^FAIL'          # 0
```

To reproduce from scratch: Lean v4.33.1, Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`, the sources from the
14 archive parts (checksums in `../parts.sha256`), and `lake build` (or `scripts/sched.py`, which passes `-R src` like Lake).
