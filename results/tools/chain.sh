#!/bin/bash
# Run-2 post-build verification chain (detached). Waits for the build driver's final `EXIT <code>`,
# then: build phase -> axiom audit -> statement audit -> parallel kernel replay of Main's closure
# -> shipped-leanchecker cross-check -> results + VERIFICATION_LOG -> commit/push (results + log only).
# Never calls `lake build` (sched.py writes no Lake traces).
set -u
TC=$HOME/.elan/toolchains/leanprover--lean4---v4.33.1
export PATH=$TC/bin:$HOME/.local/bin:$HOME/.elan/bin:/usr/local/bin:/usr/bin:/bin
R=/home/allenluo/rhv; K=$R/kv; RP=$K/replay; RES=$R/repo/results; B=$R/logs/build.log
LOG=$K/chain.log; OUT=$RP/out
export LEAN_PATH=$(cat $K/LEAN_PATH)
REPLAY_P=${REPLAY_P:-280}
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
log "chain start pid $$ (REPLAY_P=$REPLAY_P)"
mkdir -p $RES $OUT

# --- throughput sampler (every 5 min until EXIT) ---
(
  echo "# time_utc modules_done(✔/⚠ lines) d_modules/min lean_procs load1 mem_used_gb" >> $K/throughput.log
  pd=0; pt=$(date +%s)
  until grep -q '^EXIT ' $B 2>/dev/null; do
    now=$(date +%s); d=$(grep -c '^[✔⚠] \[' $B 2>/dev/null); dt=$((now-pt)); [ $dt -lt 1 ] && dt=1
    echo "$(date -u +%T) $d $(( (d-pd)*60/dt )) $(pgrep -c -x lean) $(cut -d' ' -f1 /proc/loadavg) $(free -g | awk '/^Mem/{print $3}')" >> $K/throughput.log
    pd=$d; pt=$now; sleep 300
  done
  echo "$(date -u +%T) EXIT seen: $(grep '^EXIT ' $B | tail -1)" >> $K/throughput.log
) &

# --- 1. wait for the build to finish (re-arm if a failed build is rerun) ---
while true; do
  until head -1 $B 2>/dev/null | grep -q 'driver=sched.py' && grep -q '^EXIT ' $B; do sleep 60; done
  code=$(grep '^EXIT ' $B | tail -1 | awk '{print $2}')
  ino=$(stat -c %i $B)
  summ=$(grep '^SUMMARY' $B | tail -1 | sed 's/^SUMMARY //')
  wall=$(grep '^Elapsed (wall clock)' $B | tail -1 | awk '{print $NF}')
  start=$(head -1 $B | awk '{print $2}')
  nf=$(grep -c '^✖' $B)
  { echo "# Run 2 build summary (generated $(date -u +%FT%TZ))"
    echo "## lake build phase (stopped, see VERIFICATION_LOG section 4): logs/build.run2b.log"
    head -2 $R/logs/build.run2b.log 2>/dev/null | sed -n 1p
    echo "## sched.py phase"
    grep -E '^(START|GRAPH|SUMMARY|Elapsed|EXIT)' $B
    echo "failed_lines=$nf"
    grep '^✖' $B | head -200
    echo "modules_with_warnings=$(grep -c '^== ' $R/logs/warnings.log 2>/dev/null)"
    echo "warning_lines_mentioning_sorry=$(grep -ci 'sorry' $R/logs/warnings.log 2>/dev/null)"
    echo "build_log_lines_mentioning_sorry=$(grep -ci 'sorry' $B)"
    grep -i 'sorry' $R/logs/warnings.log 2>/dev/null | head -50
  } > $RES/build_summary.txt
  cp $K/throughput.log $RES/throughput_run2.txt 2>/dev/null; cp $K/rate.log $RES/rate_sampler_run2.txt 2>/dev/null
  if [ "$code" = "0" ]; then
    ev build done "sched.py exit 0: $summ; wall $wall from $start (after 11 min of lake build from 17:49:55)"
    break
  fi
  ev build failed "sched.py EXIT $code: $summ; wall $wall"
  if [ ! -f $R/src/lean/.lake/build/lib/lean/Main.olean ]; then
    for p in axioms statement replay; do ev $p pending "blocked: build failed (EXIT $code), Main.olean not built"; done
    genlog; commit "Run 2: build finished with EXIT $code ($nf failed modules)"
    log "build failed; waiting for a new build.log (rerun) ..."
    while [ "$(stat -c %i $B 2>/dev/null)" = "$ino" ] && ! grep -q 'rerun' $K/chain.ctl 2>/dev/null; do sleep 120; done
    continue
  fi
  log "build EXIT $code but Main.olean exists; continuing with audits (noted as such)"
  break
