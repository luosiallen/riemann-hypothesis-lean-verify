#!/bin/bash
# Publish the full raw logs of run 2 to the repo (verification-logs/) once the kernel replay
# phase has been committed by kv/chain.sh. Waits; safe to start early. Never touches results/.
set -u
R=/home/allenluo/rhv; K=$R/kv; O=$R/repo/verification-logs; LOG=$R/logs/publish_logs.log
log(){ echo "$(date -u +%FT%TZ) $*" >> $LOG; }
san(){ sed -e "s#$R/src/lean/##g" -e "s#$R/#~/rhv/#g" -e "s#/home/allenluo#~#g"; }

log "waiting for the replay commit in kv/chain.log"
until grep -q "pushed: Run 2: kernel replay of Main's import closure" $K/chain.log \
      || { python3 -I -c "
import json,sys,time
p=[x for x in json.load(open('$R/events.json'))['phases'] if x['id']=='replay'][0]
sys.exit(0 if p.get('state') in ('done','failed') and time.time()-p.get('end',time.time())>900 else 1)"; }; do
  sleep 60
done
sleep 30
log "replay committed; building $O"
rm -rf $O; mkdir -p $O/discarded-run-2c
san < $R/logs/build.log | gzip -9 > $O/build.log.gz
san < $R/logs/warnings.log | xz -9 -T32 > $O/warnings.log.xz
[ -f $K/replay/out/replay_all.txt ] && san < $K/replay/out/replay_all.txt | gzip -9 > $O/replay_all.txt.gz
[ -f $K/replay/out/replay_modules.txt ] && gzip -9c $K/replay/out/replay_modules.txt > $O/replay_modules.txt.gz
san < $K/chain.log > $O/chain.log
san < $R/kv/sched_stats.txt > $O/sched_stats.txt 2>/dev/null
cp $R/events.json $O/phases.json
san < $R/logs/run2c/build.log | gzip -9 > $O/discarded-run-2c/build.log.gz
tar -C $R/logs/run2c -cf - errors | gzip -9 > $O/discarded-run-2c/errors.tar.gz
(cd $O && find . -type f ! -name SHA256SUMS ! -name README.md | sort | xargs sha256sum > SHA256SUMS)
cat > $O/README.md <<'EOF'
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
EOF
ls -la $O $O/discarded-run-2c >> $LOG
cd $R/repo
git add verification-logs
git commit -q -m "Publish raw logs of run 2 (build, warnings, kernel replay, pipeline) with checksums

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >> $LOG 2>&1
for i in 1 2 3 4 5; do
  git pull -q --rebase --autostash origin main >> $LOG 2>&1 && git push -q origin main >> $LOG 2>&1 && { log "pushed"; break; }
  log "push attempt $i failed"; sleep 60
done
touch $R/status/.logs_published
log "done"
