#!/bin/bash
# Splits chain.sh step 4 into its own dashboard phase ("crosscheck") without touching the running chain.sh
# (bash reads a running script incrementally, so it must not be edited in place).
#   "replay done in N s: ... VERDICT X"      -> replay done/failed at that time, crosscheck running
#   "crosscheck (n bad)=N B negctl_detected=K/2" -> crosscheck done/failed at that time
#   chain's own "event replay done|failed"   -> re-applied replay end/note from the first line
#     (chain.sh marks replay only after step 4 and folds the cross-check into its note).
set -u
R=/home/allenluo/rhv; L=$R/kv/chain.log; RES=$R/repo/results; ME=$R/logs/xc_watch.log
ev(){ python3 -I $R/tools/event.py "$@"; echo "$(date -u +%FT%TZ) event $*" >> $ME; }
ts(){ date -d "$1" +%s; }
echo "$(date -u +%FT%TZ) xc_watch start pid $$" >> $ME

until grep -q ' replay done in ' $L; do sleep 15; done
line=$(grep ' replay done in ' $L | tail -1); T1=$(ts "${line%% *}")
secs=$(sed -E 's/.* replay done in ([0-9]+) s.*/\1/' <<< "$line")
okn=$(grep -oE 'replayed_ok=[0-9]+' $RES/replay_summary.txt | cut -d= -f2)
fl=$(grep -oE 'failed=[0-9]+' $RES/replay_summary.txt | head -1 | cut -d= -f2)
if grep -q '^VERDICT OK' $RES/replay_summary.txt; then
  RST=done; RNOTE="$okn modules of Main's import closure re-checked by the kernel (replayexact), ${fl:-0} failures, $((secs/60)) min"
else
  RST=failed; RNOTE="$(grep -E '^(replayed_ok|VERDICT)' $RES/replay_summary.txt | tr '\n' ' ')"
fi
ev replay $RST "$RNOTE" $T1
ev crosscheck running "toolchain leanchecker on 59 modules (64 parallel), then the negative control" $T1

until grep -q ' crosscheck (n bad)=' $L; do sleep 15; done
line=$(grep ' crosscheck (n bad)=' $L | tail -1); T2=$(ts "${line%% *}")
read -r XN XB <<< "$(sed -E 's/.*\(n bad\)=([0-9]+) ([0-9]+).*/\1 \2/' <<< "$line")"
NC=$(sed -E 's/.*negctl_detected=([0-9]+)\/2.*/\1/' <<< "$line")
if [ "$XB" = "0" ] && [ "$XN" -gt 0 ] && [ "$NC" = "2" ]; then
  ev crosscheck done "leanchecker: $XN/$XN modules OK; negative control: planted False proof rejected by both leanchecker and replayexact (2/2)" $T2
else
  ev crosscheck failed "leanchecker: $XB of $XN modules failed; negative control detected $NC/2" $T2
fi

until grep -qE ' event replay (done|failed) ' $L; do sleep 15; done
ev replay $RST "$RNOTE" $T1
echo "$(date -u +%FT%TZ) xc_watch done" >> $ME
