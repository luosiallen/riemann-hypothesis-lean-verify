#!/bin/bash
# Every 120 s: collect a status snapshot and force-push it as a single commit to the `status` branch.
export PATH=$HOME/.local/bin:$HOME/.elan/bin:$PATH
ROOT=/home/allenluo/rhv
S=$ROOT/status
while true; do
  python3 -I $ROOT/tools/collect.py $S >> $ROOT/logs/pusher.log 2>&1
  if [ -e $S/.git ]; then
    cd $S && git add -A >/dev/null 2>&1 && git commit -q --amend -m "status snapshot $(date -u +%FT%TZ)" >/dev/null 2>&1 \
      && git push -q -f origin status >> $ROOT/logs/pusher.log 2>&1
  fi
  [ -f $ROOT/STOP_PUSHER ] && exit 0
  sleep 120
done
