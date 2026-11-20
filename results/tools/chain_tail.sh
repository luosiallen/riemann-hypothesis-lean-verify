#!/bin/bash
# Takes over chain.sh after step 3's replay was launched (operator decision, 2026-11-20 ~22:15 UTC):
# Phase 4 only (the parallel replayexact run of Main's closure). chain.sh's step 4 (59-module
# shipped-leanchecker cross-check and negative-control re-run) and step 5 (leanchecker --fresh Main)
# are not run.
# Usage: chain_tail.sh <pid of the replay xargs started by chain.sh>
set -u
TC=$HOME/.elan/toolchains/leanprover--lean4---v4.33.1
export PATH=$TC/bin:$HOME/.local/bin:$HOME/.elan/bin:/usr/local/bin:/usr/bin:/bin
R=/home/allenluo/rhv; K=$R/kv; RP=$K/replay; RES=$R/repo/results
LOG=$K/chain.log; OUT=$RP/out
export LEAN_PATH=$(cat $K/LEAN_PATH)
XPID=$1
log(){ echo "$(date -u +%FT%TZ) $*" >> $LOG; }
ev(){ python3 -I $R/tools/event.py "$@"; log "event $*"; }
genlog(){ python3 -I $K/write_log.py >> $LOG 2>&1; }
commit(){  # $1 = message subject
  cd $R/repo || return
  git add results VERIFICATION_LOG.md
  if git diff --cached --quiet; then log "commit: nothing to commit"; cd $R/src/lean; return; fi
  git commit -q -m "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >> $LOG 2>&1
  for i in 1 2 3 4 5; do
    git pull -q --rebase --autostash origin main >> $LOG 2>&1 && git push -q origin main >> $LOG 2>&1 && { log "pushed: $1"; break; }
    log "push attempt $i failed"; sleep 60
  done
  cd $R/src/lean
}
cd $R/src/lean
log "chain_tail start pid $$: took over from chain.sh (operator decision: Phase 4 only; cross-check, negative-control re-run and leanchecker --fresh Main dropped). Waiting for replay xargs pid $XPID"

# --- 3 (cont). wait for the replay launched by chain.sh, then summarise ---
while kill -0 $XPID 2>/dev/null; do sleep 20; done
t1=$(date +%s)
t0=$(date -d "$(grep ' replay start: ' $LOG | tail -1 | cut -d' ' -f1)" +%s)
CLO=$OUT/main_closure.txt
nmods=$(wc -l < $OUT/replay_modules.txt); ncore=$(( $(wc -l < $CLO) - nmods ))
cat $OUT/chunks/c*.out > $OUT/replay_all.txt
python3 -I - $OUT $((t1-t0)) $ncore > $RES/replay_summary.txt <<'EOF'
import sys, re, glob
out, secs, ncore = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
mods = [l.strip() for l in open(out + "/replay_modules.txt") if l.strip()]
txt = open(out + "/replay_all.txt").read()
okm = dict(re.findall(r"^OK (\S+) (\d+)ms$", txt, re.M))
fails = re.findall(r"^FAIL (\S+): (.*)$", txt, re.M)
notok = [m for m in mods if m not in okm]
tot = sum(int(v) for v in okm.values())
roots = {}
for m in okm: r = m.split(".")[0]; roots[r] = roots.get(r, 0) + 1
slow = sorted(okm.items(), key=lambda x: -int(x[1]))[:10]
print(f"tool=replayexact (verbatim leanchecker replayFromImports, Lean v4.33.1)")
print(f"closure_noncore_modules={len(mods)} core_modules_skipped={ncore}")
print(f"replayed_ok={len(okm)} failed={len(fails)} not_ok={len(notok)}")
print(f"wall_seconds={secs} sum_module_seconds={tot//1000}")
print(f"ok_by_root={dict(sorted(roots.items(), key=lambda x: -x[1]))}")
print("slowest=" + ", ".join(f"{m} {int(v)/1000:.1f}s" for m, v in slow))
print("VERDICT " + ("OK" if not fails and not notok and mods else "BAD"))
for m, e in fails[:200]: print("FAIL", m, e[:300])
for m in notok[:200]: print("NOT_OK", m)
EOF
grep -A8 '^FAIL' $OUT/replay_all.txt | head -400 > $RES/replay_failures.txt
log "replay done in $((t1-t0)) s: $(grep -E '^(replayed_ok|VERDICT)' $RES/replay_summary.txt | tr '\n' ' ')"
if grep -q '^VERDICT OK' $RES/replay_summary.txt; then
  ev replay done "$(grep -oE 'replayed_ok=[0-9]+' $RES/replay_summary.txt | cut -d= -f2) modules of Main's import closure re-checked by the kernel (replayexact), 0 failures ($(( (t1-t0)/60 )) min)" $t1
else
  ev replay failed "$(grep -E '^(replayed_ok|VERDICT)' $RES/replay_summary.txt | tr '\n' ' ')" $t1
fi
mkdir -p $RES/tools
cp $RP/ReplayExact.lean $RP/AxiomWalk.lean $RP/AxiomWalk.v1.lean $RP/ModClosure.lean $K/audit2/StatementAudit.lean \
   $K/chain.sh $K/chain_tail.sh $K/write_log.py $RES/tools/
gzip -9c $CLO > $RES/main_closure.txt.gz; sha256sum $CLO | awk '{print $1}' > $RES/main_closure.sha256
genlog; commit "Run 2: kernel replay of Main's import closure"

log "chain finished (Phase 4 only; leanchecker --fresh Main not run, operator decision 22:22 UTC)"
