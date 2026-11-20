#!/bin/bash
# Every 60 s: refresh logs.json + build_tail.txt in the status worktree (pusher.sh uploads them).
ROOT=/home/allenluo/rhv
while true; do
  python3 -I $ROOT/tools/logfeed.py $ROOT/status >> $ROOT/logs/logfeed.log 2>&1
  [ -f $ROOT/STOP_LOGFEED ] && exit 0
  sleep 60
done
