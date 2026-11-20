#!/bin/bash
# Second log upload: after kv/chain.sh finishes its supplementary `leanchecker --fresh Main` (and commits
# results/fresh_replay.txt), add the raw fresh-replay output to verification-logs/ and refresh the pipeline
# log, phase timestamps and checksums. Waits for publish_logs.sh's first upload. Touches only verification-logs/.
set -u
R=/home/allenluo/rhv; K=$R/kv; O=$R/repo/verification-logs; LOG=$R/logs/publish_logs.log
log(){ echo "$(date -u +%FT%TZ) [fresh] $*" >> $LOG; }
san(){ sed -e "s#$R/src/lean/##g" -e "s#$R/#~/rhv/#g" -e "s#/home/allenluo#~#g"; }

log "waiting for the first upload and for 'chain finished' in kv/chain.log"
until [ -f $R/status/.logs_published ] && grep -q ' chain finished' $K/chain.log; do sleep 120; done
sleep 60   # let chain.sh's own final push settle
san < $K/replay/out/fresh.txt | gzip -9 > $O/fresh_replay_leanchecker.txt.gz
san < $K/chain.log > $O/chain.log
cp $R/events.json $O/phases.json
(cd $O && find . -type f ! -name SHA256SUMS ! -name README.md | sort | xargs sha256sum > SHA256SUMS)
grep -q 'fresh_replay_leanchecker' $O/README.md || python3 -I - "$O/README.md" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
row = ("| `fresh_replay_leanchecker.txt.gz` | Phase 5 (supplementary). Output of the toolchain's own `leanchecker --fresh Main`: "
       "replays Main's whole import closure, Lean core included, into an empty environment, single-threaded, plus `/usr/bin/time -v` "
       "(wall time, peak memory). Verdict in `../results/fresh_replay.txt`. |\n")
anchor = "| `discarded-run-2c/` |"
s = s.replace(anchor, row + anchor, 1)
open(p, "w").write(s)
EOF
cd $R/repo
git add verification-logs
git commit -q -m "verification-logs: add the supplementary leanchecker --fresh Main output; refresh pipeline log and checksums

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" >> $LOG 2>&1
for i in 1 2 3 4 5; do
  git pull -q --rebase --autostash origin main >> $LOG 2>&1 && git push -q origin main >> $LOG 2>&1 && { log "pushed"; break; }
  log "push attempt $i failed"; sleep 60
done
log "done"