done

# --- 2. axiom + statement audit (parallel) ---
ev axioms running "Audit.lean (#print axioms) + independent axiom walk"
ev statement running "StatementAudit.lean"
( lean $R/audit/Audit.lean > $RES/audit.log 2>&1; echo "AUDIT_EXIT $?" >> $RES/audit.log ) &
( lean $K/audit2/StatementAudit.lean > $RES/statement_audit.txt 2>&1; echo "STATEMENT_AUDIT_EXIT $?" >> $RES/statement_audit.txt ) &
( $RP/modclosure Main > $OUT/main_closure.txt 2> $OUT/main_closure.err; echo $? > $OUT/main_closure.rc ) &
for t in riemannHypothesis riemannZeta_eq_zero_re LFunction_ne_zero_of_half_lt_re LFunction_eq_zero_re LFunction_eq_zero_re_of_isPrimitive; do
  ( $RP/axiomwalk Main $t > $OUT/walk_$t.txt 2>&1; echo "WALK_EXIT $?" >> $OUT/walk_$t.txt ) &
done
wait
cp $R/logs/audit.log $R/logs/audit.prev.log 2>/dev/null; cp $RES/audit.log $R/logs/audit.log
cat $OUT/walk_*.txt > $RES/axiom_walk.txt
{ echo "# package checkouts (git rev, dirty file count)"
  for p in $R/src/lean/.lake/packages/*; do echo "$(basename $p) $(git -C $p rev-parse HEAD) dirty=$(git -C $p status --porcelain | wc -l)"; done
  echo "lake-manifest mathlib rev: $(python3 -I -c "import json;print([p['rev'] for p in json.load(open('$R/src/lean/lake-manifest.json'))['packages'] if p['name']=='mathlib'][0])")"
} > $RES/package_revs.txt
AXV=$(python3 -I - <<'EOF'
import re
ok = {"propext", "Classical.choice", "Quot.sound"}
thms = ["riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re", "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive"]
a = open("/home/allenluo/rhv/repo/results/audit.log").read()
w = open("/home/allenluo/rhv/repo/results/axiom_walk.txt").read()
bad = []; seen = set()
for t in thms:
    m = re.search(r"'%s' depends on axioms: \[([^\]]*)\]" % re.escape(t), a)
    n = re.search(r"'%s' does not depend on any axioms" % re.escape(t), a)
    if m: ax = {x.strip() for x in m.group(1).split(",") if x.strip()}
    elif n: ax = set()
    else: bad.append(t + ":no #print axioms output"); continue
    seen |= ax
    if ax - ok: bad.append(t + ":" + ",".join(sorted(ax - ok)))
    wm = re.search(r"WALK %s: reachable=(\d+) axioms=\[([^\]]*)\] missing=(\d+)" % re.escape(t), w)
    if not wm: bad.append(t + ":no walk output"); continue
    wax = {x.strip() for x in wm.group(2).split(",") if x.strip()}
    if wax != ax: bad.append(t + ":walk/print mismatch")
    if wm.group(3) != "0": bad.append(t + ":walk missing constants")
if "AUDIT_EXIT 0" not in a: bad.append("Audit.lean exit nonzero")
print(("OK " if not bad else "BAD ") + "axioms=" + ",".join(sorted(seen)) + (" problems=" + ";".join(bad) if bad else ""))
EOF
)
log "axiom verdict: $AXV"
if [[ $AXV == OK* ]]; then ev axioms done "All 5 theorems: only ${AXV#OK axioms=} (#print axioms and independent body walk agree)"
else ev axioms failed "${AXV#BAD }"; fi
SV=BAD
if grep -q 'STATEMENT_AUDIT_OK' $RES/statement_audit.txt && grep -q 'STATEMENT_AUDIT_EXIT 0' $RES/statement_audit.txt \
   && ! grep -q 'dirty=[1-9]' $RES/package_revs.txt && grep -q '^mathlib 0df444a360eaa60ab8c11dca51a86af692955474 dirty=0' $RES/package_revs.txt; then SV=OK; fi
log "statement verdict: $SV"
if [ $SV = OK ]; then ev statement done "Mathlib RiemannHypothesis/riemannZeta/LFunction/IsPrimitive (Mathlib 0df444a, clean); RiemannZetaZerosOnLine = RiemannHypothesis by rfl; Statements imports only Mathlib; theorem types exact"
else ev statement failed "see results/statement_audit.txt"; fi
genlog; commit "Run 2: build result, axiom audit and statement audit"

# --- 3. kernel replay of Main's import closure ---
ev replay running "replaying every module in Main's import closure (parallel, $REPLAY_P processes)"
CLO=$OUT/main_closure.txt
if [ "$(cat $OUT/main_closure.rc)" != "0" ]; then log "modclosure failed"; fi
grep -vE '^(Init|Std|Lean|Lake)(\.|$)' $CLO | shuf --random-source=<(yes) > $OUT/replay_modules.txt
nmods=$(wc -l < $OUT/replay_modules.txt); ncore=$(( $(wc -l < $CLO) - nmods ))
rm -rf $OUT/chunks; mkdir -p $OUT/chunks; split -l 100 -d -a 5 $OUT/replay_modules.txt $OUT/chunks/c
t0=$(date +%s); log "replay start: $nmods modules ($ncore core modules skipped), $(ls $OUT/chunks | wc -l) chunks"
ls $OUT/chunks/c* | xargs -P $REPLAY_P -I{} sh -c '"$0" "$1" > "$1.out" 2>&1; echo "RC $?" >> "$1.out"' $RP/replayexact {}
t1=$(date +%s)
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

# --- 4. cross-check with the toolchain's own leanchecker binary + negative control ---
xargs -a $RP/crosscheck.txt -P 64 -I{} sh -c 's=$(date +%s); leanchecker "$0" > /dev/null 2> "$1/xc_$0.err"; echo "$0 rc=$? $(( $(date +%s)-s ))s"' {} $OUT > $RES/leanchecker_crosscheck.txt
for f in $OUT/xc_*.err; do [ -s $f ] && { echo "== $f"; head -20 $f; } >> $RES/leanchecker_crosscheck.txt; done
NC=$RP/negctl
{ echo "# negative control: NegCtl adds 'bogusFalse : False := True.intro' with debug.skipKernelTC"
  echo "## shipped leanchecker:"; LEAN_PATH=$NC:$TC/lib/lean leanchecker NegCtl 2>&1 | head -6; echo "rc=${PIPESTATUS[0]}"
  echo "## replayexact:"; LEAN_PATH=$NC:$TC/lib/lean $RP/replayexact $NC/list.txt 2>&1 | head -8; echo "rc=${PIPESTATUS[0]}"
  echo "## axiomwalk (expected to NOT catch it: no axioms are involved):"; LEAN_PATH=$NC:$TC/lib/lean $RP/axiomwalk NegCtl usesBogus 2>&1 | head -3
} > $RES/negative_control.txt
XOK=$(awk '/ rc=/{n++; if ($2!="rc=0") b++} END{print n+0, b+0}' $RES/leanchecker_crosscheck.txt)
NCOK=$(grep -c '^rc=1$' $RES/negative_control.txt)
log "crosscheck (n bad)=$XOK negctl_detected=$NCOK/2"
if grep -q '^VERDICT OK' $RES/replay_summary.txt && [ "${XOK#* }" = "0" ] && [ "$NCOK" = "2" ]; then
  ev replay done "$(grep -oE 'replayed_ok=[0-9]+' $RES/replay_summary.txt | cut -d= -f2) modules of Main's closure re-checked by the kernel, 0 failures ($(( (t1-t0)/60 )) min); shipped leanchecker cross-check ${XOK% *}/${XOK% *} OK"
else
  ev replay failed "$(grep -E '^(replayed_ok|VERDICT)' $RES/replay_summary.txt | tr '\n' ' ') crosscheck(n,bad)=$XOK negctl=$NCOK/2"
fi
mkdir -p $RES/tools
cp $RP/ReplayExact.lean $RP/AxiomWalk.lean $RP/ModClosure.lean $RP/crosscheck.txt $K/audit2/StatementAudit.lean $K/chain.sh $K/write_log.py $RES/tools/
gzip -9c $CLO > $RES/main_closure.txt.gz; sha256sum $CLO | awk '{print $1}' > $RES/main_closure.sha256
genlog; commit "Run 2: kernel replay of Main's import closure"

# --- 5. supplementary: single-threaded fresh-environment replay of Main (leanchecker --fresh) ---
log "fresh replay start"
s=$(date +%s)
timeout 48h /usr/bin/time -v leanchecker --fresh Main > $OUT/fresh.txt 2>&1; rc=$?
{ echo "leanchecker --fresh Main: rc=$rc wall_seconds=$(( $(date +%s)-s ))"; grep -E 'Maximum resident|Elapsed' $OUT/fresh.txt; grep -v '^\s' $OUT/fresh.txt | head -30; } > $RES/fresh_replay.txt
log "fresh replay rc=$rc"
genlog; commit "Run 2: supplementary fresh-environment replay (leanchecker --fresh Main)"
log "chain finished"
