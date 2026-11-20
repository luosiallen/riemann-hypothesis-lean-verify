#!/bin/bash
# Discard run 2c (sched.py without -R: modules named src.<Path>) and rebuild from scratch with -R srcDir.
set -u
R=/home/allenluo/rhv; cd $R
pid=$(pgrep -f '^python3 -I tools/[s]ched.py' | head -1)
[ -n "$pid" ] && kill -TERM $pid
for i in $(seq 60); do pgrep -f '^python3 -I tools/[s]ched.py' >/dev/null || break; sleep 1; done
pkill -x lean; sleep 2; pkill -9 -x lean
mkdir -p logs/run2c && mv logs/build.log logs/warnings.log logs/errors kv/sched_stats.txt logs/run2c/ 2>/dev/null
mkdir -p logs/errors
rm -rf $R/src/lean/.lake/build
rm -f $R/history.json
python3 -I tools/event.py build running "Rebuild from scratch $(date -u +%H:%M) UTC with --root fix (-R srcDir); sched.py, 288 parallel lean processes. Run 2c discarded: module names were src.<Path> (1 failed, 425 blocked)" 
JOBS=288 setsid nohup python3 -I tools/sched.py > logs/sched.stdout 2>&1 < /dev/null &
echo "restarted"
